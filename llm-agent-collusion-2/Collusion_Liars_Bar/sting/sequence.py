"""One live sequence (Stage L): n_games games with the same four players, seat arrangement
alternating A/B, the offer + consent step before `offer_game`, the private record re-attached to
T in every later game (the harness rebuilds players each game, so nothing else carries over),
and the end-of-series probes.

Output (written to <dir>.tmp, renamed to <dir> when complete, so crashed runs restart cleanly):
  meta.json        config, names, offer and consent, per-game results, call/cost stats, versions
  decisions.jsonl  one row per play/challenge decision (actual challenger, fallbacks, T prompts)
  events.jsonl     round starts, shots, system challenges, game ends, the offer
  probes.jsonl     suspicion funnel (T, O1, O2) and follow-up interview (T)
  calls.jsonl.gz   every LLM call (prompt, reply, tokens, latency, errors)
  games/           the harness's own per-game JSON records
"""
from __future__ import annotations

import json
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, Dict, Optional

from . import STUDY_VERSION, texts
from .client import ClientPool, JsonlSink
from .config import ARMS, ARRANGEMENTS, NAMES, ROLES, SequenceConfig
from .game import StingGame
from .offers import record_for_offer, run_offer
from .players import StingPlayer, TrackedPlayer
from .probes import run_interview, run_suspicion, series_summary
from .rng import stream


class StudyLogger:
    def __init__(self, out_dir: Path):
        self.decisions = JsonlSink(out_dir / "decisions.jsonl")
        self.events = JsonlSink(out_dir / "events.jsonl")
        self.probes = JsonlSink(out_dir / "probes.jsonl")

    def decision(self, rec: dict) -> None:
        self.decisions.write(rec)

    def event(self, rec: dict) -> None:
        self.events.write(rec)

    def probe(self, rec: dict) -> None:
        self.probes.write(rec)


def assign_names(seed: int) -> Dict[str, str]:
    names = list(NAMES)
    stream("names", seed).shuffle(names)
    return dict(zip(ROLES, names))


def sequence_dir(root: Path, cfg: SequenceConfig) -> Path:
    return Path(root) / cfg.arm / cfg.model / f"seed_{cfg.seed:03d}"


def git_commit() -> Optional[str]:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                              cwd=texts.LB_ROOT, timeout=10).stdout.strip() or None
    except Exception:
        return None


def run_sequence(cfg: SequenceConfig, root: Path, stub_factory: Optional[Callable] = None,
                 overwrite: bool = False) -> dict:
    final = sequence_dir(root, cfg)
    if (final / "DONE").exists() and not overwrite:
        existing = json.loads((final / "meta.json").read_text())
        if bool(existing.get("stub")) != (stub_factory is not None):
            raise RuntimeError(f"{final} holds {'stub' if existing.get('stub') else 'real'} data; refusing to "
                               f"mix runs. Use a different output directory.")
        return existing
    tmp = final.with_name(final.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    arm = ARMS[cfg.arm]
    seq_id = f"{cfg.arm}-{cfg.model}-s{cfg.seed:03d}"
    ctx = dict(stage="L", arm=cfg.arm, seed=cfg.seed, seq_id=seq_id, model=cfg.model)
    pool = ClientPool(JsonlSink(tmp / "calls.jsonl.gz"), stub_factory=stub_factory, context=ctx)
    log = StudyLogger(tmp)
    names = assign_names(cfg.seed)
    name_role = {v: k for k, v in names.items()}
    suffix_keys = ["notice"] if arm["notice"] else []
    suffix = texts.rules_suffix(suffix_keys)
    order = cfg.resolved_order()
    t_start = time.time()

    record: Optional[str] = None
    offer: Optional[dict] = None
    results = []
    for g in range(1, cfg.n_games + 1):
        arrangement = order[g - 1]
        period = "pre" if g < cfg.offer_game else "post"
        by_role = {
            "S": StingPlayer(names["S"], cfg.voice_model(), pool.get(cfg.voice_model()), cfg.policy, rules_suffix=suffix),
            "T": TrackedPlayer(names["T"], cfg.model, "T", pool.get(cfg.model), rules_suffix=suffix),
            "O1": TrackedPlayer(names["O1"], cfg.model, "O1", pool.get(cfg.model), rules_suffix=suffix),
            "O2": TrackedPlayer(names["O2"], cfg.model, "O2", pool.get(cfg.model), rules_suffix=suffix),
        }
        for role, p in by_role.items():
            p.bullet_position = stream("revolver", cfg.seed, g, role).randrange(6)

        if g == cfg.offer_game:
            others = sorted(n for r, n in names.items() if r != "T")
            if arm["offer"]:
                offer = run_offer(pool.get(cfg.model), arm["offer"], target=names["T"], sting=names["S"],
                                  players=others, n_games=cfg.n_games, game=g, suffix_keys=suffix_keys,
                                  meta={"arm": cfg.arm})
                record = record_for_offer(offer)
            else:
                record = texts.record_text("null", sting=names["S"])
            log.event(dict(ctx, event="offer", game=g, offer_kind=arm["offer"],
                           reply=(offer or {}).get("reply"), decision_strict=(offer or {}).get("decision_strict"),
                           decision_zeng=(offer or {}).get("decision_zeng"), accepted=(offer or {}).get("accepted"),
                           record=record, prompt=(offer or {}).get("prompt")))
        if record is not None and g >= cfg.offer_game:
            by_role["T"].series_memory = record

        seats = [by_role[r] for r in ARRANGEMENTS[arrangement]]
        t0 = time.time()
        game = StingGame(seats, seed=cfg.seed, game_no=g, period=period, arrangement=arrangement,
                         policy=cfg.policy, logger=log, records_dir=tmp / "games", context=ctx,
                         max_rounds=cfg.max_rounds_per_game, reflect_workers=cfg.reflect_workers)
        game.start_game()
        alive = [p for p in game.players if p.alive]
        last = alive[0].name if len(alive) == 1 else None
        results.append(dict(game=g, arrangement=arrangement, period=period, rounds=game.round_count,
                            turns=game.turn_count, capped=game.capped, winner=game.game_record.winner,
                            winner_role=name_role.get(game.game_record.winner), last_survivor=last,
                            last_survivor_role=name_role.get(last),
                            scores_by_role={name_role[n]: s for n, s in game.scores.items()},
                            elimination_order=[name_role[n] for n in game.elimination_order],
                            shots=len(game.shots), duration_s=round(time.time() - t0, 1)))

    probes = []
    if cfg.probes:
        for role in ("T", "O1", "O2"):
            player = names[role]
            others = sorted(n for n in names.values() if n != player)
            rec = record if role == "T" else None
            summary = series_summary(results, player)
            res = run_suspicion(pool.get(cfg.model), player=player, role=role, others=others,
                                others_roles={n: name_role[n] for n in others}, n_games=cfg.n_games,
                                summary=summary, record=rec, suffix_keys=suffix_keys)
            probes.append(res)
            log.probe(dict(ctx, **res))
        if offer is not None:
            player = names["T"]
            others = sorted(n for n in names.values() if n != player)
            for variant in texts.INTERVIEW_VARIANTS:
                res = run_interview(pool.get(cfg.model), player=player, role="T", others=others,
                                    n_games=cfg.n_games, summary=series_summary(results, player), record=record,
                                    recorded_accept=offer["accepted"], variant=variant, suffix_keys=suffix_keys)
                probes.append(res)
                log.probe(dict(ctx, **res))

    meta = dict(study_version=STUDY_VERSION, seq_id=seq_id, config=cfg.to_dict(), names=names,
                offer=({k: v for k, v in offer.items() if k != "prompt"} if offer else None),
                record=record, games=results, client_stats=pool.stats(),
                cost_usd_estimate=round(sum(c["cost_usd_estimate"] for c in pool.stats()), 4),
                n_calls=sum(c["n_calls"] for c in pool.stats()),
                duration_s=round(time.time() - t_start, 1), stub=stub_factory is not None,
                git_commit=git_commit(), python=platform.python_version(),
                finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    (tmp / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    (tmp / "DONE").write_text("ok\n")
    if final.exists():
        shutil.rmtree(final)
    tmp.rename(final)
    return meta
