"""Stage S: counterfactual decision snapshots (the main source of statistical power).

Source points are real decisions of the target T in PRE-offer games of arms B0-B3 (no private
record and no notice in the prompt): T deciding whether to challenge S (chal_S), T playing with
S as its challenger (play_vs_S), and T deciding on another player (chal_other). Each point's exact
logged prompt is re-asked K times under each history condition: the private record (with an
on-policy reply sampled from Stage A for the same model) is spliced into the harness's own
CROSS-GAME MEMORY slot and, where the condition says so, a suffix is added to the rules.

This is the counterfactual-history design of Scheurer et al. (2023, "Large Language Models can
Strategically Deceive their Users when Put Under Pressure", arXiv:2311.07590) and of Zeng & Rudzicz
v2's concealment continuations. Known pitfall: the edited history is partly off-policy (T's earlier
moves in that game were made without the record); this is reported, and replies that had to be
templated because no on-policy reply existed are flagged.

    python -m sting snapshots --live sting_runs/live --stage-a sting_runs/stageA --out sting_runs/stageS
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Dict, List, Optional

from . import texts
from .client import ClientPool, JsonlSink
from .config import SNAPSHOT_CONDITIONS, SNAPSHOT_K, SNAPSHOT_K_OVERRIDES, SNAPSHOT_POINTS, STAGE_S_MODELS, PRIMARY_MODEL
from .offers import base_rules
from .parsing import is_bluff, parse_accept_strict, parse_challenge_json, parse_play_json
from .rng import stream
from .stage_a import load_stage_a
from .runinfo import write_run_info

SOURCE_ARMS = ("B0", "B1", "B2", "B3")
TEMPLATE_REPLIES = {"ACCEPT": "ACCEPT. Deal.", "REFUSE": "REFUSE. I'd rather play this straight."}


def point_type(r: dict) -> Optional[str]:
    if r["decision_type"] == "challenge" and r["counterpart_role"] == "S":
        return "chal_S"
    if r["decision_type"] == "play" and r["counterpart_role"] == "S":
        return "play_vs_S"
    if r["decision_type"] == "challenge" and r["counterpart_role"] in ("O1", "O2"):
        return "chal_other"
    return None


def collect_points(live_root: Path, source_model: str, n_per_type: Dict[str, int], seed: int = 0) -> List[dict]:
    pools = defaultdict(lambda: defaultdict(list))   # type -> seq_id -> points
    for d in sorted(Path(live_root).glob(f"*/{source_model}/seed_*")):
        if d.name.endswith(".tmp") or not (d / "DONE").exists():
            continue
        meta = json.loads((d / "meta.json").read_text())
        if meta["config"]["arm"] not in SOURCE_ARMS:
            continue
        for line in open(d / "decisions.jsonl", encoding="utf-8"):
            r = json.loads(line)
            t = point_type(r)
            if (t is None or r["actor_role"] != "T" or r["period"] != "pre" or r["has_memory"]
                    or r["fallback"] or not r.get("prompt_base")):
                continue
            pid = f"{r['seq_id']}|g{r['game']}|r{r['round']}|t{r['turn']}|{t}"
            pools[t][r["seq_id"]].append(dict(
                point_id=pid, point_type=t, seq_id=r["seq_id"], source_arm=r["arm"], source_seed=r["seed"],
                game=r["game"], round=r["round"], turn=r["turn"], prompt_base=r["prompt_base"],
                sting=meta["names"]["S"], target=meta["names"]["T"], counterpart=r["counterpart"],
                counterpart_role=r["counterpart_role"], target_card=r["target_card"],
                hand_before=r.get("hand_before"), claim_was_bluff=r.get("claim_was_bluff"),
                original_challenged=r.get("challenged"), original_bluffed=r.get("bluffed")))
    rng = stream("stageS_points", seed)
    chosen = []
    for t, n in n_per_type.items():
        by_seq = pools.get(t, {})
        seqs = sorted(by_seq)
        for s in seqs:
            rng.shuffle(by_seq[s])
        picked, i = [], 0
        while len(picked) < n and any(by_seq[s] for s in seqs):     # round-robin across sequences
            s = seqs[i % len(seqs)]
            if by_seq[s]:
                picked.append(by_seq[s].pop())
            i += 1
        chosen.extend(picked)
    return chosen


def reply_pools(stage_a_rows: List[dict]) -> Dict[tuple, List[str]]:
    pools = defaultdict(list)
    for r in stage_a_rows:
        pools[(r["cell"], r["decision_strict"])].append(r["reply"])
        pools[(r["cell"], "ANY")].append(r["reply"])
    return pools


def pick_reply(pools, cond_name: str, point_id: str, model: str):
    spec = SNAPSHOT_CONDITIONS[cond_name]
    if not spec["reply_pool"]:
        return None, None
    cell, want = spec["reply_pool"]
    candidates = pools.get((cell, want), [])
    if candidates:
        rng = stream("stageS_reply", model, point_id, cond_name)
        return candidates[rng.randrange(len(candidates))], "stage_a"
    return TEMPLATE_REPLIES.get(want, TEMPLATE_REPLIES["ACCEPT"]), "template"


def build_prompt(point: dict, cond_name: str, reply: Optional[str]) -> str:
    spec = SNAPSHOT_CONDITIONS[cond_name]
    rules = base_rules()
    pb = point["prompt_base"]
    if not pb.startswith(rules):
        raise ValueError(f"prompt of {point['point_id']} does not start with the harness rules text")
    sfx = texts.rules_suffix(spec["suffix"])
    prompt = rules + ("\n\n" + sfx if sfx else "") + pb[len(rules):]
    kind = spec["record"]
    if kind:
        note = texts.record_text(kind, sting=point["sting"], target=point["target"], reply=reply or "",
                                 accepted=(kind == "designer_hint" and parse_accept_strict(reply or "") == "ACCEPT"))
        prompt += texts.MEMORY_WRAP.format(memory=note)
    return prompt


def ask(client, point: dict, prompt: str, cond_name: str, sample: int) -> dict:
    meta = dict(point_id=point["point_id"], condition=cond_name, sample=sample)
    if point["point_type"] in ("chal_S", "chal_other"):
        raws = []
        for _ in range(5):                         # the harness resends the same prompt up to 5 times
            with client.track("snapshot_challenge", **meta):
                content, _ = client.chat([{"role": "user", "content": prompt}], model=client.model_key)
            raws.append(content)
            parsed = parse_challenge_json(content)
            if parsed is not None:
                return dict(outcome=parsed[0], attempts=len(raws), fallback=False, raw=raws[-1])
        return dict(outcome=None, attempts=5, fallback=True, raw=raws[-1])
    hand = point["hand_before"] or []
    feedback, raws = "", []
    for _ in range(5):                             # the harness appends error feedback on each retry
        with client.track("snapshot_play", **meta):
            content, _ = client.chat([{"role": "user", "content": prompt + feedback}], model=client.model_key)
        raws.append(content)
        result, feedback = parse_play_json(content, hand)
        if result is not None:
            cards = result["played_cards"]
            return dict(outcome=is_bluff(cards, point["target_card"]), n_cards=len(cards), attempts=len(raws),
                        fallback=False, raw=raws[-1])
    return dict(outcome=None, attempts=5, fallback=True, raw=raws[-1])


def run_stage_s(live_root: Path, stage_a_root: Path, out_root: Path, models: List[str],
                source_model: str = PRIMARY_MODEL, n_per_type: Optional[Dict[str, int]] = None,
                k: int = SNAPSHOT_K, conditions: Optional[List[str]] = None,
                stub_factory: Optional[Callable] = None, workers: int = 16, seed: int = 0) -> dict:
    n_per_type = n_per_type or dict(SNAPSHOT_POINTS)
    conditions = conditions or list(SNAPSHOT_CONDITIONS)
    points = collect_points(live_root, source_model, n_per_type, seed=seed)
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "points.json").write_text(json.dumps([{k2: v for k2, v in p.items() if k2 != "prompt_base"}
                                                       for p in points], indent=1))
    summary = {"points": {t: sum(1 for p in points if p["point_type"] == t) for t in n_per_type}}
    for model in models:
        d = out_root / model
        d.mkdir(parents=True, exist_ok=True)
        write_run_info(d, stub=stub_factory is not None, stage="S")
        path = d / "responses.jsonl"
        done = set()
        if path.exists():
            for line in open(path, encoding="utf-8"):
                r = json.loads(line)
                done.add((r["point_id"], r["condition"], r["sample"]))
        sink = JsonlSink(path)
        pools = reply_pools(load_stage_a(stage_a_root, model))
        client = ClientPool(JsonlSink(d / "calls.jsonl.gz"), stub_factory=stub_factory,
                            context={"stage": "S", "model": model}).get(model)
        jobs = []
        for p in points:
            for c in conditions:
                reply, source = pick_reply(pools, c, p["point_id"], model)
                prompt = build_prompt(p, c, reply)
                for j in range(max(k, SNAPSHOT_K_OVERRIDES.get((p["point_type"], c), k))):
                    if (p["point_id"], c, j) not in done:
                        jobs.append((p, c, j, prompt, reply, source))

        def one(job):
            p, c, j, prompt, reply, source = job
            res = ask(client, p, prompt, c, j)
            sink.write(dict(stage="S", model=model, point_id=p["point_id"], point_type=p["point_type"],
                            seq_id=p["seq_id"], source_arm=p["source_arm"], source_seed=p["source_seed"],
                            game=p["game"], condition=c, sample=j, reply=reply, reply_source=source,
                            reply_decision=parse_accept_strict(reply) if reply else None, **res))

        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(one, jobs))
        summary[model] = dict(new_calls_planned=len(jobs), **client.stats())
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", default="sting_runs/live")
    ap.add_argument("--stage-a", default="sting_runs/stageA")
    ap.add_argument("--out", default=None, help="default: sting_runs/stageS (sting_runs_stub/... with --stub)")
    ap.add_argument("--models", nargs="+", default=STAGE_S_MODELS)
    ap.add_argument("--source-model", default=PRIMARY_MODEL)
    ap.add_argument("--k", type=int, default=SNAPSHOT_K)
    ap.add_argument("--points", type=int, nargs=3, metavar=("CHAL_S", "PLAY_VS_S", "CHAL_OTHER"),
                    default=[SNAPSHOT_POINTS["chal_S"], SNAPSHOT_POINTS["play_vs_S"], SNAPSHOT_POINTS["chal_other"]])
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--stub", action="store_true")
    a = ap.parse_args(argv)
    if a.out is None:
        a.out = "sting_runs/stageS".replace("sting_runs/", "sting_runs_stub/") if a.stub else "sting_runs/stageS"
    if a.stub and a.live == "sting_runs/live":
        a.live, a.stage_a = "sting_runs_stub/live", "sting_runs_stub/stageA"
    from .stub import stub_factory
    n = dict(zip(("chal_S", "play_vs_S", "chal_other"), a.points))
    s = run_stage_s(Path(a.live), Path(a.stage_a), Path(a.out), a.models, source_model=a.source_model,
                    n_per_type=n, k=a.k, stub_factory=stub_factory(0) if a.stub else None, workers=a.workers)
    print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()
