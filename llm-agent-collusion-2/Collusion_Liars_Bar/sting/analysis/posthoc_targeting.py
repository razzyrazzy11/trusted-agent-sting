"""Exploratory follow-ups to the post hoc extensions, requested by reviewers (not in any logged plan;
reported as exploratory). No model calls.

    python -m sting.analysis.posthoc_targeting --runs sting_runs

1. Targeting: is a target's restraint aimed at S? Per sequence, post-offer challenge rate on S minus
   challenge rate on O1/O2 ("targeting"); contrasts against B3 (no offer).
2. Change from baseline: per sequence, post-offer minus pre-offer challenge rate on S, so subgroups that
   already differed before the offer (e.g. refusers) are compared on their change; contrasts against B3.
3. Small-sample intervals: every contrast reports the cluster-bootstrap CI and a Welch CI.
Groups: arm x {all, accepted, refused}; models Llama (preregistered runs + B5), Qwen, Claude.
Outputs: sting_results/posthoc_ext/targeting.csv (group summaries), targeting_contrasts.csv.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as st

from .. import posthoc_runs as PR  # noqa: F401  (registers B5, B6)
from ..config import ANALYSIS_SEED
from . import stats as S
from .analyze import seq_rates
from .load import load
from .posthoc_extend import CLAUDE, LLAMA, QWEN, _concat, _only

REPS = 10_000


def welch_ci(t, c, alpha=0.05):
    t, c = np.asarray(t, float), np.asarray(c, float)
    if t.size < 2 or c.size < 2:
        return float("nan"), float("nan")
    vt, vc = t.var(ddof=1) / t.size, c.var(ddof=1) / c.size
    se = math.sqrt(vt + vc)
    if se == 0:
        d = t.mean() - c.mean()
        return d, d
    df = (vt + vc) ** 2 / ((vt ** 2) / (t.size - 1) + (vc ** 2) / (c.size - 1))
    q = st.t.ppf(1 - alpha / 2, df)
    d = t.mean() - c.mean()
    return float(d - q * se), float(d + q * se)


def per_sequence(data) -> pd.DataFrame:
    def r(period, roles):
        x = seq_rates(data, dtype="challenge", counterpart_roles=roles, period=period, outcome="challenged")
        return x.set_index("seq_id")
    postS, preS, postO = r("post", ["S"]), r("pre", ["S"]), r("post", ["O1", "O2"])
    df = postS[["arm", "accepted", "rate"]].rename(columns={"rate": "post_S"})
    df["pre_S"] = preS["rate"].reindex(df.index)
    df["post_O"] = postO["rate"].reindex(df.index)
    df["targeting"] = df["post_S"] - df["post_O"]
    df["change"] = df["post_S"] - df["pre_S"]
    return df.reset_index()


def groups(df):
    for arm in sorted(df["arm"].unique()):
        a = df[df["arm"] == arm]
        yield arm, "all", a
        if a["accepted"].notna().any():
            for lab, v in (("accepted", True), ("refused", False)):
                g = a[a["accepted"] == v]
                if len(g):
                    yield arm, lab, g


def analyse(model, data, rng):
    df = per_sequence(data)
    summ, cons = [], []
    b3 = df[df["arm"] == "B3"]
    for arm, lab, g in groups(df):
        summ.append(dict(model=model, arm=arm, group=lab, n=len(g), n_pre=int(g["pre_S"].notna().sum()),
                         post_S=g["post_S"].mean(), pre_S=g["pre_S"].mean(), post_O=g["post_O"].mean(),
                         targeting=g["targeting"].mean(), change=g["change"].mean()))
        if arm == "B3":
            continue
        for meas in ("post_S", "targeting", "change"):
            t, c = g[meas].dropna().values, b3[meas].dropna().values
            res = S.two_arm_cluster_rates(t, c, REPS, rng)
            lo, hi = welch_ci(t, c)
            cons.append(dict(model=model, arm=arm, group=lab, measure=meas, **res, welch_lo=lo, welch_hi=hi))
    return pd.DataFrame(summ), pd.DataFrame(cons)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", default="sting_runs")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    runs = Path(a.runs)
    d0, de = load(runs), load(Path(str(runs) + "_posthoc"))
    stub = bool(d0.stub or de.stub)
    out = Path(a.out or ("sting_results_stub" if stub else "sting_results")) / "posthoc_ext"
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(ANALYSIS_SEED + 13)
    S_all, C_all = [], []
    for model, data in ((LLAMA, _concat(d0, de, LLAMA)), (QWEN, _only(de, QWEN)), (CLAUDE, _only(de, CLAUDE))):
        if data.seqs.empty:
            continue
        s, c = analyse(model, data, rng)
        S_all.append(s), C_all.append(c)
    summ, cons = pd.concat(S_all, ignore_index=True), pd.concat(C_all, ignore_index=True)
    summ.to_csv(out / "targeting.csv", index=False)
    cons.to_csv(out / "targeting_contrasts.csv", index=False)
    from .posthoc_gaps import _md
    print("# Exploratory: targeting and change from baseline" + (" (STUB)" if stub else ""))
    print(_md(summ.round(3)))
    print()
    print(_md(cons[["model", "arm", "group", "measure", "n_t", "n_c", "estimate", "ci_low", "ci_high",
                    "welch_lo", "welch_hi", "p_welch"]].round(3)))


if __name__ == "__main__":
    main()
