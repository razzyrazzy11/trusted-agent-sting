import json
import os
from pathlib import Path

import pytest

from sting import texts
from sting.config import ARMS, SequenceConfig, StingPolicy
from sting.game import StingGame, split_memory
from sting.players import TrackedPlayer
from sting.sequence import assign_names, run_sequence
from sting.stub import StubModel, stub_factory


def _rows(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")]


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    """Stub sequences for every arm and a few seeds (fast, deterministic)."""
    import contextlib, io
    root = tmp_path_factory.mktemp("live")
    lb = Path(__file__).resolve().parents[1] / "Collusion_Liars_Bar"
    cwd = os.getcwd()
    os.chdir(lb)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            for arm in ARMS:
                for seed in range(4):
                    run_sequence(SequenceConfig(arm=arm, seed=seed), root, stub_factory=stub_factory(seed))
    finally:
        os.chdir(cwd)
    return root


def _seq(root, arm, seed):
    return root / arm / "llama-3.1-8b" / f"seed_{seed:03d}"


def test_outputs_complete(runs):
    for arm in ARMS:
        d = _seq(runs, arm, 0)
        for f in ("DONE", "meta.json", "decisions.jsonl", "events.jsonl", "probes.jsonl", "calls.jsonl.gz"):
            assert (d / f).exists(), (arm, f)
        assert len(list((d / "games").glob("game_*.json"))) == 6
        assert not d.with_name(d.name + ".tmp").exists()


def test_private_record_only_in_post_games_and_in_harness_wrapper(runs):
    for arm in ("B0", "B1", "B2", "B3", "B4"):
        meta = json.loads((_seq(runs, arm, 1) / "meta.json").read_text())
        record = meta["record"]
        assert record and record.startswith(texts.RECORD_HEADER)
        calls = _decisions(runs, arm, 1)
        for r in calls:
            if r["actor_role"] != "T":
                assert not r["has_memory"]
            elif r["period"] == "pre":
                assert not r["has_memory"]
            else:
                assert r["has_memory"]
        # The wrapper is the harness's own: check one raw prompt in the call log.
        import gzip
        with gzip.open(_seq(runs, arm, 1) / "calls.jsonl.gz", "rt") as f:
            for line in f:
                c = json.loads(line)
                if c["purpose"] == "challenge" and c.get("meta_role") == "T" and "CROSS-GAME MEMORY" in c["messages"][-1]["content"]:
                    assert texts.MEMORY_WRAP.format(memory=record) in c["messages"][-1]["content"]
                    break
            else:
                pytest.fail(f"no T challenge prompt with a record in {arm}")


def _decisions(root, arm, seed):
    return _rows(_seq(root, arm, seed) / "decisions.jsonl")


def test_seating_and_actual_challenger(runs):
    n_a = n_b = 0
    for arm in ARMS:
        for seed in range(4):
            for r in _decisions(runs, arm, seed):
                if r["decision_type"] != "play":
                    continue
                if r["arrangement"] == "A" and r["actor_role"] == "S":
                    if r["counterpart_role"] == "T":
                        n_a += 1
                        assert not r["challenger_skipped_seat"]
                    else:   # T must have had no cards (or be dead), so the challenger skipped a seat
                        assert r["challenger_skipped_seat"] or "T" not in r["alive"]
                if r["arrangement"] == "B" and r["actor_role"] == "T":
                    if r["counterpart_role"] == "S":
                        n_b += 1
    assert n_a > 50 and n_b > 50


def test_sting_policy_is_arm_invariant(runs):
    post_T, pre = [], []
    for arm in ARMS:
        for seed in range(4):
            for r in _decisions(runs, arm, seed):
                if r["decision_type"] == "challenge" and r["actor_role"] == "S":
                    if r["period"] == "post" and r["counterpart_role"] == "T":
                        post_T.append(r["challenged"])
                    if r["period"] == "pre":
                        pre.append(r["challenged"])
    assert post_T and not any(post_T)              # S never challenges T after the offer, in every arm
    assert 0.35 < sum(pre) / len(pre) < 0.65


def test_common_random_numbers_across_arms(runs):
    def first_round(arm, seed):
        ev = _rows(_seq(runs, arm, seed) / "events.jsonl")
        return [e for e in ev if e["event"] == "round_start" and e["game"] == 1][0]
    base = first_round("B1", 2)
    for arm in ARMS:
        r = first_round(arm, 2)
        assert r["hands"] == base["hands"] and r["target_card"] == base["target_card"]
        assert r["starting_role"] == base["starting_role"]
        meta = json.loads((_seq(runs, arm, 2) / "meta.json").read_text())
        assert meta["names"] == assign_names(2)


def test_no_double_round_reset(runs):
    for arm in ARMS:
        ev = _rows(_seq(runs, arm, 3) / "events.jsonl")
        for g in range(1, 7):
            rounds = [e["round"] for e in ev if e["event"] == "round_start" and e["game"] == g]
            assert rounds == list(range(1, len(rounds) + 1))
            ends = sum(1 for e in ev if e["game"] == g and e["event"] in ("shot", "system_challenge"))
            # every new round follows exactly one round-ending event
            assert len(rounds) <= ends + 1


def test_consent_recorded_and_probes(runs):
    for arm, spec in ARMS.items():
        meta = json.loads((_seq(runs, arm, 0) / "meta.json").read_text())
        probes = _rows(_seq(runs, arm, 0) / "probes.jsonl")
        assert sum(p["probe"] == "suspicion" for p in probes) == 3
        if spec["offer"]:
            assert meta["offer"]["decision_strict"] in ("ACCEPT", "REFUSE", "UNCLEAR")
            assert meta["offer"]["reply"]
            assert sum(p["probe"] == "interview" for p in probes) == 4
        else:
            assert meta["offer"] is None and texts.RECORD_NULL in meta["record"]
            assert not any(p["probe"] == "interview" for p in probes)


def test_shots_fired_display_is_true_count(quiet, tmp_path):
    stub = StubModel("llama-3.1-8b")
    from sting.client import StudyClient
    client = StudyClient("llama-3.1-8b", stub=stub)
    from sting.players import StingPlayer
    S = StingPlayer("Mike", "llama-3.1-8b", client, StingPolicy())
    T = TrackedPlayer("Lily", "llama-3.1-8b", "T", client)
    O1 = TrackedPlayer("Luke", "llama-3.1-8b", "O1", client)
    O2 = TrackedPlayer("Quinn", "llama-3.1-8b", "O2", client)

    class L:
        def __init__(self): self.d, self.e = [], []
        def decision(self, r): self.d.append(r)
        def event(self, r): self.e.append(r)
    log = L()
    g = StingGame([S, T, O1, O2], seed=5, game_no=1, period="pre", arrangement="A", policy=StingPolicy(),
                  logger=log, records_dir=tmp_path, context={})
    with quiet():
        g.start_game()
    # After the game, every round's recorded gun position equals true shots fired at round start.
    shots_so_far = {p.name: 0 for p in g.players}
    for rnd in g.game_record.rounds:
        for ps in rnd.player_initial_states:
            assert ps.current_gun_position == shots_so_far[ps.player_name]
        if rnd.round_result and rnd.round_result.shooter_name in shots_so_far:
            shots_so_far[rnd.round_result.shooter_name] += 1


def test_second_last_survivor_bonus(tmp_path):
    from sting.client import StudyClient
    client = StudyClient("llama-3.1-8b", stub=StubModel("llama-3.1-8b"))
    from sting.players import StingPlayer
    S = StingPlayer("Mike", "llama-3.1-8b", client, StingPolicy())
    T = TrackedPlayer("Lily", "llama-3.1-8b", "T", client)
    O1 = TrackedPlayer("Luke", "llama-3.1-8b", "O1", client)
    O2 = TrackedPlayer("Quinn", "llama-3.1-8b", "O2", client)

    class L:
        def decision(self, r): pass
        def event(self, r): pass
    g = StingGame([S, T, O1, O2], seed=1, game_no=1, period="pre", arrangement="A", policy=StingPolicy(),
                  logger=L(), records_dir=tmp_path, context={})
    g.choose_target_card(); g.deal_cards(); g.start_round_record()
    O1.alive = False; O2.alive = False                 # two players left: S and T
    T.bullet_position = T.current_bullet_position      # next pull fires
    g.perform_penalty(T)
    # T is the second-last survivor (+2) and is eliminated (-2); S is last survivor (+1 survive, +3 last)
    assert g.scores["Lily"] == 0 and g.scores["Mike"] == 4 and g.game_over


def test_fallbacks_are_logged(runs):
    rows = [r for arm in ARMS for seed in range(4) for r in _decisions(runs, arm, seed)]
    fb = [r for r in rows if r["fallback"]]
    assert fb, "the stub's stuck prompts should trigger harness fallbacks"
    for r in fb:
        assert r["attempts"] == 5
        if r["decision_type"] == "challenge":
            assert r["challenged"] is False          # harness default: do not challenge


def test_patched_harness_has_no_empty_rounds(tmp_path, monkeypatch, quiet):
    """The secret-tool game used to reset each round twice, leaving an empty round per challenge."""
    lb = Path(__file__).resolve().parents[1] / "Collusion_Liars_Bar"
    (tmp_path / "prompts").symlink_to(lb / "prompts")
    monkeypatch.chdir(tmp_path)

    class HarnessStub:
        stubs = {}

        def chat(self, messages, model="llama-3.1-8b", max_new_tokens=4096):
            s = HarnessStub.stubs.setdefault(model, StubModel(model, seed=3))
            return s.respond(messages, model), ""

    monkeypatch.setattr("src.agents.player.LLMClient", HarnessStub)
    import random
    random.seed(11)
    from src.game.game_secret_channel import GameSecretChannel
    cfgs = [{"name": n, "model": "llama-3.1-8b"} for n in ("Lily", "Luke", "Mike", "Quinn")]
    game = GameSecretChannel(cfgs, {})
    with quiet():
        game.start_game()
    rounds = game.game_record.rounds
    assert len(rounds) > 2
    assert all(len(r.play_history) > 0 for r in rounds), "empty rounds mean a double reset"
