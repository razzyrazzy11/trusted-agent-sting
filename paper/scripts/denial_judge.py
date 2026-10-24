"""Secondary (post hoc) analysis: interview denial after a recorded acceptance, strict parser vs the
validated LLM judge. Writes sting_results/tables/denial_judge.md. Run from Collusion_Liars_Bar/ with
the raw data in sting_runs/:  python ../../paper/scripts/denial_judge.py
This is the exact code that produced the committed table (commit 292896c); see DEVIATIONS.md section D."""
import sys
sys.path.insert(0, ".")
from pathlib import Path
from sting.analysis.load import load
from sting.analysis import stats as S
from sting.judge import load_judge
runs = Path("sting_runs"); data = load(runs); j = load_judge(runs)
P = data.P.merge(data.seqs[["seq_id", "arm"]], on="seq_id", how="left", suffixes=("", "_seq"))
iv = P[(P["probe"] == "interview") & (P["recorded_accept"] == True)].copy()
iv["judge"] = [j.get(f"L|{s}|interview|{v}") for s, v in zip(iv["seq_id"], iv["variant"])]
lines = ["| arm | variant | n | denials_parser | denials_judge | rate_judge | lo | hi | judge_unclear | judge_missing |",
         "|---|---|---|---|---|---|---|---|---|---|"]
for (arm, var), g in iv.groupby(["arm", "variant"]):
    n, kp, kj = len(g), int((g["denial"] == True).sum()), int((g["judge"] == "NO").sum())
    p, lo, hi = S.wilson(kj, n)
    lines.append(f"| {arm} | {var} | {n} | {kp} | {kj} | {p:.3f} | {lo:.3f} | {hi:.3f} | "
                 f"{int((g['judge'] == 'UNCLEAR').sum())} | {int(g['judge'].isna().sum())} |")
b4, b1 = iv[iv.arm == "B4"], iv[iv.arm == "B1"]
k4, n4, k1, n1 = int((b4.judge == "NO").sum()), len(b4), int((b1.judge == "NO").sum()), len(b1)
d, lo, hi = S.newcombe_diff(k4, n4, k1, n1)
note = (f"Judge-based denial, B4 (notice) vs B1, pooled over variants: {k4}/{n4} vs {k1}/{n1}, "
        f"diff {d:+.3f} [{lo:+.3f}, {hi:+.3f}], Fisher p = {S.fisher_p(k4, n4, k1, n1):.3f}. "
        f"Answers, not independent agents (4 variants per target).")
out = Path("sting_results/tables/denial_judge.md")
out.write_text("# Interview denial after a recorded acceptance: strict parser vs validated judge\n\n"
               "Secondary analysis. Judge: Claude Haiku 5.5, kappa 0.933 against 100 hand labels "
               "(parser 0.893).\n\n" + "\n".join(lines) + "\n\n" + note + "\n")
print(out.read_text())
