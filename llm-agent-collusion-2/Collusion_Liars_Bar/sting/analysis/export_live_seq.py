"""Export the per-sequence live restraint rates behind the paper's Figure 2b (no model calls).

T's challenge rate on S's plays per sequence, before the offer (games 1-2) and after it (games 3-6),
computed with the same function and data as `python -m sting analyze` (analyze.seq_rates on the
preregistered live runs). The per-arm means are checked against the committed tables/live_rates.csv,
so the export cannot drift from the published analysis.

    python -m sting.analysis.export_live_seq --runs sting_runs

Writes sting_results/tables/live_seq_rates.csv (columns: arm, seq_id, period, accepted, rate, n).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from ..config import ARMS
from .analyze import seq_rates
from .load import load

SPEC = dict(dtype="challenge", counterpart_roles=["S"], outcome="challenged")


def export(runs: Path, out: Path) -> pd.DataFrame:
    data = load(runs)
    if data.seqs.empty or data.D.empty:
        raise SystemExit(f"no live data under {runs}")
    rows = []
    for period in ("pre", "post"):
        r = seq_rates(data, period=period, **SPEC)
        r = r[r["arm"].isin(list(ARMS))].copy()
        r["period"] = period
        rows.append(r[["arm", "seq_id", "period", "accepted", "rate", "n"]])
    df = pd.concat(rows, ignore_index=True).sort_values(["period", "arm", "seq_id"]).reset_index(drop=True)

    # tie the export to the committed analysis table
    committed = pd.read_csv(out / "tables" / "live_rates.csv")
    committed = committed[committed["measure"] == "restraint"].set_index(["period", "arm"])
    for (period, arm), g in df.groupby(["period", "arm"]):
        ref = committed.loc[(period, arm)]
        assert int(ref["n_seq"]) == len(g), (period, arm, int(ref["n_seq"]), len(g))
        assert abs(float(ref["mean_rate"]) - float(g["rate"].mean())) < 1e-9, (period, arm)
    df.to_csv(out / "tables" / "live_seq_rates.csv", index=False)
    return df


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", default="sting_runs")
    ap.add_argument("--out", default=None, help="default: sting_results (sting_results_stub for stub runs)")
    a = ap.parse_args(argv)
    out = Path(a.out or ("sting_results_stub" if "stub" in a.runs else "sting_results"))
    df = export(Path(a.runs), out)
    n = df.groupby(["period", "arm"]).size().unstack("arm")
    print(n.to_string())
    print(f"wrote {out / 'tables' / 'live_seq_rates.csv'} ({len(df)} rows); per-arm means match tables/live_rates.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
