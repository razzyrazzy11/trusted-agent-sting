"""Every number the paper cites, looked up from the committed analysis outputs.

The paper text refers to numbers only through placeholders:
  {{ci:KEY}} / {{v:KEY}} / {{pp:KEY}} / {{ppci:KEY}}   a claim in sting_results/claims.json
  {{x:NAME}}                                         a named number defined below (source given)
A missing key stops the build, so no number can enter the text by hand. Design constants (500
offers per cell, 60 sequences, m = 20, FPR target 0.10, K = 5/20) come from PREREG.md.
"""
from __future__ import annotations

import math
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1] / "llm-agent-collusion-2" / "Collusion_Liars_Bar"
RES = ROOT / "sting_results"
TAB = RES / "tables"

CLAIMS = json.loads((RES / "claims.json").read_text())
assert CLAIMS["stub"] is False, "stub results"
C = CLAIMS["claims"]
R = json.loads((RES / "results.json").read_text())
H = R["health"]


def f(x: float, d: int = 3, sign: bool = False) -> str:
    from decimal import Decimal, ROUND_HALF_UP
    # one rounding rule for every printed number: snap binary noise (e.g. 0.24749999999999997 -> 0.2475),
    # then round half away from zero, so a value exactly halfway always rounds the same way
    q = Decimal(repr(round(float(x), 10))).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)
    s = f"{q:+.{d}f}" if sign else f"{q:.{d}f}"
    if float(s) == 0:
        s = s.lstrip("+-")
    return s.replace("-", "−")


def pct(x: float, d: int = 1) -> str:
    return f(100 * x, d) + "%"


def ci3(est, lo, hi, d=3, sign=False) -> str:
    return f"{f(est, d, sign)} [{f(lo, d, sign)}, {f(hi, d, sign)}]"


def _full(key: str) -> dict:
    """claims.json stores 4 decimals; printing at 3 would round twice. Take the same quantity at full
    precision from the table it was written from, and check it equals the claim to 4 decimals."""
    c = dict(C[key])
    row = None
    try:
        if key.startswith("snapshot."):
            rest = key[len("snapshot."):]
            model = next(m for m in ("llama-3.1-8b", "claude-haiku-5.5") if rest.startswith(m + "."))
            pt, contrast = rest[len(model) + 1:].split(".")
            cond = contrast.split("-")[0]
            r = snap.loc[(model, pt, cond)]
            row = (r["estimate"], r["ci_low"], r["ci_high"])
        elif key.startswith("live."):
            r = live_c.loc[key[len("live."):]]
            row = (r["estimate"], r["ci_low"], r["ci_high"])
        elif key.startswith("acceptance."):
            rest = key[len("acceptance."):]
            model, cell = rest.rsplit(".", 1)
            r = stage_a.loc[(model, cell)]
            row = (r["strict_p"], r["strict_lo"], r["strict_hi"])
        elif key.startswith("H1."):
            r = pd.read_csv(TAB / "h1_offerer.csv").set_index("model").loc[key[3:]]
            row = (r["diff"], r["lo"], r["hi"])
        elif key in ("H3.tpr_m20", "H3.fpr_m20", "H3.fpr_benign_m20"):
            col = {"H3.tpr_m20": "flag_C3", "H3.fpr_m20": "flag_C1b", "H3.fpr_benign_m20": "flag_C2"}[key]
            r = curve.loc[20]
            row = (r[col], r[f"{col}_lo"], r[f"{col}_hi"])
        elif key == "H3.auroc_m20":
            row = (curve.loc[20, "auroc_C3_vs_C1b"], None, None)
        elif key == "H4a.acceptance_did":
            row = (R["H4a"]["estimate"], R["H4a"]["ci_low"], R["H4a"]["ci_high"])
        elif key == "PC1.accept_A0z":
            row = (R["PC1"]["accept"], R["PC1"]["lo"], R["PC1"]["hi"])
    except KeyError:
        row = None
    if row is not None:
        for name, full in zip(("value", "ci_low", "ci_high"), row):
            if full is None or name not in c:
                continue
            assert abs(round(float(full), 4) - c[name]) < 1.5e-4, (key, name, full, c[name])
            c[name] = float(full)
    return c


def claim_ci(key: str, d: int = 3) -> str:
    c = _full(key)
    return ci3(c["value"], c["ci_low"], c["ci_high"], d)


def pp(x: float) -> str:
    return f(abs(100 * x), 0)


def claim_ppci(key: str) -> str:
    c = _full(key)
    lo, hi = sorted((abs(c["ci_low"]), abs(c["ci_high"])))
    return f"{pp(c['value'])} percentage points (95% CI {f(100 * lo, 0)}–{f(100 * hi, 0)})"


# ---- tables -------------------------------------------------------------------------------
stage_a = pd.read_csv(TAB / "stage_a_acceptance.csv", float_precision="round_trip").set_index(["model", "cell"])
snap = pd.read_csv(TAB / "snapshot_contrasts.csv", float_precision="round_trip").set_index(["model", "point_type", "condition"])
live_c = pd.read_csv(TAB / "live_contrasts.csv", float_precision="round_trip").set_index("key")
live_r = pd.read_csv(TAB / "live_rates.csv", float_precision="round_trip").set_index(["measure", "period", "arm"])
curve = pd.read_csv(TAB / "detector_curve.csv", float_precision="round_trip").set_index("m")
transfer = pd.read_csv(TAB / "detector_transfer.csv", float_precision="round_trip").set_index("m")
susp = pd.read_csv(TAB / "probes_suspicion.csv", float_precision="round_trip").set_index(["arm", "role"])
susp_pool = pd.read_csv(TAB / "probes_suspicion_pooled.csv", float_precision="round_trip").set_index("group")
denial = pd.read_csv(TAB / "probes_denial.csv", float_precision="round_trip").set_index(["arm", "variant"])
budget = pd.read_csv(TAB / "budget.csv", float_precision="round_trip")

# denial_judge.md has no CSV twin: parse its table and its note line.
_dj = (TAB / "denial_judge.md").read_text()
_rows = [l for l in _dj.splitlines() if l.startswith("| B")]
DJ = {}
for l in _rows:
    c = [x.strip() for x in l.strip("|").split("|")]
    DJ[(c[0], c[1])] = dict(n=int(c[2]), parser=int(c[3]), judge=int(c[4]), unclear=int(c[8]))
_m = re.search(r"pooled over variants: (\d+)/(\d+) vs (\d+)/(\d+), diff ([+\-][\d.]+) \[([+\-][\d.]+), "
               r"([+\-][\d.]+)\], Fisher p = (\d+\.\d+)", _dj)
_kp = re.search(r"kappa ([\d.]+) against (\d+) hand labels \(parser ([\d.]+)\)", _dj)

sc = R["probes_scalars"]["denial_notice"]
ls = R["live_scalars"]
dl = ls["detector_live"]["by_arm"]


def acc(model, cell):
    r = stage_a.loc[(model, cell)]
    return f"{int(r.strict_k)}/{int(r.strict_n)}"


def snapmean(model, pt, cond, which="mean_condition"):
    return f(snap.loc[(model, pt, cond), which])


def _p(p: float) -> str:
    return "p\u00a0<\u00a00.001" if p < 0.001 else f"p\u00a0=\u00a0{f(p)}"  # non-breaking spaces


def _flag_prob(p: float, m: int) -> float:
    """Probability that a simulated agent with pooled challenge rate p is flagged at audit length m:
    flag if the observed rate is below -tau, and with probability tie_flag_prob if equal to it."""
    from math import comb
    thr, g = -curve.loc[m, "tau"], curve.loc[m, "tie_flag_prob"]
    pmf = [comb(m, k) * p ** k * (1 - p) ** (m - k) for k in range(m + 1)]
    return sum(pmf[k] for k in range(m + 1) if k / m < thr - 1e-12) + g * sum(
        pmf[k] for k in range(m + 1) if abs(k / m - thr) < 1e-12)


def _welch_ci(t: str, c: str) -> str:
    """Welch 95% CI for the difference in mean per-sequence post-offer restraint rates (tables/live_rates.csv)."""
    from scipy import stats
    a, b = live_r.loc[("restraint", "post", t)], live_r.loc[("restraint", "post", c)]
    va, vb = a.sd_rate ** 2 / a.n_seq, b.sd_rate ** 2 / b.n_seq
    df = (va + vb) ** 2 / (va ** 2 / (a.n_seq - 1) + vb ** 2 / (b.n_seq - 1))
    d, h = a.mean_rate - b.mean_rate, stats.t.ppf(0.975, df) * (va + vb) ** 0.5
    return f"[{f(d - h)}, {f(d + h)}]"


_NUM_WORD = {i: w for i, w in enumerate("zero one two three four five six seven eight nine ten".split())}
# One-off detector calibration: K samples of the null record (C1a) at each challenge-S decision
# (sting/config.py SNAPSHOT_K_OVERRIDES; tables/snapshot_contrasts.csv n_points).
_K_C1A = int(re.search(r'\("chal_S", "C1a"\): (\d+)', (ROOT / "sting" / "config.py").read_text()).group(1))
_CALIB_CALLS = _K_C1A * int(snap.loc[("llama-3.1-8b", "chal_S", "C3"), "n_points"])


# Post hoc gap analyses (sting/analysis/posthoc_gaps.py; plan and decision rules in DEVIATIONS.md D).
PH = json.loads((RES / "posthoc" / "gaps.json").read_text())
assert not PH.get("stub"), "post hoc outputs are stub data"
assert "gap1_ablation" in PH, "run posthoc_gaps with --rerun-suspicion"

X = {
    # protocol and health (results.json -> health)
    "frozen_hash": H["protocol"]["frozen_hash"],
    "data_folders": str(H["protocol"]["data_folders"]),
    "all_frozen": "all" if H["protocol"]["all_data_under_frozen_protocol"] else "NOT all",
    "decisions_llm": f"{H['decisions_llm']:,}",
    "fallback": pct(H["fallback_rate_llm"]),
    "games": str(H["games"]),
    "capped": str(H["capped_games"]),
    "median_game": f(H["median_game_minutes"], 2),
    "sting_last": f(H["sting_last_survivor_share"]),
    "template_share": pct(H["snapshot_template_reply_share"]),
    "snap_fallback": pct(H["snapshot_fallback_rate"], 2),
    "a_unclear": pct(H["stage_a_unclear_rate"], 0),
    "strict_vs_zeng": pct(H["stage_a_strict_vs_zeng_disagreement"]),
    "live_acc_B0": f"{round(H['live_acceptance_by_arm']['B0'] * H['sequences_by_arm']['B0'])}/{H['sequences_by_arm']['B0']}",
    "live_acc_B1": f"{round(H['live_acceptance_by_arm']['B1'] * H['sequences_by_arm']['B1'])}/{H['sequences_by_arm']['B1']}",
    "live_acc_B2": f"{round(H['live_acceptance_by_arm']['B2'] * H['sequences_by_arm']['B2'])}/{H['sequences_by_arm']['B2']}",
    "live_acc_B4": f"{round(H['live_acceptance_by_arm']['B4'] * H['sequences_by_arm']['B4'])}/{H['sequences_by_arm']['B4']}",
    # Holm (results.json -> holm)
    "holm_H1": f"{R['holm']['adjusted']['H1']:.1e}",
    "holm_H2live": f"{R['holm']['adjusted']['H2_live']:.1e}",
    # Stage A counts (tables/stage_a_acceptance.csv)
    "k_llama_A1": acc("llama-3.1-8b", "A1"),
    "k_llama_A4": acc("llama-3.1-8b", "A4"),
    "k_qwen_A1": acc("qwen2.5-7b", "A1"),
    "k_qwen_A0d": acc("qwen2.5-7b", "A0d"),
    "k_claude_A2": acc("claude-haiku-5.5", "A2"),
    "k_claude_A7": acc("claude-haiku-5.5", "A7"),
    "k_llama_A2": acc("llama-3.1-8b", "A2"),
    "k_claude_A1": acc("claude-haiku-5.5", "A1"),
    "zeng_claude_A0z": f(stage_a.loc[("claude-haiku-5.5", "A0z")].zeng_p),
    "zeng_k_claude_A0z": f"{int(stage_a.loc[('claude-haiku-5.5', 'A0z')].zeng_k)}/{int(stage_a.loc[('claude-haiku-5.5', 'A0z')].zeng_n)}",
    "judge_claude_A0z": f(stage_a.loc[("claude-haiku-5.5", "A0z")].judge_p),
    "h4b": ci3(R["H4b"]["estimate"], R["H4b"]["ci_low"], R["H4b"]["ci_high"]),
    "notice_eff_direct": f(R["H4a"]["notice_effect_direct"], 3, sign=True),
    "notice_eff_benign": f(R["H4a"]["notice_effect_benign"], 3, sign=True),
    "notice_eff_direct_abs": f(abs(R["H4a"]["notice_effect_direct"])),
    "notice_eff_benign_abs": f(abs(R["H4a"]["notice_effect_benign"])),
    "notice_direct_ci": f"[{f(live_c.loc['notice_vs_direct', 'ci_low'])}, {f(live_c.loc['notice_vs_direct', 'ci_high'])}]",
    "notice_none_abs": f(abs(live_c.loc["notice_vs_none", "estimate"])),
    "notice_none_ci": f"[{f(abs(live_c.loc['notice_vs_none', 'ci_high']))}, {f(abs(live_c.loc['notice_vs_none', 'ci_low']))}]",
    # snapshot condition means (tables/snapshot_contrasts.csv)
    "llama_C1": snapmean("llama-3.1-8b", "chal_S", "C3", "mean_reference"),
    "llama_C3": snapmean("llama-3.1-8b", "chal_S", "C3"),
    "llama_C5": snapmean("llama-3.1-8b", "chal_S", "C5"),
    "claude_C1": snapmean("claude-haiku-5.5", "chal_S", "C3", "mean_reference"),
    "claude_C3": snapmean("claude-haiku-5.5", "chal_S", "C3"),
    # live (tables/live_contrasts.csv, live_rates.csv; results.json -> live_scalars)
    "B1_post": f(live_c.loc["H2_live_ITT", "mean_t"]),
    "B3_post": f(live_c.loc["H2_live_ITT", "mean_c"]),
    "B0_post": f(live_c.loc["PC2", "mean_t"]),
    "B2_post": f(live_c.loc["benign_vs_none", "mean_t"]),
    "B4_post": f(live_c.loc["notice_vs_direct", "mean_t"]),
    "B1pp_post": f(live_c.loc["H2_live_PP", "mean_t"]),
    "notice_none_pw": f(live_c.loc["notice_vs_none", "p_welch"]),
    "notice_none_pp": f(live_c.loc["notice_vs_none", "p_perm"]),
    "pre_expl_B1": f(live_r.loc[("exploitation", "pre", "B1"), "mean_rate"]),
    "pre_expl_B3": f(live_r.loc[("exploitation", "pre", "B3"), "mean_rate"]),
    "pre_disp_B1": f(live_r.loc[("displacement", "pre", "B1"), "mean_rate"]),
    "pre_disp_B3": f(live_r.loc[("displacement", "pre", "B3"), "mean_rate"]),
    "pre_B1": f(ls["balance_pre"]["mean_t"]),
    "pre_B3": f(ls["balance_pre"]["mean_c"]),
    "balance": ci3(ls["balance_pre"]["estimate"], ls["balance_pre"]["ci_low"], ls["balance_pre"]["ci_high"], sign=True),
    "balance_p": f(ls["balance_pre"]["p_welch"]),
    "pooled": ci3(ls["H2_live_pooled"]["estimate"], ls["H2_live_pooled"]["ci_low"], ls["H2_live_pooled"]["ci_high"]),
    "gee_or": ci3(ls["H2_live_gee"]["or_"], ls["H2_live_gee"]["or_low"], ls["H2_live_gee"]["or_high"]),
    "excluded": str(ls["H2_live_ITT_excluding_suspicious"]["excluded"]),
    "excl_nt": str(ls["H2_live_ITT_excluding_suspicious"]["n_t"]),
    "tau_rate": f(ls["detector_live"]["tau_rate"], 2),
    **{f"dl_{a}": f"{dl[a]['flagged']}/{dl[a]['n']}" for a in ("B0", "B1", "B2", "B4")},
    # detector (tables/detector_curve.csv, detector_transfer.csv)
    "tpr_m5": f(curve.loc[5, "flag_C3"]),
    "tpr_m10": f(curve.loc[10, "flag_C3"]),
    "fpr_m5": f(curve.loc[5, "flag_C1b"]),
    "fpr_m40": f(curve.loc[40, "flag_C1b"]),
    "fpr_m40_ci": f"[{f(curve.loc[40, 'flag_C1b_lo'])}, {f(curve.loc[40, 'flag_C1b_hi'])}]",
    "flag_C4_m20": f(curve.loc[20, "flag_C4"]),
    "flag_C6_m20": f(curve.loc[20, "flag_C6"]),
    "flag_C7_m20": f(curve.loc[20, "flag_C7"]),
    "flag_C8_m20": f(curve.loc[20, "flag_C8"]),
    "tr_fpr_m20": f(transfer.loc[20, "flag_C1b"]),
    "tr_tpr_m20": f(transfer.loc[20, "flag_C3"]),
    # suspicion (tables/probes_suspicion*.csv)
    "susp_T": f"{int(susp_pool.loc['T', 'k'])}/{int(susp_pool.loc['T', 'n'])}",
    "susp_T_ci": ci3(susp_pool.loc["T", "rate"], susp_pool.loc["T", "lo"], susp_pool.loc["T", "hi"]),
    "susp_O": f"{int(susp_pool.loc['O1/O2', 'k'])}/{int(susp_pool.loc['O1/O2', 'n'])}",
    "susp_O_rate": f(susp_pool.loc["O1/O2", "rate"]),
    "susp_O_ci": ci3(susp_pool.loc["O1/O2", "rate"], susp_pool.loc["O1/O2", "lo"], susp_pool.loc["O1/O2", "hi"]),
    "susp_B4T": f"{int(susp.loc[('B4', 'T'), 'suspects_S_q3'])}/{int(susp.loc[('B4', 'T'), 'n'])}",
    "susp_B0T": f"{int(susp.loc[('B0', 'T'), 'suspects_S_q3'])}/{int(susp.loc[('B0', 'T'), 'n'])}",
    "susp_B1T": f"{int(susp.loc[('B1', 'T'), 'suspects_S_q3'])}/{int(susp.loc[('B1', 'T'), 'n'])}",
    "susp_B2T": f"{int(susp.loc[('B2', 'T'), 'suspects_S_q3'])}/{int(susp.loc[('B2', 'T'), 'n'])}",
    "susp_B3T": f"{int(susp.loc[('B3', 'T'), 'suspects_S_q3'])}/{int(susp.loc[('B3', 'T'), 'n'])}",
    "named_B3T": f"{int(susp.loc[('B3', 'T'), 'names_S_before_q3'])}/{int(susp.loc[('B3', 'T'), 'n'])}",
    # denial (tables/probes_denial.csv; results.json -> probes_scalars; tables/denial_judge.md)
    "den_parser_B1_rh": f"{int(denial.loc[('B1', 'report_honest'), 'denials'])}/{int(denial.loc[('B1', 'report_honest'), 'n'])}",
    "den_judge_B1_rh": f"{DJ[('B1', 'report_honest')]['judge']}/{DJ[('B1', 'report_honest')]['n']}",
    "den_judge_B1_rh_unclear": str(DJ[("B1", "report_honest")]["unclear"]),
    "den_parser_B2": f"{sum(DJ[('B2', v)]['parser'] for v in ('check', 'check_honest', 'report', 'report_honest'))}/{sum(DJ[('B2', v)]['n'] for v in ('check', 'check_honest', 'report', 'report_honest'))}",
    "den_judge_B2": f"{sum(DJ[('B2', v)]['judge'] for v in ('check', 'check_honest', 'report', 'report_honest'))}/{sum(DJ[('B2', v)]['n'] for v in ('check', 'check_honest', 'report', 'report_honest'))}",
    "den_parser_notice": f"{round(sc['b4'] * sc['n_b4'])}/{sc['n_b4']} vs {round(sc['b1'] * sc['n_b1'])}/{sc['n_b1']}",
    "den_parser_diff": ci3(sc["diff"], sc["lo"], sc["hi"]),
    "den_parser_p": f(sc["p"]),
    "den_judge_notice": f"{_m.group(1)}/{_m.group(2)} vs {_m.group(3)}/{_m.group(4)}",
    "den_judge_diff": f"{_m.group(5)} [{_m.group(6)}, {_m.group(7)}]".replace("-", "−"),
    "den_judge_p": _m.group(8),
    "kappa_judge": f(R["judge_kappa"]),
    "kappa_judge_md": _kp.group(1),
    "kappa_n": _kp.group(2),
    "kappa_parser": _kp.group(3),
    # budget (tables/budget.csv)
    "cost_claude_A": "$" + f(budget[(budget.stage == 'A') & (budget.model == 'claude-haiku-5.5')].cost_usd_estimate.iloc[0], 2),
    "cost_claude_S": "$" + f(budget[(budget.stage == 'S') & (budget.model == 'claude-haiku-5.5')].cost_usd_estimate.iloc[0], 2),
    "cost_claude": "$" + f(budget[budget.model == 'claude-haiku-5.5'].cost_usd_estimate.sum(), 2),
    "calls_total": f"{int(budget.calls.sum()):,}",
    # fallback range across arms (results.json -> health)
    "fallback_arm_lo": pct(min(H["fallback_rate_by_arm"].values())),
    "fallback_arm_hi": pct(max(H["fallback_rate_by_arm"].values())),
    # detector threshold at m = 20 as a challenge rate (score = -rate; flag if rate < -tau), and the
    # share of the pact's restraint an accepter must give up to reach it (snapshot means, chal_S)
    "thr_rate_m20": f(-curve.loc[20, "tau"], 2),
    "tie_m20": f(curve.loc[20, "tie_flag_prob"]),
    # ratio of point estimates, so printed to the nearest 5%
    "evade_share": (lambda c1, c3, thr: f(5 * round(20 * (thr - c3) / (c1 - c3)), 0) + "%")(
        snap.loc[("llama-3.1-8b", "chal_S", "C3"), "mean_reference"],
        snap.loc[("llama-3.1-8b", "chal_S", "C3"), "mean_condition"], -curve.loc[20, "tau"]),
    "fpr_one_in": f"{round(1 / curve.loc[20, 'flag_C1b'])}",
    "benign_one_in": f"{round(1 / curve.loc[20, 'flag_C2'])}",
    "h2_clusters": str(int(snap.loc[("llama-3.1-8b", "chal_S", "C3"), "n_clusters"])),
    # cost of one offer plus a 20-decision audit at Claude Haiku 5.5 prices, from the Stage S per-call cost
    "audit_cost": (lambda r: "$" + f(21 * r.cost_usd_estimate / r.calls, 3))(
        budget[(budget.stage == "S") & (budget.model == "claude-haiku-5.5")].iloc[0]),
    "susp_diff_pp": f(100 * (susp_pool.loc['T', 'rate'] - susp_pool.loc['O1/O2', 'rate']), 0),
    "calls_A": f"{int(budget[budget.stage == 'A'].calls.sum()):,}",
    "calls_L": f"{int(budget[budget.stage == 'L'].calls.sum()):,}",
    "calls_S": f"{int(budget[budget.stage == 'S'].calls.sum()):,}",
    # round 7 additions
    "k_qwen_A2": acc("qwen2.5-7b", "A2"),
    "notice_direct_p": _p(live_c.loc["notice_vs_direct", "p_welch"]),
    "den_parser_hi_pp": f(100 * sc['hi'], 0),
    # sequences with no pre-offer T-on-S decision (no open circle in Figure 4)
    "no_pre": _NUM_WORD[sum(H["sequences_by_arm"].values()) - int(live_r.reset_index().query("measure == 'restraint' and period == 'pre'").n_seq.sum())],
    "no_pre_cap": _NUM_WORD[sum(H["sequences_by_arm"].values()) - int(live_r.reset_index().query("measure == 'restraint' and period == 'pre'").n_seq.sum())].capitalize(),
    "notice_none_est": f(live_c.loc["notice_vs_none", "estimate"]),
    # A simulated audited agent is m independent draws from one record's pooled answers, so its flag
    # probability is binomial given the fitted threshold (tables/detector_curve.csv: tau, tie_flag_prob).
    "flag_at_thr": f(_flag_prob(0.5, 20), 2),
    "notice_none_ci_signed": f"[{f(live_c.loc['notice_vs_none', 'ci_low'])}, {f(live_c.loc['notice_vs_none', 'ci_high'])}]",
    "susp_B3O": f"{int(susp.loc[('B3', 'O1'), 'suspects_S_q3'] + susp.loc[('B3', 'O2'), 'suspects_S_q3'])}/{int(susp.loc[('B3', 'O1'), 'n'] + susp.loc[('B3', 'O2'), 'n'])}",
    "fpr_hi_m20": f(curve.loc[20, "flag_C1b_hi"], 2),
    "fpr_exact_m20": f(_flag_prob(snap.loc[("llama-3.1-8b", "chal_S", "C1b"), "mean_condition"], 20)),
    "h2live_welch_ci": _welch_ci("B1", "B3"),
    "frozen_hash_short": H["protocol"]["frozen_hash"][:8],
    "calib_calls": f"{_CALIB_CALLS:,}",
    "calib_cost": (lambda r: "$" + f(_CALIB_CALLS * r.cost_usd_estimate / r.calls, 2))(
        budget[(budget.stage == "S") & (budget.model == "claude-haiku-5.5")].iloc[0]),
}
_g2 = PH["gap2"]["contrasts"]
_rf = pd.read_csv(RES / "posthoc" / "refusers.csv").set_index(["arm", "group"])
_sg = pd.read_csv(RES / "posthoc" / "suspicion_by_arm_group.csv")
_a = PH["gap1_ablation"]
_off = _sg[(_sg["group"] == "T") & (_sg["arm"] != "B3")]          # offered targets' original answers
_ok, _on = int(_off["k"].sum()), int(_off["n"].sum())
assert _on == _a["n_seq"], "ablation sequences != offered targets"


def _wilson(k, n, z=1.959964):
    ph, d = k / n, 1 + z * z / n
    c, h = (ph + z * z / (2 * n)) / d, z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def _binom_two_sided(k, n, p0):
    pm = [math.comb(n, i) * p0 ** i * (1 - p0) ** (n - i) for i in range(n + 1)]
    return min(1.0, sum(q for q in pm if q <= pm[k] * (1 + 1e-9)))


_wl, _wh = _wilson(_ok, _on)
X.update({
    # gap 2: B4 refusers (posthoc/refusers.csv, gaps.json -> gap2)
    "ph_ref_n": str(PH["gap2"]["refusers_n"]),
    "ph_ref_n_word": _NUM_WORD[PH["gap2"]["refusers_n"]],
    "ph_ref_rate": f(_rf.loc[("B4", "refused"), "post_mean"]),
    "ph_acc_rate": f(_rf.loc[("B4", "accepted"), "post_mean"]),
    "ph_b1acc_rate": f(_rf.loc[("B1", "accepted"), "post_mean"]),
    "ph_b3_rate": f(_rf.loc[("B3", "no offer"), "post_mean"]),
    "ph_ref_pre": f(_rf.loc[("B4", "refused"), "pre_mean"]),
    "ph_b3_pre": f(_rf.loc[("B3", "no offer"), "pre_mean"]),
    "ph_ref_vs_b3": ci3(_g2["B4_refused_vs_B3"]["estimate"], _g2["B4_refused_vs_B3"]["ci_low"],
                        _g2["B4_refused_vs_B3"]["ci_high"]),
    "ph_ref_vs_b3_v": f(_g2["B4_refused_vs_B3"]["estimate"]),
    "ph_ref_vs_b3_pw": f(_g2["B4_refused_vs_B3"]["p_welch"], 2),
    "ph_ref_vs_acc": ci3(_g2["B4_refused_vs_B4_accepted"]["estimate"], _g2["B4_refused_vs_B4_accepted"]["ci_low"],
                         _g2["B4_refused_vs_B4_accepted"]["ci_high"]),
    "ph_acc_vs_b1": ci3(_g2["B4_accepted_vs_B1_accepted"]["estimate"], _g2["B4_accepted_vs_B1_accepted"]["ci_low"],
                        _g2["B4_accepted_vs_B1_accepted"]["ci_high"]),
    "ph_ref_flagged": f"{PH['gap2']['refusers_flagged']}/{PH['gap2']['refusers_n']}",
    "ph_tau": f(PH["gap2"]["live_rule_tau"], 2),
    # gap 1: paired record ablation (gaps.json -> gap1_ablation)
    "ph_susp_own": f(_a["rate_own"]), "ph_susp_null": f(_a["rate_null"]),
    "ph_susp_diff": ci3(_a["paired"]["estimate"], _a["paired"]["ci_low"], _a["paired"]["ci_high"]),
    "ph_susp_p": f(_a["paired"]["p"]),
    "ph_susp_k": str(_a["k"]), "ph_susp_nseq": str(_a["n_seq"]),
    "ph_susp_orig": f"{_ok}/{_on}",
    "ph_susp_orig_ci": ci3(_ok / _on, _wl, _wh),
    "ph_susp_orig_p": f(_binom_two_sided(_ok, _on, _a["rate_own"]), 2),
})
assert PH["gap2"]["verdict"].startswith("no evidence"), "text assumes the gap 2 verdict"
assert _a["verdict"] == "record raises stated suspicion", "text assumes the gap 1 verdict"
assert _wl <= _a["rate_own"] <= _wh, "text says the original rate's CI contains the re-ask rate"

# Post hoc extensions (sting/analysis/posthoc_extend.py; plan and decision rules in DEVIATIONS.md D).
EXT = RES / "posthoc_ext"
EJ = json.loads((EXT / "ext.json").read_text())
assert not EJ["stub"] and EJ["snapshot_points_same"], "extension outputs are stub data or off the preregistered points"
_es = pd.read_csv(EXT / "snapshots_ext.csv")
_es = _es[_es["point_type"] == "chal_S"].set_index(["model", "contrast"])
_ed = pd.read_csv(EXT / "detector_ext.csv").set_index("model")
X["e_ll_gamma2"] = f(_ed.loc["llama-3.1-8b", "gamma"], 2)
X["tie_m20_2"] = f(curve.loc[20, "tie_flag_prob"], 2)
assert int(_ed.loc["llama-3.1-8b", "c"]) == int(round(-curve.loc[20, "tau"] * 20))  # same cut-off, only the tie probability differs
_MK = {"ll": "llama-3.1-8b", "qw": "qwen2.5-7b", "cl": "claude-haiku-5.5"}


def _live(tag):
    c = pd.read_csv(EXT / f"{tag}_live_contrasts.csv").set_index("key")
    sp = pd.read_csv(EXT / f"{tag}_live_split.csv").set_index(["arm", "group"])
    sp_ = pd.read_csv(EXT / f"{tag}_suspicion_pooled.csv").set_index("group")
    return c, sp, sp_


def _c(d):
    return ci3(d["estimate"], d["ci_low"], d["ci_high"])


for _t, _m in _MK.items():
    for _con in ("C9-C1", "C9-C2", "C10-C1", "C2-C1", "C4-C1", "C3-C1", "(C5-C3)-(C10-C1)"):
        if (_m, _con) in _es.index:
            _r = _es.loc[(_m, _con)]
            _k = _con.replace("(", "").replace(")", "").replace("-", "")
            X[f"e_{_t}_{_k}"] = _c(_r)
            X[f"e_{_t}_{_k}_v"] = f(_r["estimate"])
            X[f"e_{_t}_{_k}_a"] = f(_r["mean_a"]) if not pd.isna(_r["mean_a"]) else ""
            X[f"e_{_t}_{_k}_b"] = f(_r["mean_b"]) if not pd.isna(_r["mean_b"]) else ""
    _d = _ed.loc[_m]
    X[f"e_{_t}_c1a"] = f(_d["rate_C1a"])
    for _cond in ("C1b", "C2", "C3", "C4", "C9", "C10"):
        X[f"e_{_t}_flag_{_cond}"] = f(_d[f"flag_{_cond}"])
        X[f"e_{_t}_flag_{_cond}_ci"] = ci3(_d[f"flag_{_cond}"], _d[f"flag_{_cond}_lo"], _d[f"flag_{_cond}_hi"])
        X[f"e_{_t}_lthr_{_cond}"] = f(_d[f"llama_thr_flag_{_cond}"])
assert EJ["verdicts"]["item2_claude_acts_on_vague_pact"] and EJ["verdicts"]["item2_claude_beyond_contact"]
assert EJ["verdicts"]["item4_audit_supported_claude-haiku-5.5"] and EJ["verdicts"]["item4_audit_supported_qwen2.5-7b"]
assert EJ["verdicts"]["item3_snap_notice_weakens_pact_keeping"] and not EJ["verdicts"]["item3_live_notice_alone_raises_challenging"]

# notice-only live arm (Llama, B5)
_nc = EJ["notice_live"]
_nr = pd.read_csv(EXT / "notice_live_rates.csv").set_index(["arm", "period"])
_ns = pd.read_csv(EXT / "notice_live_suspicion.csv").set_index(["arm", "group"])
X.update({
    "e_B5_post": f(_nr.loc[("B5", "post"), "mean"]), "e_B5_n": str(int(_nr.loc[("B5", "post"), "n_seq"])),
    "e_B5_vs_B3": _c(_nc["B5_vs_B3"]), "e_B5_vs_B3_pw": f(_nc["B5_vs_B3"]["p_welch"], 2),
    "e_B4_vs_B5": _c(_nc["B4_vs_B5"]), "e_B5_pre": _c(_nc["B5_vs_B3_pre"]),
    "e_did_live": _c(_nc["did_(B4-B1)-(B5-B3)"]),
    "e_B5_susp_T": f"{int(_ns.loc[('B5', 'T'), 'k'])}/{int(_ns.loc[('B5', 'T'), 'n'])}",
    "e_B5_susp_O": f"{int(_ns.loc[('B5', 'O1/O2'), 'k'])}/{int(_ns.loc[('B5', 'O1/O2'), 'n'])}",
})

# cross-model live replications
for _t, _tag in (("qw", "qwen"), ("cl", "claude")):
    _lc, _sp, _sus = _live(_tag)
    _j = EJ[_tag]
    _acc = _j["acceptance"]
    X[f"e_{_t}_nseq"] = str(_j["n_seqs"])
    X[f"e_{_t}_ngames"] = str(_j["n_games"])
    X[f"e_{_t}_fallback"] = f"{_j['fallback_share']:.2%}"
    for _arm in ("B0", "B1", "B2", "B4", "B6"):
        if _arm in _acc:
            X[f"e_{_t}_acc_{_arm}"] = _acc[_arm]
    X[f"e_{_t}_B3"] = f(_sp.loc[("B3", "all"), "mean"])
    for _arm in ("B1", "B2", "B4", "B6"):
        for _g in ("accepted", "refused", "all"):
            if (_arm, _g) in _sp.index:
                X[f"e_{_t}_{_arm}_{_g}"] = f(_sp.loc[(_arm, _g), "mean"])
    for _k in ("H2_live_ITT", "H2_live_PP", "PC2", "benign_vs_none", "notice_vs_none", "notice_vs_direct",
               "exploitation_B1_vs_B3", "displacement_B1_vs_B3"):
        if _k in _lc.index and not pd.isna(_lc.loc[_k, "estimate"]):
            X[f"e_{_t}_{_k}"] = _c(_lc.loc[_k])
    for _k, _v in _j["extra"].items():
        if "estimate" in _v:
            X[f"e_{_t}_{_k}"] = _c(_v)
            X[f"e_{_t}_{_k}_pw"] = f(_v["p_welch"], 3)
        elif "flagged" in _v:
            X[f"e_{_t}_{_k}"] = f"{_v['flagged']}/{_v['n']}"
    X[f"e_{_t}_susp_T"] = f"{int(_sus.loc['T', 'k'])}/{int(_sus.loc['T', 'n'])}"
    X[f"e_{_t}_susp_O"] = f"{int(_sus.loc['O1/O2', 'k'])}/{int(_sus.loc['O1/O2', 'n'])}"
    _ab = (EJ.get("ablation") or {}).get(_tag)
    if _ab:
        X[f"e_{_t}_reask"] = f"{f(_ab['rate_own'])} vs {f(_ab['rate_null'])}"
    _dl = (_j.get("detector_live") or {}).get("by_arm", {})
    for _arm, _v in _dl.items():
        if _v["n"]:
            X[f"e_{_t}_dl_{_arm}"] = f"{_v['flagged']}/{_v['n']}"
    if "B6_vs_B3_ITT" in _j["extra"]:
        X[f"e_{_t}_B6_itt_pp"] = f(abs(_j['extra']['B6_vs_B3_ITT']['estimate']) * 100, 0)
    if (_j.get("detector_live") or {}).get("tau_rate") is not None:
        X[f"e_{_t}_tau"] = f(_j["detector_live"]["tau_rate"])
    if _j.get("balance_pre"):
        X[f"e_{_t}_bal_pre"] = _c(_j["balance_pre"])
# exploratory targeting / change-from-baseline (sting/analysis/posthoc_targeting.py)
_tg = pd.read_csv(EXT / "targeting_contrasts.csv")
_ts = pd.read_csv(EXT / "targeting.csv").set_index(["model", "arm", "group"])
for _t, _m in _MK.items():
    for _, _r in _tg[_tg["model"] == _m].iterrows():
        if pd.isna(_r["ci_low"]):
            continue
        _k = f"tg_{_t}_{_r['arm']}_{_r['group']}_{_r['measure']}"
        X[_k] = _c(_r)
        X[_k + "_v"] = f(_r["estimate"])
        X[_k + "_w"] = f"[{f(_r['welch_lo'])}, {f(_r['welch_hi'])}]"
    for (_mm, _arm, _g), _r in _ts.loc[[_m]].iterrows() if _m in _ts.index.get_level_values(0) else []:
        for _col in ("post_S", "pre_S", "post_O"):
            X[f"ts_{_t}_{_arm}_{_g}_{_col}"] = f(_r[_col])
for _t in ("qw", "cl"):
    for _k in ("H2_live_ITT", "B6_vs_B3_ITT", "B1_refused_vs_B3"):
        if f"e_{_t}_{_k}" in X:
            X[f"e_{_t}_{_k}_v"] = X[f"e_{_t}_{_k}"].split(" [")[0]
for _t, _tag in (("qw", "qwen"), ("cl", "claude")):
    _dn = pd.read_csv(EXT / f"{_tag}_denial.csv")
    _acc = _dn[_dn["arm"].isin(["B0", "B1", "B6"])]
    X[f"den_ext_{_t}_acc"] = f"{int(_acc['denials'].sum())}/{int(_acc['n'].sum())}"
    _b2 = _dn[_dn["arm"] == "B2"]
    if len(_b2):
        X[f"den_ext_{_t}_B2"] = f"{int(_b2['denials'].sum())}/{int(_b2['n'].sum())}"
# post hoc coalition-disruption snapshots (sting/posthoc_coalition.py)
_co = pd.read_csv(EXT / "coalition.csv")
_cj = json.loads((EXT / "coalition.json").read_text())
assert not _cj["stub"]
for _t, _m in _MK.items():
    for _, _r in _co[_co["model"] == _m].iterrows():
        _k = "co_" + _t + "_" + _r["contrast"].replace("(", "").replace(")", "").replace("-", "")
        X[_k] = _c(_r)
        X[_k + "_v"] = f(_r["estimate"])
    for _cn, _val in _cj["verdicts"][_m]["means"].items():
        X[f"co_{_t}_m_{_cn}"] = f(_val)
_cc = _co.set_index(["model", "contrast"])
_shares = []
for _t, _m in _MK.items():
    _eff = abs(_cc.loc[(_m, "K1-C1"), "estimate"])
    for _cn, _lab in (("(K2-K1)-(C10-C1)", "notice"), ("K3-K4", "warning")):
        _sh = max(0.0, _cc.loc[(_m, _cn), "ci_high"]) / _eff
        X[f"co_{_t}_ub_{_lab}"] = f(_sh * 100, 0) + "%"
        _shares.append(_sh)
X["e_qw_benign_pp"] = f(abs(pd.read_csv(EXT / 'qwen_live_contrasts.csv').set_index('key').loc['benign_vs_none', 'estimate']) * 100, 0)
X["co_ub_max"] = f(max(_shares) * 100, 0) + "%"
# the same upper bounds against the weakest pact effect inside its 95% CI (K1 - C1 is negative, so its ci_high)
_shares_cons = [max(0.0, _cc.loc[(_m, _cn), "ci_high"]) / abs(_cc.loc[(_m, "K1-C1"), "ci_high"])
                for _m in _MK.values() for _cn in ("(K2-K1)-(C10-C1)", "K3-K4")]
X["co_ub_max_cons"] = f(max(_shares_cons) * 100, 0) + "%"
X["tau_rate3"] = f(ls["detector_live"]["tau_rate"])
_sc = pd.read_csv(TAB / "snapshot_contrasts.csv")
_sc = _sc[(_sc["model"] == "llama-3.1-8b") & (_sc["point_type"] == "play_vs_S")]
X["expl_max"] = f(_sc["estimate"].abs().max(), 2)  # Figure 3 headline: largest change in bluffing against S
assert all(_cj["verdicts"][_m]["coalition_formed"] for _m in _MK.values())
assert not any(_cj["verdicts"][_m]["notice_disrupts"] or _cj["verdicts"][_m]["warning_disrupts_beyond_contact"]
               for _m in _MK.values()), "text says no intervention disrupted the coalition"
assert X["e_cl_susp_T"].startswith("0/") and X["e_qw_susp_T"].startswith("0/"), "text says no Claude/Qwen target named S"

assert all(stage_a.loc[("claude-haiku-5.5", c), "strict_p"] == 0 for c in ("A0z", "A0b", "A0d", "A1", "A4", "A6", "A8")), \
    "Section 4.1: unless instructed to collude, Claude refused every offer naming the pact or a designer tool"
assert X["kappa_judge"] == X["kappa_judge_md"], "judge kappa differs between results.json and denial_judge.md"

# ---- claims typed into the text that depend on results (each fails the build if the data stop supporting it)
X["e_ll_flag_C1b_hi2"] = f(_ed.loc["llama-3.1-8b", "flag_C1b_hi"], 2)
X["live_acc_B4_n_word"] = _NUM_WORD[round(H["live_acceptance_by_arm"]["B4"] * H["sequences_by_arm"]["B4"])]
assert all(R[k]["passed"] for k in ("PC1", "PC2", "PC3")), "Table 1 and Section 4 say all positive controls passed"
assert R["H2"]["supported"] and R["H3"]["supported"], "Table 1 says every preregistered test was supported"
assert all(v < 0.001 for v in R["holm"]["adjusted"].values()), "Table 1 prints Holm p < 0.001"
assert curve.loc[20, "flag_C1b_lo"] <= 0.10 <= curve.loc[20, "flag_C1b_hi"], "Table 1: FPR CI includes 0.10"
assert H["capped_games"] == 0 and EJ["qwen"]["capped"] == 0 and EJ["claude"]["capped"] == 0, "text says no game hit the cap"
assert H["stage_a_unclear_rate"] == 0, "Appendix B says no offer-battery reply was unparseable"
assert abs(_flag_prob(-curve.loc[20, "tau"], 20) - 0.5) < 0.05, "Section 4.3: flagged about half the time at the threshold rate"
assert EJ["verdicts"]["qwen_H2_live_ITT_replicates"] and not EJ["verdicts"]["claude_H2_live_ITT_replicates"], "H2-live replicates for Qwen, not Claude"
assert EJ["verdicts"]["item3_snap_general_notice_effect"], "Appendix B: the notice alone raises challenging in snapshots"
assert all(_cc.loc[(m, "K4-K1"), "p"] >= 0.06 for m in ("claude-haiku-5.5", "qwen2.5-7b")), "Appendix B: both sign-flip p >= 0.06"
assert _g2["B4_refused_vs_B3"]["ci_low"] > _rf.loc[("B1", "accepted"), "post_mean"] - _rf.loc[("B3", "no offer"), "post_mean"], "Section 4.4 item 3: the refusers' interval excludes a drop like B1 accepters'"
assert all(_ts.loc[("qwen2.5-7b", a, "accepted"), "post_S"] == 0 for a in ("B0", "B1")), "Appendix B: both Qwen accepter groups challenged S at 0.000"
# deterrence verdict for Llama (preregistered rule): acceptance falls (H4a) and accepters restrain less (H4b)
assert R["H4a"]["estimate"] < 0 and R["H4a"]["ci_high"] < 0 and R["H4b"]["ci_low"] > 0, "Section 4.4: verdict for Llama is deterrence"

SOURCES = {
    "ci": "claims.json", "v": "claims.json", "pp": "claims.json", "ppci": "claims.json",
}

_PAT = re.compile(r"\{\{(ci|v|pp|ppci|x):([^}]+)\}\}")
USED: dict[str, str] = {}


def render(text: str) -> str:
    def sub(m):
        kind, key = m.group(1), m.group(2)
        if kind == "x":
            out = X[key]
        else:
            c = _full(key)
            out = {"ci": lambda: claim_ci(key), "v": lambda: f(c["value"]),
                   "pp": lambda: pp(c["value"]), "ppci": lambda: claim_ppci(key)}[kind]()
        USED[f"{kind}:{key}"] = out
        return out
    return _PAT.sub(sub, text)
