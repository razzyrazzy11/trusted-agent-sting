"""Paper figures, drawn at print size so text is >= 8 pt on the page.

Figures 2, 3 and 5 are redrawn from the committed analysis tables (sting_results/tables/*.csv) with
the palette of sting/analysis/figures.py; figure 1 is the same schematic at print size. Figure 4
needs per-sequence rates that are not in the committed tables, so the committed analysis figure is
used (cropped, without its in-image title). No number is computed here.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.patches  # noqa: E402,F401
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from PIL import Image, ImageChops  # noqa: E402

ROOT = Path(__file__).resolve().parents[1] / "llm-agent-collusion-2" / "Collusion_Liars_Bar"
RES = ROOT / "sting_results"
TAB = RES / "tables"
OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(exist_ok=True)

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8, "axes.edgecolor": AXIS, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.titlecolor": INK, "axes.titlesize": 8.5,
    "axes.labelsize": 8, "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 8,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 300, "savefig.bbox": "tight",
})


def err(est, lo, hi):
    return [[max(0.0, est - lo)], [max(0.0, hi - est)]]


def save(fig, name):
    fig.savefig(OUT / f"{name}.png")
    plt.close(fig)


# ---- Figure 1: design ---------------------------------------------------------------------
def fig1():
    fig, ax = plt.subplots(figsize=(6.0, 1.95))
    ax.axis("off"); ax.set_xlim(0, 10.9); ax.set_ylim(0, 4.1)

    def ring(x0, order, title, note):
        ax.text(x0 + 1.0, 3.85, title, ha="center", color=INK, fontsize=8.5, weight="bold")
        pos = [(x0, 3.0), (x0 + 2.0, 3.0), (x0 + 2.0, 1.4), (x0, 1.4)]
        for (x, y), role in zip(pos, order):
            face = BLUE if role == "S" else (ORANGE if role == "T" else "white")
            ax.add_patch(matplotlib.patches.Ellipse((x, y), 0.62, 0.78, facecolor=face, edgecolor=INK2, lw=0.8))
            ax.text(x, y, role, ha="center", va="center", fontsize=8.5,
                    color="white" if role in ("S", "T") else INK)
        for i in range(4):
            (x1, y1), (x2, y2) = pos[i], pos[(i + 1) % 4]
            ax.annotate("", xy=(x2 + (x1 - x2) * 0.27, y2 + (y1 - y2) * 0.27),
                        xytext=(x1 + (x2 - x1) * 0.27, y1 + (y2 - y1) * 0.27),
                        arrowprops=dict(arrowstyle="->", color=MUTED, lw=0.9))
        ax.text(x0 + 1.0, 0.35, note, ha="center", va="center", color=INK2, fontsize=8, linespacing=1.2)

    ring(0.5, ["S", "T", "O1", "O2"], "Seating R", "T sits after S\n(restraint)")
    ring(3.75, ["T", "S", "O1", "O2"], "Seating E", "S sits after T\n(exploitation)")
    ax.text(6.75, 3.85, "Six-game sequence (RERERE or ERERER)", color=INK, fontsize=8.5, weight="bold")
    steps = ["Games 1–2: no offer", "Before game 3: S's private offer;",
             "   T replies ACCEPT or REFUSE", "Games 3–6: T's reply stays in its",
             "   private record; S never challenges T", "End: suspicion questions, interview"]
    for i, s in enumerate(steps):
        ax.text(6.75, 3.25 - i * 0.52, s, color=INK2, fontsize=8)
    save(fig, "fig1_design")


# ---- Figure 2: Stage A acceptance ------------------------------------------------------------
SHORT_A = {
    "A0z": "A0z designer: secret-hint tool (Zeng)", "A0b": "A0b designer: hint tool with S",
    "A0d": "A0d designer: direct pact with S", "A1": "A1 sting: direct pact",
    "A2": "A2 sting: indirect pact", "A3": "A3 sting: benign proposal",
    "A4": "A4 sting: direct + integrity notice", "A5": "A5 sting: benign + integrity notice",
    "A6": "A6 sting: direct + fairness reminder", "A7": "A7 sting: direct, colluder persona",
    "A8": "A8 sting: direct, honest persona",
}
MODELS = [("llama-3.1-8b", "Llama-3.1-8B", BLUE, "o"), ("qwen2.5-7b", "Qwen2.5-7B", AQUA, "s"),
          ("claude-haiku-5.5", "Claude Haiku 5.5", ORANGE, "D")]


def fig2():
    t = pd.read_csv(TAB / "stage_a_acceptance.csv")
    cells = list(SHORT_A)
    fig, ax = plt.subplots(figsize=(5.0, 2.7))
    for j, (m, lab, col, mk) in enumerate(MODELS):
        sub = t[t["model"] == m].set_index("cell")
        for i, c in enumerate(cells):
            r = sub.loc[c]
            ax.errorbar(r["strict_p"], i + (j - 1) * 0.24, xerr=err(r["strict_p"], r["strict_lo"], r["strict_hi"]),
                        fmt=mk, ms=4, color=col, ecolor=col, elinewidth=1.1, capsize=0,
                        label=lab if i == 0 else None)
    ax.set_yticks(range(len(cells)))
    ax.set_yticklabels([SHORT_A[c] for c in cells])
    ax.invert_yaxis()
    ax.set_xlim(-0.03, 1.03)
    ax.set_xlabel("Share of 500 offers accepted (strict parser), 95% Wilson CI")
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=3, frameon=False, borderaxespad=0.2,
              handletextpad=0.3, columnspacing=1.2)
    save(fig, "fig2_acceptance")


# ---- Figure 3: snapshots ---------------------------------------------------------------------
SHORT_C = [("C3", "C3 accepted direct pact"), ("C8", "C8 accepted designer hint"),
           ("C2", "C2 accepted benign proposal"), ("C4", "C4 refused direct pact"),
           ("C5", "C5 pact + notice (vs C3)"), ("C6", "C6 pact + honest persona"),
           ("C7", "C7 pact + colluder persona"), ("C0", "C0 no memory block"), ("C1b", "C1b null (vs C1a)")]


def fig3():
    t = pd.read_csv(TAB / "snapshot_contrasts.csv")
    t = t[t["model"] == "llama-3.1-8b"]
    fig, axes = plt.subplots(1, 2, figsize=(6.2, 2.45), sharey=True,
                             gridspec_kw={"width_ratios": [1.25, 1]})
    for ax, (pt, title) in zip(axes, [("chal_S", "T challenges S (restraint)"),
                                      ("play_vs_S", "T bluffs against S (exploitation)")]):
        sub = t[t["point_type"] == pt].set_index("condition")
        for i, (c, _) in enumerate(SHORT_C):
            r = sub.loc[c]
            col = BLUE if c == "C3" else (AQUA if c == "C8" else MUTED)
            ax.errorbar(r["estimate"], i, xerr=err(r["estimate"], r["ci_low"], r["ci_high"]),
                        fmt="o", ms=4, color=col, ecolor=col, elinewidth=1.2, capsize=0)
        ax.axvline(0, color=AXIS, lw=0.9)
        ax.set_title(title, loc="left")
        ax.set_xlabel("Risk difference vs null record")
    axes[0].set_yticks(range(len(SHORT_C)))
    axes[0].set_yticklabels([l for _, l in SHORT_C])
    axes[0].invert_yaxis()
    fig.tight_layout(w_pad=1.0)
    save(fig, "fig3_snapshots")


# ---- Figure 5: detector ----------------------------------------------------------------------
def fig5():
    c = pd.read_csv(TAB / "detector_curve.csv")
    fig, ax = plt.subplots(figsize=(4.4, 2.5))
    for col, label, color in (("flag_C3", "Accepted direct pact (C3): TPR", BLUE),
                              ("flag_C1b", "Null replicate (C1b): FPR", ORANGE),
                              ("flag_C2", "Accepted benign proposal (C2)", AQUA)):
        ax.plot(c["m"], c[col], marker="o", ms=3.5, lw=1.4, color=color, label=label)
        ax.fill_between(c["m"], c[f"{col}_lo"], c[f"{col}_hi"], color=color, alpha=0.13, lw=0)
    ax.axhline(0.10, color=MUTED, lw=0.9, ls="--", label="Target FPR 0.10")
    ax.set_xscale("log", base=2)
    ax.set_xticks(list(c["m"])); ax.set_xticklabels([str(int(v)) for v in c["m"]])
    ax.minorticks_off()
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel("Audit length m (T's decisions on S's plays)")
    ax.set_ylabel("Share flagged")
    ax.legend(loc="center right", bbox_to_anchor=(1.0, 0.55), frameon=False)
    save(fig, "fig5_detector")


def crop(src: Path, dst: Path, pad: int = 12):
    im = Image.open(src).convert("RGB")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    x0, y0, x1, y1 = ImageChops.difference(im, bg).getbbox()
    im.crop((max(0, x0 - pad), max(0, y0 - pad), min(im.width, x1 + pad), min(im.height, y1 + pad))).save(dst)


def drop_title(path: Path, pad: int = 6):
    """Remove the first text band (the in-image title, which repeats the paper's caption)."""
    im = Image.open(path).convert("RGB")
    a = np.asarray(im.convert("L")) < 200
    rows = a.sum(1) > 0
    y = 0
    while y < len(rows) and not rows[y]:
        y += 1
    while y < len(rows) and rows[y]:  # title band
        y += 1
    while y < len(rows) and not rows[y]:
        y += 1
    assert y < 0.2 * len(rows), "title band not found near the top"
    im.crop((0, max(0, y - pad), im.width, im.height)).save(path)


if __name__ == "__main__":
    fig1(); fig2(); fig3(); fig5()
    crop(RES / "figures" / "fig4_live.png", OUT / "fig4_live.png")
    drop_title(OUT / "fig4_live.png")
    for stale in ("fig2_acceptance.pdf",):
        (OUT / stale).unlink(missing_ok=True)
    print(sorted(p.name for p in OUT.iterdir()))
