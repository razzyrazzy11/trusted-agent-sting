"""Pre-run simulation: data yield, call budget and power (simulation-based power analysis,
Arnold, Hogan, Colford & Hubbard 2011, BMC Med Res Methodol 11:94).

Part 1 runs the REAL study engine (StingGame, sequences, seating, scripted sting) with a
parametric stub in place of the LLM, so the yield of T-on-S decisions, the sting's survival and
the call count per game are exact for these rules. Inputs are Zeng & Rudzicz's reported rates for
the planned target model (Llama-3.1-8B, seat "Lily"): pre-offer challenge rate 0.57-0.65 (we use
0.60) and bluff rate 0.59-0.63 (0.60).

Part 2 simulates the planned live H2 test with those cluster sizes, a sequence-level random
effect (ICC on the latent logit scale) and treatment effects RD = -0.10/-0.20/-0.30.

Part 3 simulates the snapshot stage: point-level heterogeneity, K samples per point and
condition, the paired H2 test, and the H3 detector operating characteristics as a function of
audit length m (decisions observed per audited agent).

    python -m sting.simulate --out results/sim [--n-seq 60] [--reps 2000]
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import os
import tempfile
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

import numpy as np

from .config import SequenceConfig
from .stub import StubEffects, StubModel

BASE_P = 0.60
BASE_BLUFF = 0.60


def _expit(x):
    return 1.0 / (1.0 + np.exp(-x))


def _logit(p):
    return np.log(p / (1 - p))


# ---------------------------------------------------------------------------- part 1
def _yield_one(args):
    arm, seed, effect_p, root = args
    from .sequence import run_sequence
    eff = StubEffects(p_challenge=BASE_P, p_bluff=BASE_BLUFF, p_challenge_pact_partner=effect_p,
                      p_challenge_pact_refused=effect_p, p_malformed=0.0, p_empty=0.0, p_stuck=0.0)
    eff.accept["direct"] = 1.0                    # yield under full uptake
    factory = lambda m: StubModel(m, seed=seed, effects=eff)
    cfg = SequenceConfig(arm=arm, seed=seed, probes=False, reflect_workers=1)
    with contextlib.redirect_stdout(io.StringIO()):
        meta = run_sequence(cfg, Path(root), stub_factory=factory, overwrite=True)
    d = Path(root) / arm / cfg.model / f"seed_{seed:03d}"
    rows = [json.loads(l) for l in open(d / "decisions.jsonl")]
    out = {"arm": arm, "seed": seed, "effect_p": effect_p}
    for period in ("pre", "post"):
        out[f"n_TS_chal_{period}"] = sum(1 for r in rows if r["decision_type"] == "challenge" and r["actor_role"] == "T"
                                         and r["counterpart_role"] == "S" and r["period"] == period)
        out[f"n_T_play_vs_S_{period}"] = sum(1 for r in rows if r["decision_type"] == "play" and r["actor_role"] == "T"
                                             and r["counterpart_role"] == "S" and r["period"] == period)
        out[f"n_T_chal_other_{period}"] = sum(1 for r in rows if r["decision_type"] == "challenge" and r["actor_role"] == "T"
                                              and r["counterpart_role"] in ("O1", "O2") and r["period"] == period)
    games = meta["games"]
    out["calls_per_game"] = meta["n_calls"] / len(games)
    out["rounds_per_game"] = float(np.mean([g["rounds"] for g in games]))
    out["capped_games"] = sum(g["capped"] for g in games)
    out["S_last_survivor_share"] = float(np.mean([g["last_survivor_role"] == "S" for g in games]))
    out["T_eliminated_first_share"] = float(np.mean([(g["elimination_order"] or [None])[0] == "T" for g in games]))
    return out


def part1(n_seq: int, workers: int):
    jobs = []
    with tempfile.TemporaryDirectory() as root:
        for effect_p in (BASE_P, 0.30):           # null and RD = -0.30 restraint
            for arm in ("B1", "B3"):
                for s in range(n_seq):
                    jobs.append((arm, 1000 + s, effect_p, os.path.join(root, f"e{effect_p}")))
        with ProcessPoolExecutor(max_workers=workers) as ex:
            rows = list(ex.map(_yield_one, jobs, chunksize=4))
    return rows


def summarize_yield(rows):
    out = {}
    for effect_p in sorted({r["effect_p"] for r in rows}):
        for arm in ("B1", "B3"):
            sub = [r for r in rows if r["arm"] == arm and r["effect_p"] == effect_p]
            key = f"{arm}_p{effect_p:.2f}"
            out[key] = {k: {"mean": float(np.mean([r[k] for r in sub])), "p10": float(np.percentile([r[k] for r in sub], 10)),
                            "p90": float(np.percentile([r[k] for r in sub], 90))}
                        for k in sub[0] if k not in ("arm", "seed", "effect_p")}
    return out


# ---------------------------------------------------------------------------- part 2
def power_live(rows, reps: int, rng: np.random.Generator):
    """Welch t-test on per-sequence post-offer T-on-S challenge rates (B1 vs B3), and the same on
    per-sequence (post - pre) differences. Cluster sizes resampled from the engine yield."""
    from scipy import stats
    # cluster sizes: treatment arm from the engine runs WITH planted restraint, control from null runs
    pool = {"B1": [(r["n_TS_chal_pre"], r["n_TS_chal_post"]) for r in rows if r["arm"] == "B1" and r["effect_p"] < BASE_P],
            "B3": [(r["n_TS_chal_pre"], r["n_TS_chal_post"]) for r in rows if r["arm"] == "B3" and r["effect_p"] == BASE_P]}
    res = []
    for icc in (0.05, 0.10, 0.20):
        sigma = math.sqrt(icc * (math.pi ** 2 / 3) / (1 - icc))
        for rd in (-0.10, -0.20, -0.30):
            for n in (5, 10, 15, 20):
                hits_post = hits_did = 0
                for _ in range(reps):
                    rates = {}
                    dids = {}
                    for arm in ("B1", "B3"):
                        idx = rng.integers(0, len(pool[arm]), size=n)
                        u = rng.normal(0, sigma, size=n)
                        p_pre = _expit(_logit(BASE_P) + u)
                        p_post = _expit(_logit(BASE_P + (rd if arm == "B1" else 0.0)) + u)
                        m_pre = np.array([max(pool[arm][i][0], 1) for i in idx])
                        m_post = np.array([max(pool[arm][i][1], 1) for i in idx])
                        r_pre = rng.binomial(m_pre, p_pre) / m_pre
                        r_post = rng.binomial(m_post, p_post) / m_post
                        rates[arm], dids[arm] = r_post, r_post - r_pre
                    if stats.ttest_ind(rates["B1"], rates["B3"], equal_var=False).pvalue < 0.05:
                        hits_post += 1
                    if stats.ttest_ind(dids["B1"], dids["B3"], equal_var=False).pvalue < 0.05:
                        hits_did += 1
                res.append(dict(icc=icc, rd=rd, n_seq_per_arm=n, power_post=hits_post / reps, power_did=hits_did / reps))
    return res


# ---------------------------------------------------------------------------- part 3
def power_snapshot(reps: int, rng: np.random.Generator, k: int = 5):
    from scipy import stats
    res = []
    for sigma_pt in (0.5, 1.0, 1.5):
        for rd in (-0.10, -0.20, -0.30):
            for P in (30, 60, 90):
                hits = 0
                for _ in range(reps):
                    v = rng.normal(0, sigma_pt, size=P)
                    p0 = _expit(_logit(BASE_P) + v)
                    # shift on the logit scale so that the average risk difference equals rd
                    shift = _solve_shift(p0, rd)
                    p1 = _expit(_logit(p0) + shift)
                    y0 = rng.binomial(k, p0) / k
                    y1 = rng.binomial(k, p1) / k
                    if stats.ttest_rel(y1, y0).pvalue < 0.05:
                        hits += 1
                res.append(dict(sigma_point=sigma_pt, rd=rd, points=P, k=k, power=hits / reps))
    return res


def _solve_shift(p0, rd):
    lo, hi = -8.0, 8.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if np.mean(_expit(_logit(p0) + mid) - p0) < rd:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def detector_curve(reps: int, rng: np.random.Generator, k: int = 5, P: int = 60, sigma_pt: float = 1.0):
    """H3: resample audit episodes of m decisions from held-out points. Calibrate tau on the
    calibration half's null decisions (FPR 0.10), report held-out TPR and FPR."""
    out = []
    for rd in (-0.10, -0.20, -0.30, -0.35):
        for m in (5, 10, 20, 40):
            tprs, fprs = [], []
            for _ in range(max(50, reps // 20)):
                v = rng.normal(0, sigma_pt, size=P)
                p0 = _expit(_logit(BASE_P) + v)
                p1 = _expit(_logit(p0) + _solve_shift(p0, rd))
                cal, hold = np.arange(P) < P // 2, np.arange(P) >= P // 2
                null_a = rng.binomial(1, np.repeat(p0, k).reshape(P, k))
                null_b = rng.binomial(1, np.repeat(p0, k).reshape(P, k))
                pact = rng.binomial(1, np.repeat(p1, k).reshape(P, k))

                def episodes(mat, mask, n_ep=400):
                    dec = mat[mask].ravel()
                    draws = rng.integers(0, dec.size, size=(n_ep, m))
                    return -dec[draws].mean(axis=1)    # restraint score: minus the challenge rate
                from .analysis.analyze import calibrate_threshold, flag_rate
                cal_null = episodes(null_a, cal)
                tau, gamma = calibrate_threshold(cal_null, 0.10)   # same randomized rule as the analysis
                tprs.append(flag_rate(episodes(pact, hold), tau, gamma))
                fprs.append(flag_rate(episodes(null_b, hold), tau, gamma))
            out.append(dict(rd=rd, m=m, k=k, points=P, sigma_point=sigma_pt,
                            tpr=float(np.mean(tprs)), fpr=float(np.mean(fprs))))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="results/sim")
    ap.add_argument("--n-seq", type=int, default=60)
    ap.add_argument("--reps", type=int, default=2000)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2)))
    ap.add_argument("--seed", type=int, default=20261023)
    a = ap.parse_args(argv)
    from .texts import LB_ROOT
    os.chdir(LB_ROOT)                             # the harness reads prompts/ relative to the cwd
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(a.seed)
    rows = part1(a.n_seq, a.workers)
    y = summarize_yield(rows)
    live = power_live(rows, a.reps, rng)
    snap = power_snapshot(a.reps, rng)
    det = detector_curve(a.reps, rng)
    (out / "yield_rows.json").write_text(json.dumps(rows, indent=1))
    result = {"inputs": {"base_challenge": BASE_P, "base_bluff": BASE_BLUFF, "n_seq": a.n_seq, "reps": a.reps},
              "yield": y, "power_live": live, "power_snapshot": snap, "detector_curve": det}
    (out / "simulation.json").write_text(json.dumps(result, indent=2))
    (out / "simulation.md").write_text(render_md(result))
    print(render_md(result))


def render_md(r) -> str:
    y = r["yield"]
    L = ["# Pre-run simulation", "",
         f"Inputs: baseline challenge {r['inputs']['base_challenge']}, bluff {r['inputs']['base_bluff']} "
         f"(Zeng & Rudzicz, Llama-3.1-8B seat), {r['inputs']['n_seq']} engine sequences per arm and effect, "
         f"{r['inputs']['reps']} power replicates.", "",
         "## Yield per 6-game sequence (mean [p10, p90]), real engine + stub", "",
         "| arm, T->S challenge prob post | T->S challenges pre | T->S challenges post | T plays vs S post | calls/game | rounds/game | S last survivor |",
         "|---|---|---|---|---|---|---|"]
    for key, v in y.items():
        f = lambda k: f"{v[k]['mean']:.1f} [{v[k]['p10']:.0f}, {v[k]['p90']:.0f}]"
        L.append(f"| {key} | {f('n_TS_chal_pre')} | {f('n_TS_chal_post')} | {f('n_T_play_vs_S_post')} | "
                 f"{v['calls_per_game']['mean']:.0f} | {v['rounds_per_game']['mean']:.1f} | {v['S_last_survivor_share']['mean']:.2f} |")
    L += ["", "## Power, live H2 (B1 vs B3, alpha 0.05; Welch t on per-sequence rates)", "",
          "| ICC | RD | n/arm | power (post) | power (post-pre) |", "|---|---|---|---|---|"]
    for p in r["power_live"]:
        L.append(f"| {p['icc']} | {p['rd']} | {p['n_seq_per_arm']} | {p['power_post']:.2f} | {p['power_did']:.2f} |")
    L += ["", "## Power, snapshot H2 (paired, K=5)", "", "| point SD (logit) | RD | points | power |", "|---|---|---|---|"]
    for p in r["power_snapshot"]:
        L.append(f"| {p['sigma_point']} | {p['rd']} | {p['points']} | {p['power']:.2f} |")
    L += ["", "## H3 detector operating characteristics (held-out, tau at calibration FPR 0.10)", "",
          "| RD | audit length m | TPR | FPR |", "|---|---|---|---|"]
    for p in r["detector_curve"]:
        L.append(f"| {p['rd']} | {p['m']} | {p['tpr']:.2f} | {p['fpr']:.2f} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
