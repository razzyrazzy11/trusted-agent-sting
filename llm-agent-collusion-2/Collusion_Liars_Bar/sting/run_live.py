"""Stage L: live sequences, run in parallel processes (each sequence is independent, resumable,
and written atomically).

    python -m sting live --pilot                      # B0, B1, B3 x seeds 0-2 (go/no-go)
    python -m sting live                              # all arms at the pre-registered n (LIVE_N)
    python -m sting live --arms B1 B3 --seeds 0-14    # explicit
    python -m sting live --stub --pilot               # zero-cost dry run

Rate limits: total concurrency is roughly workers x (1 + reflect_workers) calls in flight.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import multiprocessing as mp
import os
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from .config import ARMS, LIVE_N, PILOT_ARMS, PILOT_SEEDS, PRIMARY_MODEL, SequenceConfig


def parse_seeds(spec: str):
    seeds = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            seeds.extend(range(int(a), int(b) + 1))
        elif part:
            seeds.append(int(part))
    return seeds


def _worker(arm, seed, model, out, stub, probes, reflect_workers):
    from .texts import LB_ROOT
    os.chdir(LB_ROOT)
    if str(LB_ROOT) not in sys.path:
        sys.path.insert(0, str(LB_ROOT))
    from .sequence import run_sequence
    from .stub import stub_factory
    log_dir = Path(out) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{arm}-{model}-s{seed:03d}.log"
    t0 = time.time()
    try:
        with open(log_path, "w", encoding="utf-8") as f, contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
            cfg = SequenceConfig(arm=arm, seed=seed, model=model, probes=probes, reflect_workers=reflect_workers)
            meta = run_sequence(cfg, Path(out), stub_factory=stub_factory(seed) if stub else None)
        return dict(arm=arm, seed=seed, ok=True, n_calls=meta["n_calls"], cost=meta["cost_usd_estimate"],
                    minutes=round((time.time() - t0) / 60, 1),
                    accepted=(meta.get("offer") or {}).get("accepted"))
    except Exception as e:  # noqa: BLE001
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        return dict(arm=arm, seed=seed, ok=False, error=f"{type(e).__name__}: {e}", log=str(log_path))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arms", nargs="+", default=list(ARMS))
    ap.add_argument("--seeds", default=None, help="e.g. 0-9 or 0,1,2 (default: pre-registered LIVE_N per arm)")
    ap.add_argument("--pilot", action="store_true", help=f"arms {PILOT_ARMS} x seeds {PILOT_SEEDS}")
    ap.add_argument("--model", default=PRIMARY_MODEL)
    ap.add_argument("--out", default=None, help="default: sting_runs/live (sting_runs_stub/... with --stub)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--reflect-workers", type=int, default=4)
    ap.add_argument("--no-probes", action="store_true")
    ap.add_argument("--stub", action="store_true", help="use the stub model (no API calls)")
    a = ap.parse_args(argv)
    if a.out is None:
        a.out = "sting_runs/live".replace("sting_runs/", "sting_runs_stub/") if a.stub else "sting_runs/live"
    if a.pilot:
        jobs = [(arm, s) for arm in PILOT_ARMS for s in PILOT_SEEDS]
    elif a.seeds:
        jobs = [(arm, s) for arm in a.arms for s in parse_seeds(a.seeds)]
    else:
        jobs = [(arm, s) for arm in a.arms for s in range(LIVE_N[arm])]
    # interleave arms so a partial run is balanced across arms
    jobs.sort(key=lambda j: (j[1], list(ARMS).index(j[0])))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    from .runinfo import keep_out_of_git
    keep_out_of_git(out)
    from .freeze import announce
    announce("L-pilot" if a.pilot else "L", stub=a.stub)
    from .client import prepare_backends
    prepare_backends([a.model], stub=a.stub)       # wake + verify the server once, before the workers
    print(f"{len(jobs)} sequences, model {a.model}, {a.workers} workers -> {out}", flush=True)
    ctx = mp.get_context("spawn")
    results = []
    with ProcessPoolExecutor(max_workers=a.workers, mp_context=ctx) as ex:
        futs = [ex.submit(_worker, arm, s, a.model, str(out), a.stub, not a.no_probes, a.reflect_workers)
                for arm, s in jobs]
        for f in as_completed(futs):
            r = f.result()
            results.append(r)
            if r["ok"]:
                print(f"done {r['arm']} seed {r['seed']}: {r['n_calls']} calls, ${r['cost']:.3f}, "
                      f"{r['minutes']} min, accepted={r['accepted']}", flush=True)
            else:
                print(f"FAILED {r['arm']} seed {r['seed']}: {r['error']} (see {r['log']})", flush=True)
    with open(out / "manifest.jsonl", "a", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(dict(r, model=a.model, finished=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))) + "\n")
    bad = [r for r in results if not r["ok"]]
    print(f"{len(results) - len(bad)} ok, {len(bad)} failed", flush=True)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
