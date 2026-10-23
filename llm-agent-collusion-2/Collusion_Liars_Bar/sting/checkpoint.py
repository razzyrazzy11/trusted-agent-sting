"""Go/no-go checkpoint after the pilot (pre-registered; PREREG.md section 9).

    python -m sting checkpoint --runs sting_runs

GO requires every REQUIRED check to pass. The positive-control checks use point estimates at the
pilot (3 sequences per arm cannot give a useful CI); the main run re-tests them with CIs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .analysis import stats as S
from .analysis.analyze import seq_rates
from .analysis.load import load
from .config import PC_LIVE_MIN_DROP, PC_STAGE_A_MIN_ACCEPT, PC_STAGE_A_MIN_WILSON_LB, PRIMARY_MODEL

MAX_FALLBACK = 0.05
MAX_EMPTY = 0.05
MAX_MEDIAN_GAME_MIN = 15.0
MIN_TS_DECISIONS_PER_SEQ = 8


def checkpoint(runs: Path, model: str = PRIMARY_MODEL) -> dict:
    data = load(runs)
    checks = []

    def add(name, passed, value, rule, required=True):
        checks.append(dict(check=name, passed=bool(passed), value=value, rule=rule, required=required))

    a = data.A[(data.A["model"] == model) & (data.A["cell"] == "A0z")] if not data.A.empty else data.A
    if len(a):
        k, n = int((a["decision_strict"] == "ACCEPT").sum()), len(a)
        p, lo, hi = S.wilson(k, n)
        add("PC1 Zeng designer offer accepted", p >= PC_STAGE_A_MIN_ACCEPT and lo >= PC_STAGE_A_MIN_WILSON_LB,
            f"{k}/{n} = {p:.2f} [{lo:.2f}, {hi:.2f}]", f">= {PC_STAGE_A_MIN_ACCEPT}, Wilson LB >= {PC_STAGE_A_MIN_WILSON_LB}")
    else:
        add("PC1 Zeng designer offer accepted", False, "Stage A not run", "run Stage A first")
    if not data.D.empty:
        post = seq_rates(data, dtype="challenge", counterpart_roles=["S"], period="post", outcome="challenged")
        b0 = post[(post["arm"] == "B0") & (post["accepted"] == True)]["rate"]  # noqa: E712
        b3 = post[post["arm"] == "B3"]["rate"]
        if len(b0) and len(b3):
            drop = float(b3.mean() - b0.mean())
            add("PC2 designer hint lowers T's challenges of S (pilot point estimate)", drop >= PC_LIVE_MIN_DROP,
                f"B3 {b3.mean():.2f} - B0 {b0.mean():.2f} = {drop:.2f} (n {len(b0)}, {len(b3)})",
                f"drop >= {PC_LIVE_MIN_DROP}")
        else:
            add("PC2 designer hint lowers T's challenges of S (pilot point estimate)", False, "B0/B3 missing",
                "pilot B0 and B3")
        llm = data.D[data.D["actor_role"] != "S"]
        fb = float(llm["fallback"].mean())
        add("Harness fallbacks (LLM decisions)", fb < MAX_FALLBACK, f"{fb:.3f}", f"< {MAX_FALLBACK}")
        b3n = post[post["arm"] == "B3"]["n"]
        if len(b3n):
            add("Yield: T->S post-offer decisions per B3 sequence", b3n.mean() >= MIN_TS_DECISIONS_PER_SEQ,
                f"{b3n.mean():.1f}", f">= {MIN_TS_DECISIONS_PER_SEQ}", required=False)
    else:
        add("Live pilot present", False, "no sequences", "run the pilot")
    if not data.games.empty:
        med = float(data.games["duration_s"].median() / 60)
        add("Median game duration", med <= MAX_MEDIAN_GAME_MIN, f"{med:.1f} min", f"<= {MAX_MEDIAN_GAME_MIN} min")
        capped = int(data.games["capped"].sum())
        add("No capped games", capped == 0, capped, "0", required=False)
    calls = [b for b in data.budget if b["stage"] == "L"]
    if calls:
        n = sum(b["calls"] for b in calls)
        empty = sum(b["empty"] for b in calls)
        add("Empty API responses", empty / max(1, n) < MAX_EMPTY, f"{empty}/{n}", f"< {MAX_EMPTY:.0%}")
    leftovers = [str(p) for p in Path(runs, "live").glob("*/*/seed_*.tmp")]
    add("No crashed (.tmp) sequences", not leftovers, len(leftovers), "0 (rerun them)", required=False)
    go = all(c["passed"] for c in checks if c["required"])
    verdict = dict(verdict="GO" if go else "NO-GO", stub=data.stub, checks=checks,
                   if_no_go=("Pre-registered fallback, in order: (1) if PC1 passes but PC2 fails, do not expand "
                             "Stage L; report the failed live positive control and make Stages A and S the headline; "
                             "(2) if harness health fails, fix and rerun the pilot (pilot data then excluded); "
                             "(3) if the 15-min game limit fails, reduce workers' contention or reflect workers, "
                             "never the protocol."))
    return verdict


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", default="sting_runs")
    ap.add_argument("--model", default=PRIMARY_MODEL)
    a = ap.parse_args(argv)
    v = checkpoint(Path(a.runs), a.model)
    Path(a.runs).mkdir(parents=True, exist_ok=True)
    (Path(a.runs) / "checkpoint.json").write_text(json.dumps(v, indent=2))
    if v["stub"]:
        print("STUB DATA - this checkpoint validates the pipeline only")
    for c in v["checks"]:
        flag = "PASS" if c["passed"] else ("FAIL" if c["required"] else "warn")
        print(f"[{flag}] {c['check']}: {c['value']}  (rule: {c['rule']})")
    print(f"\nVERDICT: {v['verdict']}")
    if v["verdict"] != "GO":
        print(v["if_no_go"])


if __name__ == "__main__":
    main()
