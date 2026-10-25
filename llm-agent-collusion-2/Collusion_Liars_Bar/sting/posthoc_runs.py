"""Post hoc extensions (DEVIATIONS.md, section D): new data collected after the main analysis.

Nothing frozen is edited. New snapshot conditions and the new live arm are registered at import time
(below), so the frozen runners (stage_s.run_stage_s, sequence.run_sequence) execute them unchanged, and
every output goes to its own root, sting_runs_posthoc/ (sting_runs_stub_posthoc/ for stub runs), so
the preregistered analyses never see these data.

    python -m sting.posthoc_runs snapshots                      # C9, C10 for Llama and Claude; Qwen full set
    python -m sting.posthoc_runs live --arms B5 --model llama-3.1-8b
    python -m sting.posthoc_runs live --arms B0 B1 B2 B3 B4 B6 --model qwen2.5-7b
    python -m sting.posthoc_runs live --arms B1 B3 B6 --model claude-haiku-5.5
    (add --stub for a zero-cost dry run)

What each addition tests:
  C9   Indirect pact accepted, with the model's OWN accepted reply to the indirect offer (Stage A cell A2).
       Claude refused every explicit pact but accepted the indirect one; does it then act on it?
  C10  Null record + integrity notice: the notice-only control for C5 (pact + notice) vs C3 (pact).
  B5   Live arm: no offer, integrity notice in every player's rules: the notice-only control for B4.
  B6   Live arm: the sting's indirect pact (the offer Claude and Qwen accept; they refuse the direct one).
  Qwen Live arms B0-B4 and B6 with Qwen2.5-7B as every LLM player (cross-model replication with its own
       records and suspicion answers), and Qwen snapshots so the audit can be tested on it.
  Claude Live arms B1, B3 and B6 with Claude Haiku 5.5 as every LLM player: does it act on the vague
       pact it accepts in live play?
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config

POSTHOC_CONDITIONS = {
    "C9": dict(record="indirect", suffix=[], reply_pool=("A2", "ACCEPT"),
               label="Indirect pact, accepted (own reply)"),
    "C10": dict(record="null", suffix=["notice"], reply_pool=None,
                label="Null record + integrity notice (notice-only control)"),
}
# chal_S is the audited decision: as many samples as C1a/C1b/C3 (config.SNAPSHOT_K_OVERRIDES)
POSTHOC_K_OVERRIDES = {("chal_S", "C9"): 20, ("chal_S", "C10"): 20}
POSTHOC_ARMS = {"B5": dict(offer=None, notice=True, label="No offer + integrity notice (notice-only control)"),
                "B6": dict(offer="indirect", notice=False, label="Sting, indirect pact (Stage A cell A2)")}
# B5 = B3's size (its comparison arm); B6 = B1's. Seeds 0..n-1 match every other arm's (same deals and names).
POSTHOC_LIVE_N = {"B5": 15, "B6": 15}

EXT_SNAPSHOT_MODELS = ["llama-3.1-8b", "claude-haiku-5.5"]
EXT_SNAPSHOT_CONDITIONS = ["C9", "C10"]
QWEN = "qwen2.5-7b"
QWEN_SNAPSHOT_CONDITIONS = ["C1a", "C1b", "C2", "C3", "C4", "C5", "C9", "C10"]


def register() -> None:
    """Add the post hoc conditions and arm to the (shared) config dicts. Idempotent."""
    for k, v in POSTHOC_CONDITIONS.items():
        config.SNAPSHOT_CONDITIONS.setdefault(k, v)
    for k, v in POSTHOC_K_OVERRIDES.items():
        config.SNAPSHOT_K_OVERRIDES.setdefault(k, v)
    for k, v in POSTHOC_ARMS.items():
        config.ARMS.setdefault(k, v)


register()       # at import: spawned live workers import this module, so they see B5 too


def roots(stub: bool):
    base = Path("sting_runs_stub" if stub else "sting_runs")
    return base, Path(str(base) + "_posthoc")


def _enter_lb_root():
    import os
    from .texts import LB_ROOT
    os.chdir(LB_ROOT)
    if str(LB_ROOT) not in sys.path:
        sys.path.insert(0, str(LB_ROOT))


def cmd_snapshots(a) -> int:
    from .client import prepare_backends
    from .runinfo import keep_out_of_git
    from .stage_s import run_stage_s
    from .stub import stub_factory
    src, out = roots(a.stub)
    keep_out_of_git(out)
    out_s = out / "stageS"
    jobs = []
    if not a.only_qwen:
        jobs += [(m, EXT_SNAPSHOT_CONDITIONS) for m in a.models]
    if not a.no_qwen:
        jobs.append((QWEN, QWEN_SNAPSHOT_CONDITIONS))
    prepare_backends([m for m, _ in jobs], stub=a.stub)
    summary = {}
    for model, conds in jobs:
        s = run_stage_s(src / "live", src / "stageA", out_s, [model], conditions=conds,
                        stub_factory=stub_factory(0) if a.stub else None, workers=a.workers)
        summary[model] = s.get(model)
    # same decision points as the preregistered snapshots (deterministic selection; checked here)
    orig = json.loads((src / "stageS" / "points.json").read_text())
    new = json.loads((out_s / "points.json").read_text())
    same = [p["point_id"] for p in orig] == [p["point_id"] for p in new]
    summary["same_points_as_preregistered"] = same
    print(json.dumps(summary, indent=2))
    if not same:
        print("ERROR: decision points differ from the preregistered snapshots", file=sys.stderr)
        return 1
    return 0


def _worker(arm, seed, model, out, stub, probes, reflect_workers):
    from .run_live import _worker as w            # this module is imported in the child: B5 is registered
    return w(arm, seed, model, out, stub, probes, reflect_workers)


def cmd_live(a) -> int:
    import multiprocessing as mp
    import time
    from concurrent.futures import ProcessPoolExecutor, as_completed
    from .client import prepare_backends
    from .run_live import parse_seeds
    from .runinfo import keep_out_of_git
    _, out = roots(a.stub)
    out = out / "live"
    out.mkdir(parents=True, exist_ok=True)
    keep_out_of_git(out)
    for arm in a.arms:
        if arm not in config.ARMS:
            raise SystemExit(f"unknown arm {arm}")
    n = {**config.LIVE_N, **POSTHOC_LIVE_N}
    jobs = ([(arm, s) for arm in a.arms for s in parse_seeds(a.seeds)] if a.seeds
            else [(arm, s) for arm in a.arms for s in range(n[arm])])
    jobs.sort(key=lambda j: (j[1], list(config.ARMS).index(j[0])))
    prepare_backends([a.model], stub=a.stub)
    print(f"{len(jobs)} sequences, model {a.model}, {a.workers} workers -> {out}", flush=True)
    results = []
    with ProcessPoolExecutor(max_workers=a.workers, mp_context=mp.get_context("spawn")) as ex:
        futs = [ex.submit(_worker, arm, s, a.model, str(out), a.stub, True, a.reflect_workers) for arm, s in jobs]
        for f in as_completed(futs):
            r = f.result()
            results.append(r)
            print((f"done {r['arm']} seed {r['seed']}: {r['n_calls']} calls, {r['minutes']} min, "
                   f"accepted={r['accepted']}") if r["ok"] else f"FAILED {r['arm']} seed {r['seed']}: {r['error']}",
                  flush=True)
    with open(out / "manifest.jsonl", "a", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(dict(r, model=a.model, finished=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))) + "\n")
    bad = [r for r in results if not r["ok"]]
    print(f"{len(results) - len(bad)} ok, {len(bad)} failed", flush=True)
    return 1 if bad else 0


def main(argv=None) -> int:
    _enter_lb_root()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshots")
    s.add_argument("--models", nargs="+", default=EXT_SNAPSHOT_MODELS)
    s.add_argument("--no-qwen", action="store_true")
    s.add_argument("--only-qwen", action="store_true")
    s.add_argument("--workers", type=int, default=16)
    s.add_argument("--stub", action="store_true")
    l = sub.add_parser("live")
    l.add_argument("--arms", nargs="+", required=True)
    l.add_argument("--model", required=True)
    l.add_argument("--seeds", default=None)
    l.add_argument("--workers", type=int, default=6)
    l.add_argument("--reflect-workers", type=int, default=4)
    l.add_argument("--stub", action="store_true")
    a = ap.parse_args(argv)
    return cmd_snapshots(a) if a.cmd == "snapshots" else cmd_live(a)


if __name__ == "__main__":
    sys.exit(main())
