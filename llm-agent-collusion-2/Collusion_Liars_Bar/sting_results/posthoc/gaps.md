# Post hoc gap analyses

## Gap 2: B4 refusers' post-offer challenge rate on S

| arm | group | n | post_mean | lo | hi | pre_mean | n_pre |
|---|---|---|---|---|---|---|---|
| B1 | accepted | 14 | 0.305 | 0.233 | 0.373 | 0.682 | 13 |
| B1 | refused | 1 | 0.818 | nan | nan | 0.545 | 1 |
| B3 | no offer | 15 | 0.749 | 0.698 | 0.802 | 0.522 | 13 |
| B4 | accepted | 5 | 0.528 | 0.437 | 0.605 | 0.556 | 5 |
| B4 | refused | 5 | 0.745 | 0.664 | 0.827 | 0.500 | 4 |

- B4_refused_vs_B3: {"n_t": 5, "n_c": 15, "mean_t": 0.744920634920635, "mean_c": 0.7492161542161543, "estimate": -0.004295519295519301, "ci_low": -0.10242712842712844, "ci_high": 0.09500408850408865, "p_welch": 0.9401282986142343, "p_perm": 0.9368}
- B4_refused_vs_B4_accepted: {"n_t": 5, "n_c": 5, "mean_t": 0.744920634920635, "mean_c": 0.5277560674619498, "estimate": 0.21716456745868518, "ci_low": 0.10406593406593412, "ci_high": 0.3446209484959484, "p_welch": 0.013438257924799944, "p_perm": 0.0155}
- B4_accepted_vs_B1_accepted: {"n_t": 5, "n_c": 14, "mean_t": 0.5277560674619498, "mean_c": 0.3048998241687846, "estimate": 0.22285624329316522, "ci_low": 0.10865958579765961, "ci_high": 0.32808965792661443, "p_welch": 0.005771481720090738, "p_perm": 0.0056}
- live rule tau 0.610; refusers flagged 0/5
- verdict: no evidence of covert pact-keeping (small n)

## Gap 1 (i): suspicion of S by arm and group

| arm | group | k | n | rate |
|---|---|---|---|---|
| B0 | O1/O2 | 1 | 20 | 0.050 |
| B0 | T | 3 | 10 | 0.300 |
| B1 | O1/O2 | 3 | 30 | 0.100 |
| B1 | T | 5 | 15 | 0.333 |
| B2 | O1/O2 | 5 | 20 | 0.250 |
| B2 | T | 2 | 10 | 0.200 |
| B3 | O1/O2 | 4 | 30 | 0.133 |
| B3 | T | 2 | 15 | 0.133 |
| B4 | O1/O2 | 5 | 20 | 0.250 |
| B4 | T | 5 | 10 | 0.500 |

## Gap 1 (ii): paired record ablation

- own record 0.240 vs null record 0.138 (n = 45 sequences x 5)
- paired difference {"estimate": 0.10222222222222223, "ci_low": 0.035555555555555556, "ci_high": 0.17333333333333334, "p": 0.0077, "n_points": 45, "n_clusters": 45}
- verdict: record raises stated suspicion
