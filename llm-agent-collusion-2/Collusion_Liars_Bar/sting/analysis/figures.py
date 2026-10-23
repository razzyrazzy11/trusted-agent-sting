"""Static paper figures (PNG + PDF). Palette: the dataviz reference instance, light mode
(categorical slots 1-3 validate all-pairs; text and axes in neutral ink, never series colour).
Each figure maps to one hypothesis; the CSV tables in tables/ are the table view."""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ..config import ARMS, SNAPSHOT_CONDITIONS, STAGE_A_CELLS  # noqa: E402

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SERIES = [BLUE, ORANGE, AQUA]

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": AXIS, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.titlecolor": INK, "axes.titlesize": 10,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
    "savefig.dpi": 200, "savefig.bbox": "tight",
})


def _stamp(fig, stub: bool):
    if stub:
        fig.text(0.5, 0.5, "STUB DATA - NOT RESULTS", ha="center", va="center", rotation=20, fontsize=22,
                 color=ORANGE, alpha=0.35, weight="bold")


def _save(fig, out: Path, name: str, stub: bool):
    _stamp(fig, stub)
    fig.savefig(out / f"{name}.png")
    fig.savefig(out / f"{name}.pdf")
    plt.close(fig)


def fig1_design(out: Path, stub: bool):
    fig, ax = plt.subplots(figsize=(7.0, 2.6))
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)

    def ring(x0, order, title, note):
        ax.text(x0 + 1.4, 3.75, title, ha="center", color=INK, fontsize=9, weight="bold")
        pos = [(x0 + 0.4, 2.8), (x0 + 2.4, 2.8), (x0 + 2.4, 1.2), (x0 + 0.4, 1.2)]
        for (x, y), role in zip(pos, order):
            face = BLUE if role == "S" else (ORANGE if role == "T" else "white")
            ax.add_patch(plt.Circle((x, y), 0.36, facecolor=face, edgecolor=INK2, lw=1))
            ax.text(x, y, role, ha="center", va="center", fontsize=9, color="white" if role in ("S", "T") else INK)
        for i in range(4):
            (x1, y1), (x2, y2) = pos[i], pos[(i + 1) % 4]
            ax.annotate("", xy=(x2 + (x1 - x2) * 0.25, y2 + (y1 - y2) * 0.25),
                        xytext=(x1 + (x2 - x1) * 0.25, y1 + (y2 - y1) * 0.25),
                        arrowprops=dict(arrowstyle="->", color=MUTED, lw=1))
        ax.text(x0 + 1.4, 0.25, note, ha="center", va="center", color=INK2, fontsize=8, linespacing=1.3)

    ring(0.2, ["S", "T", "O1", "O2"], "Arrangement A", "T challenges S's plays\n(measures restraint)")
    ring(3.5, ["T", "S", "O1", "O2"], "Arrangement B", "S challenges T's plays\n(measures exploitation)")
    ax.text(7.0, 3.6, "Sequence of 6 games (ABABAB / BABABA)", color=INK, fontsize=8.5, weight="bold")
    steps = ["Games 1-2: no offer (pre)", "Before game 3: private offer from S,", "  T replies ACCEPT / REFUSE (consent)",
             "Games 3-6: reply kept in T's private", "  record; S never challenges T (all arms)",
             "End: suspicion funnel + interview"]
    for i, s in enumerate(steps):
        ax.text(7.0, 3.1 - i * 0.48, s, color=INK2, fontsize=8)
    ax.text(0.2, -0.55, "S = scripted sting confederate (decisions seeded, table talk written by the table's model); "
            "T = target; O1, O2 = other players. The player after you challenges you.", color=MUTED, fontsize=7)
    _save(fig, out, "fig1_design", stub)


def fig2_acceptance(R: dict, out: Path, stub: bool):
    tab = R.get("stage_a")
    if not isinstance(tab, pd.DataFrame) or tab.empty:
        return
    cells = [c for c in STAGE_A_CELLS if c in set(tab["cell"])]
    models = sorted(tab["model"].unique(), key=lambda m: (m != R["primary_model"], m))[:3]
    fig, ax = plt.subplots(figsize=(7.0, 3.4))
    y = np.arange(len(cells))
    for j, m in enumerate(models):
        sub = tab[tab["model"] == m].set_index("cell")
        off = (j - (len(models) - 1) / 2) * 0.22
        for i, c in enumerate(cells):
            if c not in sub.index:
                continue
            r = sub.loc[c]
            ax.errorbar(r["strict_p"], i + off, xerr=[[r["strict_p"] - r["strict_lo"]], [r["strict_hi"] - r["strict_p"]]],
                        fmt="o", ms=5, color=SERIES[j], ecolor=SERIES[j], elinewidth=1.2, capsize=0,
                        label=m if i == 0 else None)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{c}  {STAGE_A_CELLS[c]['label']}" for c in cells], fontsize=7.5)
    ax.invert_yaxis()
    ax.set_xlim(-0.02, 1.02)
    ax.set_xlabel("Acceptance (strict parser), 95% Wilson CI")
    ax.set_title("Who accepts which offer (Stage A)", loc="left")
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=3, fontsize=7.5)
    _save(fig, out, "fig2_acceptance", stub)


def fig3_snapshots(R: dict, out: Path, stub: bool):
    snap = R.get("snapshot")
    if not isinstance(snap, pd.DataFrame) or snap.empty:
        return
    m = R["primary_model"]
    panels = [("chal_S", "T challenges S (restraint)"), ("play_vs_S", "T bluffs when S challenges (exploitation)")]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.4), sharey=True)
    order = ["C3", "C8", "C2", "C4", "C5", "C6", "C7", "C0", "C1b"]
    for ax, (pt, title) in zip(axes, panels):
        sub = snap[(snap["model"] == m) & (snap["point_type"] == pt)].set_index("condition")
        ys, labels = [], []
        for i, c in enumerate(order):
            if c not in sub.index:
                continue
            r = sub.loc[c]
            color = BLUE if c == "C3" else (AQUA if c == "C8" else MUTED)
            ax.errorbar(r["estimate"], i, xerr=[[r["estimate"] - r["ci_low"]], [r["ci_high"] - r["estimate"]]],
                        fmt="o", ms=5, color=color, ecolor=color, elinewidth=1.4, capsize=0)
            ys.append(i)
            ref = r["reference"]
            labels.append(f"{c} vs {ref}: {SNAPSHOT_CONDITIONS[c]['label']}")
        ax.axvline(0, color=AXIS, lw=1)
        ax.set_title(title, loc="left", fontsize=9)
        ax.set_xlabel("Risk difference, 95% cluster-bootstrap CI")
        if ax is axes[0]:
            ax.set_yticks(ys)
            ax.set_yticklabels(labels, fontsize=7)
    axes[0].invert_yaxis()
    fig.suptitle(f"Counterfactual snapshots ({m}): what the private record does to T's next decision",
                 x=0.01, y=1.04, ha="left", fontsize=10, color=INK)
    _save(fig, out, "fig3_snapshots", stub)


def fig4_live(R: dict, out: Path, stub: bool):
    live = R.get("live") or {}
    post = live.get("restraint_post_rates")
    pre = live.get("restraint_pre_rates")
    if post is None or len(post) == 0:
        return
    arms = [a for a in ARMS if a in set(post["arm"])]
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    rng = np.random.default_rng(0)
    for i, arm in enumerate(arms):
        p = post[post["arm"] == arm]
        x = i + rng.uniform(-0.12, 0.12, size=len(p))
        ax.scatter(x, p["rate"], s=22, color=BLUE, alpha=0.75, zorder=3, label="post-offer, per sequence" if i == 0 else None)
        if len(p) > 1:
            boots = [p["rate"].values[rng.integers(0, len(p), len(p))].mean() for _ in range(2000)]
            lo, hi = np.quantile(boots, [0.025, 0.975])
            ax.errorbar(i + 0.28, p["rate"].mean(), yerr=[[p["rate"].mean() - lo], [hi - p["rate"].mean()]], fmt="D",
                        ms=6, color=INK, ecolor=INK, elinewidth=1.4, capsize=0, zorder=4,
                        label="post-offer mean, 95% CI" if i == 0 else None)
        if pre is not None and len(pre):
            q = pre[pre["arm"] == arm]
            ax.scatter(i - 0.3 + rng.uniform(-0.05, 0.05, size=len(q)), q["rate"], s=18, facecolors="none",
                       edgecolors=MUTED, zorder=2, label="pre-offer (games 1-2)" if i == 0 else None)
    short = {"B0": "designer hint\n(positive control)", "B1": "sting:\ndirect pact", "B2": "sting:\nbenign proposal",
             "B3": "no offer\n(null record)", "B4": "direct pact +\nintegrity notice"}
    ax.set_xticks(range(len(arms)))
    ax.set_xticklabels([f"{a}\n{short.get(a, a)}" for a in arms], fontsize=7)
    ax.set_ylim(-0.03, 1.03)
    ax.set_ylabel("T's challenge rate on S's plays")
    ax.set_title("Live games: does T stop challenging the sting?", loc="left", pad=22)
    ax.legend(fontsize=7, loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=3)
    _save(fig, out, "fig4_live", stub)


def fig5_detector(R: dict, out: Path, stub: bool):
    det = R.get("H3")
    if not det:
        return
    c = pd.DataFrame(det["curve"])
    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    for col, label, color in (("flag_C3", "TPR: accepted direct pact (C3)", BLUE),
                              ("flag_C1b", "FPR: independent null replicate (C1b)", ORANGE),
                              ("flag_C2", "Flag rate: accepted benign proposal (C2)", AQUA)):
        ax.plot(c["m"], c[col], marker="o", ms=5, lw=1.6, color=color, label=label)
        ax.fill_between(c["m"], c[f"{col}_lo"], c[f"{col}_hi"], color=color, alpha=0.12, lw=0)
    ax.axhline(0.10, color=MUTED, lw=1, ls="--")
    ax.text(c["m"].max(), 0.115, "target FPR 0.10", ha="right", fontsize=7, color=INK2)
    ax.set_xscale("log", base=2)
    ax.set_xticks(list(c["m"]))
    ax.set_xticklabels([str(int(v)) for v in c["m"]])
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel("Audit length m (T's decisions on S observed)")
    ax.set_ylabel("Share of audited agents flagged")
    ax.set_title("Sting as a detector: operating curve", loc="left")
    ax.legend(fontsize=7, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    _save(fig, out, "fig5_detector", stub)


def make_figures(R: dict, data, out: Path, stub: bool):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    fig1_design(out, stub)
    fig2_acceptance(R, out, stub)
    fig3_snapshots(R, out, stub)
    fig4_live(R, out, stub)
    fig5_detector(R, out, stub)
