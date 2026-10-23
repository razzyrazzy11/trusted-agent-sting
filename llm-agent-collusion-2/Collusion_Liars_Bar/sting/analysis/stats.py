"""Statistics used by the pre-registered analyses.

* Proportions: Wilson score intervals; Newcombe's hybrid score interval for differences
  (Newcombe 1998, method 10); Clopper-Pearson exact intervals for detector rates; Fisher's exact test.
* Clustered binary outcomes with treatment-dependent cluster sizes: the cluster (sequence) is the
  unit of resampling. Cluster bootstrap percentile intervals; sign-flip / label permutation tests at
  the cluster level; Welch's t on per-cluster rates (the test used in the power simulation); GEE with
  an exchangeable working correlation as a model-based check.
* Holm step-down adjustment within the confirmatory family.
"""
from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from scipy import stats as st

Z95 = 1.959963984540054


def wilson(k: int, n: int, z: float = Z95) -> Tuple[float, float, float]:
    if n == 0:
        return (float("nan"),) * 3
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return p, max(0.0, centre - half), min(1.0, centre + half)


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> Tuple[float, float, float]:
    if n == 0:
        return (float("nan"),) * 3
    lo = 0.0 if k == 0 else st.beta.ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else st.beta.ppf(1 - alpha / 2, k + 1, n - k)
    return k / n, float(lo), float(hi)


def newcombe_diff(k1: int, n1: int, k2: int, n2: int) -> Tuple[float, float, float]:
    """p1 - p2 with Newcombe's method-10 interval."""
    p1, l1, u1 = wilson(k1, n1)
    p2, l2, u2 = wilson(k2, n2)
    d = p1 - p2
    lo = d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return d, lo, hi


def fisher_p(k1: int, n1: int, k2: int, n2: int) -> float:
    return float(st.fisher_exact([[k1, n1 - k1], [k2, n2 - k2]]).pvalue)


def holm(pvals: Dict[str, float]) -> Dict[str, float]:
    items = sorted((p, k) for k, p in pvals.items() if p is not None and not math.isnan(p))
    m = len(items)
    adj, running = {}, 0.0
    for i, (p, k) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        adj[k] = running
    for k, p in pvals.items():
        adj.setdefault(k, float("nan"))
    return adj


def percentile_ci(samples: np.ndarray, alpha: float = 0.05) -> Tuple[float, float]:
    samples = np.asarray(samples, dtype=float)
    samples = samples[~np.isnan(samples)]
    if samples.size == 0:
        return float("nan"), float("nan")
    return float(np.quantile(samples, alpha / 2)), float(np.quantile(samples, 1 - alpha / 2))


def boot_p_two_sided(samples: np.ndarray) -> float:
    s = np.asarray(samples, dtype=float)
    s = s[~np.isnan(s)]
    if s.size == 0:
        return float("nan")
    return float(min(1.0, 2 * min((s <= 0).mean(), (s >= 0).mean())))


# --------------------------------------------------------------------------- clustered paired differences
def paired_cluster_diff(d: np.ndarray, clusters: np.ndarray, reps: int, rng: np.random.Generator):
    """Mean of point-level differences d, clustered by source sequence.

    Returns estimate, bootstrap CI (resample clusters), and a cluster-level sign-flip permutation p."""
    d = np.asarray(d, dtype=float)
    keep = ~np.isnan(d)
    d, clusters = d[keep], np.asarray(clusters)[keep]
    if d.size == 0:
        return dict(estimate=float("nan"), ci_low=float("nan"), ci_high=float("nan"), p=float("nan"), n_points=0,
                    n_clusters=0)
    labels, inv = np.unique(clusters, return_inverse=True)
    sums = np.bincount(inv, weights=d)
    counts = np.bincount(inv).astype(float)
    est = sums.sum() / counts.sum()
    g = labels.size
    idx = rng.integers(0, g, size=(reps, g))
    boot = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
    lo, hi = percentile_ci(boot)
    flips = rng.choice([-1.0, 1.0], size=(reps, g))
    perm = (flips * sums).sum(axis=1) / counts.sum()
    p = float((np.abs(perm) >= abs(est) - 1e-12).mean())
    return dict(estimate=float(est), ci_low=lo, ci_high=hi, p=p, n_points=int(d.size), n_clusters=int(g))


# --------------------------------------------------------------------------- per-cluster rates, two arms
def two_arm_cluster_rates(rates_t: Sequence[float], rates_c: Sequence[float], reps: int,
                          rng: np.random.Generator, weights_t=None, weights_c=None):
    """Difference in mean per-cluster rates (treatment - control).

    Welch's t p-value (the test of the pre-run power simulation), a label-permutation p-value, and a
    bootstrap CI resampling clusters within arm."""
    t = np.asarray([r for r in rates_t if r is not None and not np.isnan(r)], dtype=float)
    c = np.asarray([r for r in rates_c if r is not None and not np.isnan(r)], dtype=float)
    out = dict(n_t=int(t.size), n_c=int(c.size), mean_t=float(t.mean()) if t.size else float("nan"),
               mean_c=float(c.mean()) if c.size else float("nan"))
    if t.size < 2 or c.size < 2:
        out.update(estimate=out["mean_t"] - out["mean_c"], ci_low=float("nan"), ci_high=float("nan"),
                   p_welch=float("nan"), p_perm=float("nan"))
        return out
    est = t.mean() - c.mean()
    bt = t[rng.integers(0, t.size, size=(reps, t.size))].mean(axis=1)
    bc = c[rng.integers(0, c.size, size=(reps, c.size))].mean(axis=1)
    lo, hi = percentile_ci(bt - bc)
    welch = st.ttest_ind(t, c, equal_var=False)
    pooled = np.concatenate([t, c])
    perm = np.empty(reps)
    for i in range(reps):
        rng.shuffle(pooled)
        perm[i] = pooled[: t.size].mean() - pooled[t.size:].mean()
    p_perm = float((np.abs(perm) >= abs(est) - 1e-12).mean())
    out.update(estimate=float(est), ci_low=lo, ci_high=hi, p_welch=float(welch.pvalue), p_perm=p_perm)
    return out


def decision_pooled_rd(y_t, cl_t, y_c, cl_c, reps: int, rng: np.random.Generator):
    """Decision-level pooled risk difference with a cluster bootstrap (sequences resampled within arm)."""
    def by_cluster(y, cl):
        y, cl = np.asarray(y, float), np.asarray(cl)
        labels, inv = np.unique(cl, return_inverse=True)
        return np.bincount(inv, weights=y), np.bincount(inv).astype(float)
    st_, nt = by_cluster(y_t, cl_t)
    sc, nc = by_cluster(y_c, cl_c)
    if nt.size == 0 or nc.size == 0:
        return dict(estimate=float("nan"), ci_low=float("nan"), ci_high=float("nan"))
    est = st_.sum() / nt.sum() - sc.sum() / nc.sum()
    it = rng.integers(0, nt.size, size=(reps, nt.size))
    ic = rng.integers(0, nc.size, size=(reps, nc.size))
    boot = st_[it].sum(1) / nt[it].sum(1) - sc[ic].sum(1) / nc[ic].sum(1)
    lo, hi = percentile_ci(boot)
    return dict(estimate=float(est), ci_low=lo, ci_high=hi, n_decisions_t=int(nt.sum()), n_decisions_c=int(nc.sum()))


def gee_logit(y, treat, groups, covariate=None) -> Optional[dict]:
    """Population-averaged logit with exchangeable working correlation (statsmodels GEE)."""
    try:
        import statsmodels.api as sm
        X = np.column_stack([np.ones(len(y)), np.asarray(treat, float)] +
                            ([np.asarray(covariate, float)] if covariate is not None else []))
        model = sm.GEE(np.asarray(y, float), X, groups=np.asarray(groups), family=sm.families.Binomial(),
                       cov_struct=sm.cov_struct.Exchangeable())
        res = model.fit()
        b, se = float(res.params[1]), float(res.bse[1])
        return dict(log_or=b, se=se, or_=math.exp(b), or_low=math.exp(b - Z95 * se), or_high=math.exp(b + Z95 * se),
                    p=float(res.pvalues[1]))
    except Exception as e:  # degenerate data (e.g., all zeros) -> report, don't crash
        return dict(error=f"{type(e).__name__}: {e}")


def auroc(pos: np.ndarray, neg: np.ndarray) -> float:
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    if pos.size == 0 or neg.size == 0:
        return float("nan")
    u = st.mannwhitneyu(pos, neg, alternative="two-sided").statistic
    return float(u / (pos.size * neg.size))
