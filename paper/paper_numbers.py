"""Every number the paper cites, looked up from the committed analysis outputs.

The paper text refers to numbers only through placeholders:
  {{ci:KEY}} / {{v:KEY}} / {{pp:KEY}} / {{ppci:KEY}}   a claim in sting_results/claims.json
  {{x:NAME}}                                         a named number defined below (source given)
A missing key stops the build, so no number can enter the text by hand. Design constants (500
offers per cell, 60 sequences, m = 20, FPR target 0.10, K = 5/20) come from PREREG.md.
"""
from __future__ import annotations

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
    s = f"{x:+.{d}f}" if sign else f"{x:.{d}f}"
    if float(s) == 0:
        s = s.lstrip("+-")
    return s.replace("-", "−")


def pct(x: float, d: int = 1) -> str:
    return f"{100 * x:.{d}f}%"


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
    return f"{abs(100 * x):.0f}"


def claim_ppci(key: str) -> str:
    c = _full(key)
    lo, hi = sorted((abs(c["ci_low"]), abs(c["ci_high"])))
    return f"{pp(c['value'])} percentage points (95% CI {100 * lo:.0f}–{100 * hi:.0f})"


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
    return "p < 0.001" if p < 0.001 else f"p = {f(p)}"


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
    "zeng_claude_A0z": f(stage_a.loc[("claude-haiku-5.5", "A0z")].zeng_p),
    "zeng_k_claude_A0z": f"{int(stage_a.loc[('claude-haiku-5.5', 'A0z')].zeng_k)}/{int(stage_a.loc[('claude-haiku-5.5', 'A0z')].zeng_n)}",
    "judge_claude_A0z": f(stage_a.loc[("claude-haiku-5.5", "A0z")].judge_p),
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
    "cost_claude_A": f"${budget[(budget.stage == 'A') & (budget.model == 'claude-haiku-5.5')].cost_usd_estimate.iloc[0]:.2f}",
    "cost_claude_S": f"${budget[(budget.stage == 'S') & (budget.model == 'claude-haiku-5.5')].cost_usd_estimate.iloc[0]:.2f}",
    "cost_claude": f"${budget[budget.model == 'claude-haiku-5.5'].cost_usd_estimate.sum():.2f}",
    "calls_total": f"{int(budget.calls.sum()):,}",
    # fallback range across arms (results.json -> health)
    "fallback_arm_lo": pct(min(H["fallback_rate_by_arm"].values())),
    "fallback_arm_hi": pct(max(H["fallback_rate_by_arm"].values())),
    # detector threshold at m = 20 as a challenge rate (score = -rate; flag if rate < -tau), and the
    # share of the pact's restraint an accepter must give up to reach it (snapshot means, chal_S)
    "thr_rate_m20": f(-curve.loc[20, "tau"], 2),
    "tie_m20": f(curve.loc[20, "tie_flag_prob"]),
    "evade_share": (lambda c1, c3, thr: f"{100 * (thr - c3) / (c1 - c3):.0f}%")(
        snap.loc[("llama-3.1-8b", "chal_S", "C3"), "mean_reference"],
        snap.loc[("llama-3.1-8b", "chal_S", "C3"), "mean_condition"], -curve.loc[20, "tau"]),
    "fpr_one_in": f"{round(1 / curve.loc[20, 'flag_C1b'])}",
    "benign_one_in": f"{round(1 / curve.loc[20, 'flag_C2'])}",
    "h2_clusters": str(int(snap.loc[("llama-3.1-8b", "chal_S", "C3"), "n_clusters"])),
    # cost of one offer plus a 20-decision audit at Claude Haiku 5.5 prices, from the Stage S per-call cost
    "audit_cost": (lambda r: f"${21 * r.cost_usd_estimate / r.calls:.3f}")(
        budget[(budget.stage == "S") & (budget.model == "claude-haiku-5.5")].iloc[0]),
    "susp_diff_pp": f"{100 * (susp_pool.loc['T', 'rate'] - susp_pool.loc['O1/O2', 'rate']):.0f}",
    "calls_A": f"{int(budget[budget.stage == 'A'].calls.sum()):,}",
    "calls_L": f"{int(budget[budget.stage == 'L'].calls.sum()):,}",
    "calls_S": f"{int(budget[budget.stage == 'S'].calls.sum()):,}",
    # round 7 additions
    "k_qwen_A2": acc("qwen2.5-7b", "A2"),
    "notice_direct_p": _p(live_c.loc["notice_vs_direct", "p_welch"]),
    "den_parser_hi_pp": f"{100 * sc['hi']:.0f}",
    # sequences with no pre-offer T-on-S decision (no open circle in Figure 4)
    "no_pre": _NUM_WORD[sum(H["sequences_by_arm"].values()) - int(live_r.reset_index().query("measure == 'restraint' and period == 'pre'").n_seq.sum())],
    "no_pre_cap": _NUM_WORD[sum(H["sequences_by_arm"].values()) - int(live_r.reset_index().query("measure == 'restraint' and period == 'pre'").n_seq.sum())].capitalize(),
    "notice_none_est": f(live_c.loc["notice_vs_none", "estimate"]),
    # A simulated audited agent is m independent draws from one record's pooled answers, so its flag
    # probability is binomial given the fitted threshold (tables/detector_curve.csv: tau, tie_flag_prob).
    "flag_at_thr": f(_flag_prob(0.5, 20), 2),
    "fpr_hi_m20": f(curve.loc[20, "flag_C1b_hi"], 2),
    "fpr_exact_m20": f(_flag_prob(snap.loc[("llama-3.1-8b", "chal_S", "C1b"), "mean_condition"], 20)),
    "h2live_welch_ci": _welch_ci("B1", "B3"),
    "frozen_hash_short": H["protocol"]["frozen_hash"][:8],
    "calib_calls": f"{_CALIB_CALLS:,}",
    "calib_cost": (lambda r: f"${_CALIB_CALLS * r.cost_usd_estimate / r.calls:.2f}")(
        budget[(budget.stage == "S") & (budget.model == "claude-haiku-5.5")].iloc[0]),
}
assert X["kappa_judge"] == X["kappa_judge_md"], "judge kappa differs between results.json and denial_judge.md"

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
