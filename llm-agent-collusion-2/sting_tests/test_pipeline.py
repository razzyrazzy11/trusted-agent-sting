"""End-to-end pipeline validation on the stub: planted effects must be recovered, nulls must stay null,
and every output must carry the stub banner."""
import contextlib
import io
import json
import os
from pathlib import Path

import pytest

LB = Path(__file__).resolve().parents[1] / "Collusion_Liars_Bar"


@pytest.fixture(scope="module")
def pipeline(tmp_path_factory):
    from sting.analysis.analyze import run
    from sting.config import ARMS, SequenceConfig
    from sting.sequence import run_sequence
    from sting.stage_a import run_stage_a
    from sting.stage_s import run_stage_s
    from sting.stub import stub_factory
    runs = tmp_path_factory.mktemp("runs")
    out = tmp_path_factory.mktemp("results")
    cwd = os.getcwd()
    os.chdir(LB)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            run_stage_a(["llama-3.1-8b"], ["A0z", "A0b", "A0d", "A1", "A3", "A4", "A5", "A6", "A7", "A8"],
                        runs / "stageA", stub_factory=stub_factory(0), workers=4)
            for arm in ARMS:
                for seed in range(8):
                    run_sequence(SequenceConfig(arm=arm, seed=seed, reflect_workers=1), runs / "live",
                                 stub_factory=stub_factory(seed))
            run_stage_s(runs / "live", runs / "stageA", runs / "stageS", ["llama-3.1-8b"],
                        n_per_type={"chal_S": 60, "play_vs_S": 30, "chal_other": 10}, k=6,
                        stub_factory=stub_factory(0), workers=4)
            R = run(runs, out, reps=500)
    finally:
        os.chdir(cwd)
    return R, out


def test_positive_controls_pass(pipeline):
    R, _ = pipeline
    assert R["PC1"]["passed"]
    assert R["PC3"]["passed"]
    assert R["PC2"]["estimate"] < -0.3                      # planted 0.60 -> 0.10


def test_primary_effect_recovered(pipeline):
    R, _ = pipeline
    h2 = R["H2"]
    assert -0.50 < h2["estimate"] < -0.20                   # planted -0.35
    assert h2["ci_high"] < 0 and h2["supported"]


def test_nulls_stay_null(pipeline):
    R, _ = pipeline
    snap = R["snapshot"]
    s = snap[(snap["model"] == "llama-3.1-8b") & (snap["point_type"] == "chal_S")].set_index("condition")
    assert s.loc["C1b", "ci_low"] <= 0 <= s.loc["C1b", "ci_high"]     # A/A
    assert abs(s.loc["C2", "estimate"]) < 0.12                         # benign contact: no planted effect
    assert s.loc["C7", "estimate"] < -0.25 and s.loc["C6", "estimate"] > 0.05   # personas


def test_acceptance_and_detector(pipeline):
    R, _ = pipeline
    a = R["stage_a"].set_index("cell")
    assert a.loc["A8", "strict_p"] < 0.2 and a.loc["A7", "strict_p"] > 0.8
    assert a.loc["A4", "strict_p"] < a.loc["A1", "strict_p"]
    curve = {row["m"]: row for row in R["H3"]["curve"]}
    for m, row in curve.items():
        assert abs(row["calibration_fpr"] - 0.10) < 1e-9        # randomized threshold is exact
    assert curve[40]["flag_C3"] > curve[5]["flag_C3"]           # longer audits detect more


def test_outputs_are_stamped_as_stub(pipeline):
    _, out = pipeline
    claims = json.loads((out / "claims.json").read_text())
    assert claims["stub"] is True and "NOT RESULTS" in claims["banner"]
    assert (out / "summary.md").read_text().startswith("> **STUB DATA")
    for f in ("fig1_design", "fig2_acceptance", "fig3_snapshots", "fig4_live", "fig5_detector"):
        assert (out / "figures" / f"{f}.png").exists() and (out / "figures" / f"{f}.pdf").exists()


def test_refuses_to_mix_stub_and_real(tmp_path):
    from sting.runinfo import write_run_info
    write_run_info(tmp_path, stub=True, stage="A")
    with pytest.raises(RuntimeError):
        write_run_info(tmp_path, stub=False, stage="A")
