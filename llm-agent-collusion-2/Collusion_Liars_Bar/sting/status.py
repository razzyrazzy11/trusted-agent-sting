"""Progress of every stage: python -m sting status [--runs sting_runs]"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .config import ARMS, LIVE_N, SNAPSHOT_CONDITIONS, STAGE_A_BATCHES, STAGE_A_CELLS, stage_a_per_batch


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="sting_runs")
    a = ap.parse_args(argv)
    runs = Path(a.runs)
    print("== Stage A")
    for d in sorted((runs / "stageA").glob("*")):
        f = d / "responses.jsonl"
        target_a = len(STAGE_A_CELLS) * STAGE_A_BATCHES * stage_a_per_batch(d.name)
        if f.exists():
            rows = [json.loads(l) for l in open(f, encoding="utf-8")]
            acc = sum(r["decision_strict"] == "ACCEPT" for r in rows)
            print(f"  {d.name:14s} {len(rows):5d}/{target_a}  accepted {acc}")
    print("== Stage L (target per arm: " + ", ".join(f"{k} {v}" for k, v in LIVE_N.items()) + ")")
    done = Counter()
    tmp = Counter()
    cost = 0.0
    for arm in ARMS:
        for d in sorted((runs / "live" / arm).glob("*/seed_*")):
            if d.name.endswith(".tmp"):
                tmp[arm] += 1
            elif (d / "DONE").exists():
                done[arm] += 1
                cost += json.loads((d / "meta.json").read_text())["cost_usd_estimate"]
    for arm in ARMS:
        print(f"  {arm}: {done[arm]:3d}/{LIVE_N[arm]} done" + (f", {tmp[arm]} in progress/crashed" if tmp[arm] else ""))
    print(f"  live cost so far (est.): ${cost:.2f}")
    print("== Stage S")
    for d in sorted((runs / "stageS").glob("*")):
        f = d / "responses.jsonl"
        if f.exists():
            n = sum(1 for _ in open(f, encoding="utf-8"))
            print(f"  {d.name:14s} {n} samples ({len(SNAPSHOT_CONDITIONS)} conditions)")
    ck = runs / "checkpoint.json"
    if ck.exists():
        print(f"== Checkpoint: {json.loads(ck.read_text())['verdict']}")


if __name__ == "__main__":
    main()
