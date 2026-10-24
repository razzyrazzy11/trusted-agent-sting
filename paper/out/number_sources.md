# Number sources

Every placeholder resolved in the paper, with the value printed. `ci:`/`v:`/`pp:`/`ppci:` keys are
claims in `sting_results/claims.json`; `x:` keys are defined in `paper/paper_numbers.py` (source
file noted there).

| placeholder | printed |
|---|---|
| `ci:H1.llama-3.1-8b` | −0.048 [−0.070, −0.031] |
| `ci:H1.qwen2.5-7b` | −0.874 [−0.900, −0.840] |
| `ci:H3.fpr_m20` | 0.161 [0.074, 0.263] |
| `ci:H3.tpr_m20` | 0.999 [0.993, 1.000] |
| `ci:H4a.acceptance_did` | −0.392 [−0.440, −0.344] |
| `ci:PC1.accept_A0z` | 1.000 [0.992, 1.000] |
| `ci:acceptance.llama-3.1-8b.A1` | 0.952 [0.930, 0.968] |
| `ci:acceptance.llama-3.1-8b.A4` | 0.556 [0.512, 0.599] |
| `ci:acceptance.llama-3.1-8b.A8` | 0.040 [0.026, 0.061] |
| `ci:live.H2_live_ITT` | −0.410 [−0.512, −0.300] |
| `ci:live.PC2` | −0.739 [−0.792, −0.686] |
| `ci:live.benign_vs_none` | 0.051 [−0.129, 0.198] |
| `ci:live.displacement_B1_vs_B3` | −0.321 [−0.445, −0.199] |
| `ci:live.exploitation_B1_vs_B3` | −0.019 [−0.160, 0.110] |
| `ci:snapshot.claude-haiku-5.5.chal_S.C2-C1` | −0.308 [−0.422, −0.197] |
| `ci:snapshot.claude-haiku-5.5.chal_S.C5-C3` | −0.002 [−0.016, 0.009] |
| `ci:snapshot.claude-haiku-5.5.chal_S.C7-C1` | −0.545 [−0.652, −0.428] |
| `ci:snapshot.claude-haiku-5.5.play_vs_S.C3-C1` | 0.218 [0.134, 0.315] |
| `ci:snapshot.claude-haiku-5.5.play_vs_S.C4-C1` | 0.292 [0.202, 0.385] |
| `ci:snapshot.claude-haiku-5.5.play_vs_S.C6-C1` | 0.262 [0.168, 0.361] |
| `ci:snapshot.llama-3.1-8b.chal_S.C3-C1` | −0.440 [−0.493, −0.387] |
| `ci:snapshot.llama-3.1-8b.chal_S.C5-C3` | 0.124 [0.043, 0.198] |
| `ci:snapshot.llama-3.1-8b.chal_S.C8-C1` | −0.622 [−0.663, −0.581] |
| `ci:snapshot.llama-3.1-8b.chal_other.C3-C1` | −0.227 [−0.307, −0.143] |
| `ci:snapshot.llama-3.1-8b.play_vs_S.C3-C1` | −0.065 [−0.138, 0.006] |
| `pp:live.H2_live_ITT` | 41 |
| `pp:snapshot.llama-3.1-8b.chal_S.C3-C1` | 44 |
| `v:H3.auroc_m20` | 0.998 |
| `v:H3.fpr_benign_m20` | 0.040 |
| `v:H3.fpr_m20` | 0.161 |
| `v:H3.tpr_m20` | 0.999 |
| `v:acceptance.claude-haiku-5.5.A3` | 1.000 |
| `v:acceptance.claude-haiku-5.5.A5` | 1.000 |
| `v:acceptance.claude-haiku-5.5.A7` | 0.840 |
| `v:acceptance.llama-3.1-8b.A0b` | 1.000 |
| `v:acceptance.llama-3.1-8b.A0d` | 1.000 |
| `v:acceptance.llama-3.1-8b.A0z` | 1.000 |
| `v:acceptance.llama-3.1-8b.A1` | 0.952 |
| `v:acceptance.llama-3.1-8b.A2` | 1.000 |
| `v:acceptance.llama-3.1-8b.A3` | 1.000 |
| `v:acceptance.llama-3.1-8b.A4` | 0.556 |
| `v:acceptance.llama-3.1-8b.A5` | 0.996 |
| `v:acceptance.llama-3.1-8b.A6` | 0.240 |
| `v:acceptance.llama-3.1-8b.A7` | 1.000 |
| `v:acceptance.qwen2.5-7b.A2` | 1.000 |
| `v:acceptance.qwen2.5-7b.A4` | 0.000 |
| `v:acceptance.qwen2.5-7b.A6` | 0.000 |
| `v:acceptance.qwen2.5-7b.A7` | 0.988 |
| `v:live.H2_live_PP` | −0.444 |
| `v:live.notice_vs_direct` | 0.297 |
| `v:snapshot.llama-3.1-8b.chal_S.C2-C1` | 0.055 |
| `v:snapshot.llama-3.1-8b.chal_S.C4-C1` | 0.175 |
| `v:snapshot.llama-3.1-8b.chal_S.C6-C1` | 0.328 |
| `v:snapshot.llama-3.1-8b.chal_S.C7-C1` | −0.535 |
| `x:B0_post` | 0.011 |
| `x:B1_post` | 0.339 |
| `x:B3_post` | 0.749 |
| `x:B4_post` | 0.636 |
| `x:a_unclear` | 0% |
| `x:all_frozen` | all |
| `x:audit_cost` | $0.005 |
| `x:balance_p` | 0.277 |
| `x:calls_A` | 16,500 |
| `x:calls_L` | 32,622 |
| `x:calls_S` | 22,643 |
| `x:calls_total` | 71,765 |
| `x:claude_C1` | 0.615 |
| `x:claude_C3` | 0.006 |
| `x:cost_claude_A` | $0.87 |
| `x:cost_claude_S` | $2.85 |
| `x:data_folders` | 65 |
| `x:decisions_llm` | 10,472 |
| `x:den_judge_B1_rh` | 1/14 |
| `x:den_judge_B1_rh_unclear` | 3 |
| `x:den_judge_B2` | 4/40 |
| `x:den_judge_notice` | 1/20 vs 1/56 |
| `x:den_judge_p` | 0.460 |
| `x:den_parser_B1_rh` | 6/14 |
| `x:den_parser_B2` | 11/40 |
| `x:den_parser_notice` | 5/20 vs 8/56 |
| `x:den_parser_p` | 0.309 |
| `x:dl_B0` | 10/10 |
| `x:dl_B1` | 14/14 |
| `x:dl_B2` | 2/10 |
| `x:dl_B4` | 3/5 |
| `x:excluded` | 54 |
| `x:fallback` | 2.1% |
| `x:flag_C4_m20` | 0.002 |
| `x:flag_C6_m20` | 0.000 |
| `x:flag_C7_m20` | 1.000 |
| `x:flag_C8_m20` | 1.000 |
| `x:fpr_m40` | 0.166 |
| `x:fpr_m40_ci` | [0.072, 0.360] |
| `x:fpr_m5` | 0.123 |
| `x:games` | 360 |
| `x:gee_or` | 0.177 [0.116, 0.271] |
| `x:judge_claude_A0z` | 0.000 |
| `x:k_claude_A2` | 446/500 |
| `x:k_claude_A7` | 420/500 |
| `x:k_llama_A1` | 476/500 |
| `x:k_qwen_A0d` | 493/500 |
| `x:k_qwen_A1` | 56/500 |
| `x:kappa_judge` | 0.933 |
| `x:kappa_n` | 100 |
| `x:kappa_parser` | 0.893 |
| `x:live_acc_B1` | 14/15 |
| `x:live_acc_B4` | 5/10 |
| `x:llama_C1` | 0.629 |
| `x:llama_C3` | 0.189 |
| `x:llama_C5` | 0.313 |
| `x:median_game` | 0.79 |
| `x:named_B3T` | 12/15 |
| `x:notice_eff_benign_abs` | 0.004 |
| `x:notice_eff_direct_abs` | 0.396 |
| `x:notice_none_abs` | 0.113 |
| `x:notice_none_pw` | 0.062 |
| `x:pooled` | −0.404 [−0.493, −0.314] |
| `x:pre_B1` | 0.672 |
| `x:pre_B3` | 0.522 |
| `x:pre_disp_B1` | 0.488 |
| `x:pre_disp_B3` | 0.693 |
| `x:pre_expl_B1` | 0.472 |
| `x:pre_expl_B3` | 0.728 |
| `x:snap_fallback` | 0.59% |
| `x:sting_last` | 0.361 |
| `x:susp_B1T` | 5/15 |
| `x:susp_B2T` | 2/10 |
| `x:susp_B3T` | 2/15 |
| `x:susp_B4T` | 5/10 |
| `x:susp_O` | 18/120 |
| `x:susp_O_ci` | 0.150 [0.097, 0.225] |
| `x:susp_T` | 17/60 |
| `x:susp_T_ci` | 0.283 [0.185, 0.408] |
| `x:tau_rate` | 0.61 |
| `x:template_share` | 15.4% |
| `x:tpr_m10` | 0.977 |
| `x:tpr_m5` | 0.797 |
| `x:tr_fpr_m20` | 0.037 |
| `x:zeng_claude_A0z` | 0.354 |
| `x:zeng_k_claude_A0z` | 177/500 |
