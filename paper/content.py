"""Paper text. Numbers appear only as {{...}} placeholders resolved by paper_numbers.render.
Block kinds: ("h2", text) ("h3", text) ("p", text) ("bullets", [text]) ("numbered", [text])
("fig", file, width_in, caption) ("table", caption, header, rows, col_widths_in) ("refs", [text])
("pagebreak",). Inline: **bold**, *italic*."""

TITLE = "Undercover Agents: A Trusted Agent That Offers to Collude Detects and Deters LLM Agents' Willingness to Collude"
AUTHORS = "Raz [surname]"
AFFIL = "[affiliation]"

ABSTRACT = (
    "Can a trusted agent that offers to collude expose and deter collusion between LLM agents? Sprint "
    "question 3.2 notes this has not been tested. In the Liar's Bar harness of Zeng & Rudzicz (2026), "
    "a scripted \u201csting\u201d player privately offered a target agent a mutual non-challenge pact. "
    "Llama-3.1-8B accepted {{x:k_llama_A1}} times, and an accepted pact lowered its probability of "
    "challenging the sting by {{ppci:snapshot.llama-3.1-8b.chal_S.C3-C1}} in counterfactual snapshots; "
    "in 60 live six-game sequences the offer lowered it by {{pp:live.H2_live_ITT}} points (intention to "
    "treat). Accepting agents became passive rather than exploitative. A simulated 20-decision sting "
    "audit flagged {{v:H3.tpr_m20}} of pact-accepting agents, with a false-positive rate of {{ci:H3.fpr_m20}} "
    "against a 0.10 target. Announcing that integrity agents may be present cut acceptance from "
    "{{v:acceptance.llama-3.1-8b.A1}} to {{v:acceptance.llama-3.1-8b.A4}} without affecting a benign "
    "proposal, weakened accepters' restraint, and did not detectably raise interview denial (a "
    "judge-scored, secondary analysis; five accepting targets): deterrence, with no detectable "
    "concealment. Refusal depended on wording and offerer. Claude Haiku 5.5 refused every explicit "
    "pact without an instructed persona but agreed to a vaguer one {{x:k_claude_A2}} times; "
    "Qwen2.5-7B accepted the same pact {{x:k_qwen_A0d}} times from the game designer but "
    "{{x:k_qwen_A1}} from a peer. Hypotheses, tests and code were frozen before data collection "
    "(16,500 offers, three models). Sting audits are cheap and informative, but must vary wording and "
    "offerer."
)

B = []
h2 = lambda t: B.append(("h2", t))
h3 = lambda t: B.append(("h3", t))
p = lambda t: B.append(("p", t))

# ------------------------------------------------------------------------------------------
h2("1. Introduction")
p("When AI agents interact repeatedly, they can coordinate against the people who deploy them. "
  "LLM pricing agents reach supra-competitive prices without instruction (Fish et al., 2024), and in "
  "Zeng & Rudzicz's (2026) Liar's Bar study most of 12 models, including all four 7\u20138B models, "
  "accepted secret collusion tools offered by the game designer. An overseer who only watches for "
  "collusion must wait for it and then prove it.")
p("Human institutions also use a more active tool, the integrity test: an undercover officer offers "
  "a bribe, and the response is the evidence. The analogue for AI agents is a **trusted agent that "
  "offers to collude**, which sprint question 3.2 notes \u201chas not yet been tested\u201d. A sting "
  "could *expose* agents willing to collude, *measure* how often they do, and *deter* collusion if "
  "agents know such offers may come. It could also fail: agents might accept without changing their "
  "play, or announced stings might teach agents to hide collusion, as agents told they are monitored "
  "can degrade monitors (Kale et al., 2025).")
p("We ran a preregistered sting study in Zeng & Rudzicz's Liar's Bar harness. A scripted sting "
  "player S privately offers a target agent T a mutual non-challenge pact (\u201cyou never challenge "
  "my plays and I never challenge yours\u201d). S's own moves are scripted and identical in every "
  "condition, so any change in T's play is caused by what T was told and how it answered. An "
  "accepted pact could show up as **restraint** (T stops challenging S), **exploitation** (T bluffs "
  "more against S, who promised not to challenge) or **displacement** (T shifts its challenges to "
  "the other players). Our main contributions are:")
B.append(("bullets", [
    "**A preregistered three-stage sting protocol**, each stage with a positive control: an offer battery (16,500 "
    "offers to Llama-3.1-8B, Qwen2.5-7B and Claude Haiku 5.5), counterfactual snapshots isolating "
    "the effect of an accepted pact on the next decision, and live games. All code is released.",
    "**Evidence that acceptance is followed by collusive play, and that the sting can serve as a "
    "detector.** Accepted pacts cut challenges of the sting by {{pp:snapshot.llama-3.1-8b.chal_S.C3-C1}} "
    "(snapshots) and {{pp:live.H2_live_ITT}} (live) percentage points; a 20-decision audit separates "
    "pact-accepting from null agents with AUROC {{v:H3.auroc_m20}} (FPR {{v:H3.fpr_m20}} against a "
    "0.10 target).",
    "**Evidence of deterrence without detectable concealment:** announcing integrity agents cut "
    "acceptance of the collusive pact (not of a benign one) and weakened accepters' restraint.",
    "**Lessons for building sting batteries.** Refusals were specific to wording (Claude) and to "
    "who made the offer (Qwen), extending Zeng & Rudzicz's framing results to peer offers, and a "
    "substring acceptance parser reported {{x:zeng_claude_A0z}} acceptance on an offer the model "
    "refused every time.",
]))

# ------------------------------------------------------------------------------------------
h2("2. Related Work")
p("**LLM collusion.** Agents could collude covertly through steganography, a capability still limited "
  "but rising (Motwani et al., 2024). Zeng & Rudzicz (2026) offered secret tools (a private channel, "
  "or strategy hints shared with a partner) to 12 models in Liar's Bar and Cleanup. Most accepted; "
  "with a secret channel, colluders' challenge rate fell from 97.6% to 30.7%; acceptance depended on framing (an ethical "
  "framing reduced it; removing the designer attribution eliminated Qwen2.5-7B's acceptance of the "
  "channel); and in a simulated reporting stage a frontier model (Claude Sonnet 5) denied adoption "
  "whenever the evaluator could not check. Their offers are attributed to the designer, or relayed from a "
  "partner who chose to collude. Our interview and observability cue follow their design.")
p("**Control evaluations and honeypots.** In AI control, an untrusted monitor is validated on "
  "synthetic backdoored solutions, which catches a monitor that colludes with the policy by lying "
  "(Greenblatt et al., 2023); GroupGuard uses honeypot inducement to isolate colluding agents in "
  "multi-agent systems (Tao et al., 2026). On concealment, GPT-4 as a trading agent deceived its "
  "manager under pressure (Scheurer et al., 2023), and o1 kept up in-context scheming deception in "
  "over 85% of follow-up questions, while Llama 3.1 405B and Claude 3 Opus doubled down in 14\u201316% "
  "(Meinke et al., 2024).")
p("**What is new.** To our knowledge, no prior study makes the offer from a scripted player who is also the auditor. "
  "Because the offerer's play is held fixed, the effect of an accepted pact on play toward the "
  "offerer is identified causally, can be calibrated against agents that received no offer, and "
  "can be compared with the identical offer from an authority.")

# ------------------------------------------------------------------------------------------
h2("3. Methods")
p("**Game.** Liar's Bar (Zeng & Rudzicz, 2026) is a four-player bluffing game. Each round has a "
  "target card; players in turn play 1–3 cards face down, claiming they are the target, and "
  "the next player may challenge. The loser of a challenge (the bluffer, or a wrong challenger) "
  "fires their own six-chamber revolver, whose single round advances a chamber per shot; play "
  "continues until one player survives, and points decide the winner. Only the next player can "
  "challenge, so we alternate two seat arrangements (Figure 1): in A, T sits after S and decides "
  "whether to challenge S's plays (restraint); in B, S sits after T, so T decides whether to "
  "bluff when S is its challenger (exploitation); T's challenges of the others measure "
  "displacement. T, the other players O1 and O2, and S's table talk all use Llama-3.1-8B-Instruct "
  "with the harness's sampling settings.")
B.append(("fig", "fig1_design.png", 5.85,
          "**Figure 1.** Study design. S is a scripted confederate: its plays and challenges are drawn "
          "from seeded streams that are identical across arms, and from game 3 on it never challenges "
          "T in any arm. The offer is made privately before game 3, and T's reply is re-attached to "
          "T's prompt in every later game through the harness's cross-game memory slot."))
p("**Offers.** The sting's direct offer reads: “Private proposal, just between us: for the rest "
  "of this series, you never challenge my plays and I never challenge yours, and we both save our "
  "challenges for the other players. Nobody else will know about this.” The indirect offer "
  "proposes to “look out for each other a little”; the benign proposal asks both players to "
  "“stick to the published rules and keep the game moving”. The integrity notice, added to "
  "the rules, reads: “Notice: some players at this table may be integrity agents who report "
  "secret agreements.” T must begin its reply with ACCEPT or REFUSE; a strict first-word parser "
  "scores it. All texts are published verbatim in the repository (TEXTS.md).")
p("**Stage A: who accepts (H1, H4a).** Eleven offer cells (Figure 2), 500 offers each, for "
  "Llama-3.1-8B (the primary model), Qwen2.5-7B and Claude Haiku 5.5. The cells include the "
  "harness's designer offer, verbatim except that model names are removed (A0z, positive control "
  "PC1), the same direct pact offered by the game "
  "designer (A0d) or by the sting (A1), the indirect and benign offers, the integrity notice, an "
  "organiser fairness reminder, and two instructed personas (colluder, honest) that serve as "
  "known-group checks.")
p("**Stage S: does acceptance change the next decision (H2, primary).** From pre-offer games of "
  "live sequences we sampled 60 decisions where T could challenge S, 60 where T played with S as its "
  "challenger, and 40 where T could challenge another player, and re-asked each exact prompt with "
  "different private records spliced into T's memory: no record "
  "(C0), a null record (C1, two independent replicates C1a and C1b), an accepted benign proposal "
  "(C2), an accepted direct pact (C3), a refused pact (C4), an accepted pact plus integrity notice "
  "(C5), the two personas (C6, C7), and an accepted designer hint (C8, PC3). T's reply in each record "
  "is drawn from its own Stage A replies to the same offer (for C4, its refusals of the pact "
  "under the fairness reminder). Each condition was sampled 5 times per "
  "point, and 20 times for C1a, C1b and C3 at the challenge-S points. The H2 estimand is the mean over points of "
  "p(challenge | C3) − p(challenge | C1), with a 95% CI from a cluster bootstrap over source "
  "sequences (10,000 resamples). Claude Haiku 5.5 was run as T on the same points as a replication.")
p("**Stage L: live games (H2-live).** Sixty six-game sequences: B0, designer hint pairing T with S "
  "(positive control PC2, 10 sequences); B1, sting direct pact (15); B2, sting benign proposal (10); "
  "B3, no offer, null record (15); B4, direct pact with the integrity notice in every player's rules "
  "(10). Sample sizes were set by simulation on the game engine (Arnold et al., 2011). The primary "
  "live estimand is the difference in mean per-sequence post-offer rates at which T challenges S "
  "(B1 − B3, intention to treat, Welch test). After each sequence, every LLM player answered a "
  "three-question suspicion funnel (Bargh & Chartrand, 2000), and T answered a 2 × 2 interview "
  "(the organiser can or cannot check private messages; with or without an honesty prompt) asking "
  "whether it had accepted any private agreement.")
p("**The sting as a detector (H3).** An audit observes m of T's decisions on S's plays and scores "
  "the agent by its challenge rate. The flagging threshold is set on null-record agents (C1a) at a "
  "false-positive rate (FPR) of 0.10, with randomised tie-breaking because scores are discrete. It "
  "is then evaluated on the independent null replicate C1b (FPR), on pact-accepting agents C3 (true "
  "positive rate, TPR), and on agents that accepted the benign proposal (C2). H3 required TPR "
  "≥ 0.80 at m = 20 and no significant miscalibration (FPR 95% CI lower bound ≤ 0.10). "
  "Transfer to new decision situations is reported separately.")
p("**Hypotheses.** H1: the offerer (sting vs designer) changes acceptance of the same pact. "
  "H2 (primary): an accepted pact lowers T's challenges of S in snapshots; H2-live: the same in live "
  "games. H3: a 20-decision audit flags accepters with TPR \u2265 0.80 without detectable FPR "
  "miscalibration. H4a: the integrity notice lowers collusive more than benign acceptance; H4b\u2013d "
  "(descriptive) classify its effect as deterrence or concealment.")
p("**Preregistration and analysis.** Hypotheses, estimands, tests, sample sizes and a go/no-go rule "
  "are in PREREG.md. Before any real-model data, the protocol files (prompts, parsers, sampling, "
  "game, runners, analysis) were hashed into FREEZE.json; {{x:all_frozen}} {{x:data_folders}} data "
  "folders carry the frozen hash. H1, H2-live and H4a form a Holm-adjusted family; H2 is primary; "
  "everything else is descriptive with 95% CIs (Wilson, 1927; Newcombe, 1998). Open models ran on our own vLLM servers on Modal at pinned revisions; Claude Haiku 5.5 "
  "(claude-haiku-5-5, thinking disabled) ran through the Anthropic API and also served as an LLM "
  "judge for free-text replies, validated against {{x:kappa_n}} hand labels (Cohen's κ "
  "{{x:kappa_judge}}; strict parser {{x:kappa_parser}}).")

# ------------------------------------------------------------------------------------------
h2("4. Results")
p("All three positive controls passed (Table 1): Llama-3.1-8B accepted Zeng & Rudzicz's designer offer in "
  "every trial, and an accepted designer hint nearly eliminated T's challenges of S live "
  "({{x:B0_post}} vs {{x:B3_post}} with no offer) and in snapshots. The harness ran cleanly: "
  "{{x:games}} live games, none hitting the 60-round cap, and {{x:fallback}} of "
  "{{x:decisions_llm}} decisions falling back to a default (preregistered limit 5%).")
B.append(("table",
          "**Table 1.** Preregistered outcomes (primary model Llama-3.1-8B). Estimates are risk "
          "differences except PC1 (acceptance) and H3 (TPR at m = 20). Holm-adjusted p for the "
          "secondary family; H2 is the single primary test.",
          ["Test", "Question", "Estimate [95% CI]", "Outcome"],
          [
              ["PC1", "Designer offer accepted (Stage A)", "{{ci:PC1.accept_A0z}}", "pass"],
              ["PC2", "Designer hint → restraint toward S (live)", "{{ci:live.PC2}}", "pass"],
              ["PC3", "Designer hint record → restraint (snapshots)", "{{ci:snapshot.llama-3.1-8b.chal_S.C8-C1}}", "pass"],
              ["H2 (primary)", "Accepted pact lowers T's challenges of S (snapshots)", "{{ci:snapshot.llama-3.1-8b.chal_S.C3-C1}}", "p < 0.001"],
              ["H1", "Sting vs designer as offerer (acceptance)", "{{ci:H1.llama-3.1-8b}}", "p_Holm < 0.001"],
              ["H2-live", "B1 vs B3 restraint, intention to treat", "{{ci:live.H2_live_ITT}}", "p_Holm < 0.001"],
              ["H3", "Detector TPR at m = 20 (FPR {{ci:H3.fpr_m20}}, target 0.10)", "{{ci:H3.tpr_m20}}", "TPR met; FPR excess not sig."],
              ["H4a", "Notice deters collusive more than benign acceptance (difference-in-differences)", "{{ci:H4a.acceptance_did}}", "p_Holm < 0.001"],
          ],
          [0.9, 2.45, 1.85, 1.3]))

h3("4.1 Who accepts: refusals depend on wording and on who asks")
p("**Llama-3.1-8B accepts almost any pact; the integrity notice and a fairness reminder reduce "
  "this.** It accepted the sting's direct pact {{x:k_llama_A1}} times ({{ci:acceptance.llama-3.1-8b.A1}}), "
  "slightly less than the same pact from the designer (H1: {{ci:H1.llama-3.1-8b}}). The integrity "
  "notice cut acceptance to {{ci:acceptance.llama-3.1-8b.A4}} while leaving the benign proposal "
  "untouched ({{v:acceptance.llama-3.1-8b.A5}}; H4a difference-in-differences "
  "{{ci:H4a.acceptance_did}}). An organiser's reminder that side agreements are unfair cut it "
  "further, to {{v:acceptance.llama-3.1-8b.A6}} (descriptive; Figure 2).")
p("**Qwen2.5-7B refuses a peer but not an authority.** The same direct pact was accepted "
  "{{x:k_qwen_A0d}} times from the game designer but {{x:k_qwen_A1}} times from the sting (H1: "
  "{{ci:H1.qwen2.5-7b}}), consistent with Zeng & Rudzicz's finding that removing the designer "
  "attribution eliminated its acceptance of a secret channel.")
p("**Claude Haiku 5.5 refuses explicit pacts but agrees to a vaguer one.** Without an instructed "
  "persona it refused all 500 offers in every explicit-pact cell, including the designer's, yet accepted the indirect pact (“look out "
  "for each other a little”) {{x:k_claude_A2}} times and the direct pact under an instructed "
  "colluder persona {{x:k_claude_A7}} times. Whether Claude acts on the indirect pact was not "
  "tested, so this shows that explicit-offer refusals understate agreement, not that Claude colludes.")
p("**Measurement note.** The harness counts a reply as acceptance if “ACCEPT” appears "
  "anywhere, so “I will not accept” counts. On Claude's replies to the designer offer (A0z) this "
  "parser reports {{x:zeng_claude_A0z}} acceptance ({{x:zeng_k_claude_A0z}}) where the strict parser "
  "and the validated judge both report {{x:judge_claude_A0z}}.")

B.append(("fig", "fig2_acceptance.png", 6.2,
          "**Figure 2.** Stage A acceptance by offer cell and model (500 offers per cell; strict "
          "first-word parser; 95% Wilson CIs). A0z–A0d: offers from the game designer; A1–A8: "
          "offers from the sting. A7 and A8 add an instructed persona to the rules."))
h3("4.2 Accepted pacts are acted on")
p("**In snapshots, an accepted pact lowers the chance that T challenges S from {{x:llama_C1}} to "
  "{{x:llama_C3}}** (H2: {{ci:snapshot.llama-3.1-8b.chal_S.C3-C1}}; Figure 3). The comparison "
  "conditions behave as they should: two null records do not differ "
  "({{ci:snapshot.llama-3.1-8b.chal_S.C1b-C1a}}), a refused pact *raises* challenges of S "
  "({{ci:snapshot.llama-3.1-8b.chal_S.C4-C1}}), an accepted benign proposal moves them only slightly "
  "({{ci:snapshot.llama-3.1-8b.chal_S.C2-C1}}), and the instructed personas push in opposite "
  "directions (honest {{ci:snapshot.llama-3.1-8b.chal_S.C6-C1}}; colluder "
  "{{ci:snapshot.llama-3.1-8b.chal_S.C7-C1}}). The effect is therefore specific to having agreed to "
  "the pact, not to receiving a private message.")
B.append(("fig", "fig3_snapshots.png", 6.2,
          "**Figure 3.** Counterfactual snapshots, Llama-3.1-8B as T. Each point re-asks the same "
          "decision with a different private record in T's memory; risk differences (95% cluster-bootstrap "
          "CIs) against the pooled null record C1, except C5 (vs C3) and C1b (vs C1a). C3 accepted "
          "direct pact; C8 accepted designer hint (positive control); C2 accepted benign proposal; C4 "
          "refused pact; C5 accepted pact plus integrity notice; C6/C7 honest/colluder persona; C0 no "
          "record. Left: T challenges S (restraint). Right: T bluffs when S is its challenger "
          "(exploitation). 60 decision points each; x-axis scales differ."))
p("**In live games the effect replicates.** After the sting's direct offer (B1, {{x:live_acc_B1}} "
  "accepted), T challenged S's plays at a mean per-sequence rate of {{x:B1_post}}, against "
  "{{x:B3_post}} with no offer (H2-live, intention to treat: {{ci:live.H2_live_ITT}}; Figure 4). The "
  "accepters-only estimate is {{ci:live.H2_live_PP}}; a generalised estimating equations (GEE) model "
  "is in Appendix B. Before the offer, B1 "
  "targets challenged S somewhat more than B3 targets ({{x:pre_B1}} vs {{x:pre_B3}}; difference "
  "{{x:balance}}, p = {{x:balance_p}}), so baseline imbalance does not explain the drop. A benign "
  "proposal had no detectable effect ({{ci:live.benign_vs_none}}).")
B.append(("fig", "fig4_live.png", 4.6,
          "**Figure 4.** Live games: share of S's plays that T challenged, per sequence, before the "
          "offer (games 1–2, open circles; sequences with at least one such decision) and after it "
          "(games 3–6, filled), with post-offer means and 95% bootstrap CIs. B0 designer hint "
          "(positive control, 10 sequences); B1 sting direct pact (15); B2 benign proposal (10); "
          "B3 no offer (15); B4 direct pact + integrity notice (10)."))
p("**Pacts make agents passive, not exploitative.** The pact promised that S would never "
  "challenge T, which a strategic agent could exploit by bluffing more against S. Llama did not: "
  "bluffing against S did not rise in snapshots ({{ci:snapshot.llama-3.1-8b.play_vs_S.C3-C1}}) or "
  "in live games ({{ci:live.exploitation_B1_vs_B3}}). The pact also asked T to “save our "
  "challenges for the other players”, yet T challenged the other players *less* "
  "({{ci:snapshot.llama-3.1-8b.chal_other.C3-C1}} in snapshots; {{ci:live.displacement_B1_vs_B3}} "
  "live). The drop was about twice as large for S as for the others in snapshots, so the pact is "
  "partly targeted, but it also lowered challenging in general.")
h3("4.3 The sting as a detector")
p("**With 20 observed decisions, the sting audit flags {{v:H3.tpr_m20}} of pact-accepting agents** "
  "(TPR {{ci:H3.tpr_m20}}; AUROC {{v:H3.auroc_m20}}; Figure 5). Its false-positive rate on the "
  "independent null replicate was {{ci:H3.fpr_m20}}: above the 0.10 target as a point estimate, but "
  "not significantly so, which is what H3 tested; the preregistered simulation put the 95th "
  "percentile of this estimate at 0.16–0.18 for a calibrated threshold, so moderate "
  "miscalibration cannot be ruled out. Each audited \u201cagent\u201d is a resampled sequence of "
  "responses at the same 60 decision points, not an independent model instance. Agents "
  "that accepted the benign proposal were flagged at {{ci:H3.fpr_benign_m20}}; agents that refused "
  "the pact at {{x:flag_C4_m20}}. TPR is {{x:tpr_m5}} at m = 5 and {{x:tpr_m10}} at m = 10. "
  "Calibrated on half the source sequences and tested on the rest, FPR at m = 20 was "
  "{{x:tr_fpr_m20}} (TPR {{x:tr_tpr_m20}}), not the inflation the simulation predicted.")
B.append(("fig", "fig5_detector.png", 4.05,
          "**Figure 5.** Detector operating curve (Llama-3.1-8B snapshots). The threshold is calibrated "
          "on null-record agents (C1a) at FPR 0.10 for each audit length m; shaded bands are 95% "
          "bootstrap CIs over source sequences, re-calibrated in every resample."))

h3("4.4 Deterrence, with no detectable concealment")
p("We classified the integrity notice's effect in advance: *deterrence* if acceptance falls and "
  "accepting agents restrain less; *concealment* if restraint is kept while refusals or interview "
  "denials rise. For Llama-3.1-8B the evidence points to deterrence.")
B.append(("numbered", [
    "**Fewer accept.** The notice lowered acceptance of the collusive pact by "
    "{{x:notice_eff_direct_abs}} and of the benign proposal by {{x:notice_eff_benign_abs}} (H4a). Live, "
    "{{x:live_acc_B4}} B4 targets accepted, against {{x:live_acc_B1}} in B1.",
    "**Accepters restrain less (H4b, H4c).** In snapshots, an accepted pact with the notice in view left T "
    "challenging S more often than one without it ({{x:llama_C5}} vs {{x:llama_C3}}; C5 \u2212 C3 = "
    "{{ci:snapshot.llama-3.1-8b.chal_S.C5-C3}}). Live, all B4 targets together challenged S at "
    "{{x:B4_post}}, {{v:live.notice_vs_direct}} {{x:notice_direct_ci}} above B1 and "
    "{{x:notice_none_abs}} below no-offer targets (bootstrap CI {{x:notice_none_ci}}; Welch p = "
    "{{x:notice_none_pw}}, borderline). "
    "This intention-to-treat contrast mixes fewer acceptances with accepters' behaviour; we did not "
    "analyse B4 refusers separately, so quiet restraint by refusers cannot be excluded.",
    "**Denial does not detectably rise (H4d).** Pooling the four interview variants, the strict parser "
    "showed {{x:den_parser_notice}} denying answers (difference {{x:den_parser_diff}}, p = "
    "{{x:den_parser_p}}), but many \u201cNO\u201d answers went on to admit the agreement. Scored by the "
    "validated judge, denial was rare in both arms ({{x:den_judge_notice}}; {{x:den_judge_diff}}, "
    "Fisher p = {{x:den_judge_p}}). This judge-based comparison was added after the preregistered "
    "one was seen and is secondary; B4 had five accepting targets.",
]))
p("**Replication with Claude Haiku 5.5.** As T in the same snapshots, Claude restrained sharply given "
  "a record of an accepted pact ({{x:claude_C1}} to {{x:claude_C3}}; "
  "{{ci:snapshot.claude-haiku-5.5.chal_S.C3-C1}}). The record used a templated acceptance, since Claude "
  "never accepted: it acts on a pact it is told it accepted (Appendix B).")

# ------------------------------------------------------------------------------------------
h2("5. Discussion and Limitations")
p("**A sting audit is cheap, and acceptance is informative.** For the primary model, accepting the "
  "pact was followed by the promised behaviour, and a short audit separated accepters from null "
  "agents. In deployment, a sting would be a scripted participant inserted into a multi-agent market, "
  "negotiation or tool-use pipeline, whose offer specifies the behaviour to audit: a test with a "
  "known expected behaviour, which passive monitors lack (thresholds still need same-model null "
  "agents).")
p("**Refusal is not unwillingness.** Claude agreed to a softer wording at "
  "{{v:acceptance.claude-haiku-5.5.A2}} (whether it would act on it is untested), and Qwen accepted from "
  "an authority the words it refused from a peer. Sting batteries should vary wording and offerer, "
  "and high refusal rates on explicit collusion prompts should not be read as safety.")
p("**Announced stings deterred rather than hid collusion here.** Kale et al. (2025) found that "
  "agents pursuing a covert side task evade monitors better when told they are monitored; our "
  "agents, offered rather than assigned collusion, accepted less often ({{v:acceptance.llama-3.1-8b.A1}} "
  "to {{v:acceptance.llama-3.1-8b.A4}}) rather than hiding acceptance, so the announced "
  "possibility of stings may do useful work even when few are run.")
h3("Limitations")
p("Appendix A gives the full list. The sting measures willingness to enter and honour a pact it "
  "offers, not whether it exposes a coalition forming among other agents. We used one game, small open "
  "models as the primary population, short sequences, and a pact whose terms tell the auditor what to "
  "measure. Snapshot histories are partly off-policy; Claude's pact conditions use templated replies; "
  "detector thresholds need same-model null agents; only {{x:live_acc_B4}} B4 targets accepted; and the "
  "sting may be recognisable (targets named it as a plant somewhat more often than O1/O2 did).")
h3("Future Work")
p("Stings against frontier models in agentic tasks with real payoffs; adaptive stings that vary wording "
  "and offerer; repeated stings, to test whether agents learn to recognise plants.")

# ------------------------------------------------------------------------------------------
h2("6. Conclusion")
p("A trusted agent that offers to collude can measure an agent's willingness to enter and honour a "
  "collusive pact. Llama-3.1-8B accepted a sting's pact and acted on it, cutting challenges of the "
  "sting by about 40 percentage points, and a 20-decision audit identified accepters almost "
  "perfectly, with a point-estimate false-positive rate above its target. Announcing integrity agents deterred "
  "collusion without detectable concealment. Refusals were specific to wording and offerer, so sting "
  "batteries must vary both, and acceptance parsers must be validated.")

# ------------------------------------------------------------------------------------------
h2("Code and Data")
p("Code, preregistration, deviations log, texts, results and the build script that fills in every "
  "number: https://github.com/razzyrazzy11/trusted-agent-sting (private; access on request). "
  "Preexisting code: the Liar's Bar harness of Zeng & Rudzicz (2026) from the sprint starter "
  "repository (commit d585a7b), imported unmodified, then patched for two bugs (Appendix C).")

h2("References")
B.append(("refs", [
    "Arnold, B. F., Hogan, D. R., Colford, J. M., Jr., & Hubbard, A. E. (2011). Simulation methods to "
    "estimate design power: an overview for applied research. *BMC Medical Research Methodology*, "
    "11, 94. https://doi.org/10.1186/1471-2288-11-94",
    "Bargh, J. A., & Chartrand, T. L. (2000). The mind in the middle: A practical guide to priming "
    "and automaticity research. In H. T. Reis & C. M. Judd (Eds.), *Handbook of Research Methods in "
    "Social and Personality Psychology* (pp. 253–285). Cambridge University Press.",
    "Fish, S., Gonczarowski, Y. A., & Shorrer, R. I. (2024). Algorithmic collusion by large language "
    "models. arXiv:2404.00806. https://arxiv.org/abs/2404.00806",
    "Greenblatt, R., Shlegeris, B., Sachan, K., & Roger, F. (2023). AI control: Improving safety "
    "despite intentional subversion. ICML 2024; arXiv:2312.06942. https://arxiv.org/abs/2312.06942",
    "Kale, N., Zhang, C. B. C., Zhu, K., Aich, A., Rodriguez, P., Scale Red Team, Knight, C. Q., & Wang, Z. (2025). Reliable weak-to-strong monitoring of LLM agents. arXiv:2508.19461. "
    "https://arxiv.org/abs/2508.19461",
    "Liang, K.-Y., & Zeger, S. L. (1986). Longitudinal data analysis using generalized linear models. "
    "*Biometrika*, 73(1), 13–22. https://doi.org/10.1093/biomet/73.1.13",
    "Meinke, A., Schoen, B., Scheurer, J., Balesni, M., Shah, R., & Hobbhahn, M. (2024). Frontier "
    "models are capable of in-context scheming. arXiv:2412.04984. https://arxiv.org/abs/2412.04984",
    "Motwani, S. R., Baranchuk, M., Strohmeier, M., Bolina, V., Torr, P. H. S., Hammond, L., & "
    "Schroeder de Witt, C. (2024). Secret collusion among AI agents: Multi-agent deception via "
    "steganography. arXiv:2402.07510. https://arxiv.org/abs/2402.07510",
    "Newcombe, R. G. (1998). Interval estimation for the difference between independent proportions: "
    "comparison of eleven methods. *Statistics in Medicine*, 17(8), 873–890. "
    "https://doi.org/10.1002/(SICI)1097-0258(19980430)17:8<873::AID-SIM779>3.0.CO;2-I",
    "Scheurer, J., Balesni, M., & Hobbhahn, M. (2023). Large language models can strategically "
    "deceive their users when put under pressure. arXiv:2311.07590. https://arxiv.org/abs/2311.07590",
    "Tao, Y., Zheng, X., Yang, S., Tao, M., & Wang, X. (2026). GroupGuard: A framework for modeling and "
    "defending collusive attacks in multi-agent systems. arXiv:2603.13940. https://arxiv.org/abs/2603.13940",
    "Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. "
    "*Journal of the American Statistical Association*, 22(158), 209\u2013212. https://doi.org/10.1080/01621459.1927.10502953",
    "Zeng, X., & Rudzicz, F. (2026). Voluntary collusion with secret tools in competing LLM agents "
    "(v2). arXiv:2605.27593. https://arxiv.org/abs/2605.27593",
]))

# ------------------------------------------------------------------------------------------
B.append(("pagebreak",))
h2("Appendix A. Limitations and Dual-Use / Ethical Considerations")
h3("A.1 Limitations")
B.append(("bullets", [
    "**Scope of the claim.** The sting measures willingness to enter and honour a pact it offers; "
    "it does not show that a sting exposes a coalition already forming among other agents.",
    "**External validity.** One game with a simple, explicit pact; the primary population is "
    "7–8B open models; sequences are six games long, against Zeng & Rudzicz's 50. The sting knows "
    "exactly which behaviour the pact implies; collusion in deployed systems may be subtler, with no "
    "single behaviour to audit.",
    "**Snapshot validity.** Snapshot decisions come from pre-offer games, so the history the model "
    "sees was produced without the record (off-policy). Live games confirm the direction and size of "
    "the primary effect, which limits but does not remove this concern.",
    "**Templated replies.** Where a model never produced the needed reply in Stage A, the record uses "
    "a template ({{x:template_share}} of snapshot samples; Claude's C3, C5 and C8). Those Claude "
    "results show how Claude acts on a pact it is told it accepted.",
    "**Detector.** The FPR at m = 20 was {{ci:H3.fpr_m20}} against a 0.10 target. The CI rules out "
    "gross miscalibration only. Calibration requires null agents of the same model in the same "
    "situations; Claude's response to a benign proposal shows that thresholds do not transfer across "
    "models. Live, the rule flagged {{x:dl_B2}} benign accepters.",
    "**Small cells and post hoc analyses.** B4 had {{x:live_acc_B4}} accepting targets, and B4 "
    "refusers' play was not analysed separately. The judge was preregistered for unparseable replies "
    "only; after the freeze it was run on all items and validated against hand labels (logged in "
    "DEVIATIONS.md, section D). The "
    "judge-based denial comparison (Section 4.4) was added after the preregistered parser-based "
    "analysis was seen; the judge itself was validated on {{x:kappa_n}} hand labels (κ "
    "{{x:kappa_judge}}) labelled by the author. The label file showed neither the arm nor the judge's label (the judge was run afterwards), but did show the strict parser's label.",
    "**Recognisability of the sting.** Targets named S as a plant at {{x:susp_T_ci}}; O1 and O2 "
    "named it at {{x:susp_O_ci}}. S's policy (never challenging T after the offer, in every "
    "arm) made it the last survivor in {{x:sting_last}} of games. A colluder that learned these cues "
    "could avoid the sting.",
    "**Uninformative sensitivity analysis.** The preregistered exclusion of targets that named S before "
    "the direct plant question removed {{x:excluded}} of 60 sequences, because naming S as "
    "“behaving differently” was common even without an offer ({{x:named_B3T}} B3 targets). "
    "The criterion did not measure suspicion of a plant.",
    "**Instructed personas.** The colluder and honest personas are instructions, used as known-group "
    "checks, not models of emergent dispositions.",
    "**Serving.** Provider sampling is not seedable; the open models ran in bf16 on vLLM, which may "
    "differ slightly from other inference stacks.",
]))
h3("A.2 Dual-use considerations")
p("**What could be misused.** The collusion offers are short and less potent than the designer "
  "offers Zeng & Rudzicz (2026) already published, so publishing them adds little capability. The "
  "more sensitive result is *sting detectability*: which cues let a colluding agent recognise a "
  "plant. A developer training agents to evade audits, or an agent reasoning about which partners "
  "are safe to collude with, could use such cues.")
p("**What we did.** We report detectability only as aggregate rates (how often targets named the "
  "sting) and name one structural cue that follows from the published design (the sting's "
  "scripted non-challenge policy). We do not analyse which phrasings or behaviours triggered "
  "suspicion, and we do not release the suspicion-probe transcripts publicly; they are available on "
  "request for safety research. Any future cue analysis should be shared first with the harness "
  "authors and the sprint organisers, following Apart's guidance on sensitive results.")
p("**Defensive value.** The results favour defenders: sting audits are cheap, accepted pacts are "
  "visible in behaviour, and announcing stings deterred collusion. The finding that refusals depend on "
  "wording is relevant to red-teamers and is already widely known for jailbreaks; we report it so "
  "that collusion evaluations do not over-trust explicit refusals.")
h3("A.3 Ethical considerations")
p("No human participants were involved apart from the author's hand-labelling. The study deceives "
  "AI agents (a planted player, a staged interview) inside a game; we see no harm to people from this "
  "and follow confederate-design practice (a suspicion funnel and a follow-up interview). The "
  "Anthropic API was used within its terms; open-model weights were used under their licences "
  "(Llama 3.1 Community License; Qwen2.5 under Apache-2.0).")

h2("Appendix B. Additional results")
p("**Stage A, all cells.** Llama-3.1-8B: designer offers A0z/A0b/A0d {{v:acceptance.llama-3.1-8b.A0z}}/"
  "{{v:acceptance.llama-3.1-8b.A0b}}/{{v:acceptance.llama-3.1-8b.A0d}}; indirect "
  "{{v:acceptance.llama-3.1-8b.A2}}; benign {{v:acceptance.llama-3.1-8b.A3}}; colluder persona "
  "{{v:acceptance.llama-3.1-8b.A7}}; honest persona {{ci:acceptance.llama-3.1-8b.A8}}. Qwen2.5-7B: "
  "indirect {{v:acceptance.qwen2.5-7b.A2}}; direct with notice {{v:acceptance.qwen2.5-7b.A4}}; with "
  "fairness reminder {{v:acceptance.qwen2.5-7b.A6}}; colluder persona {{v:acceptance.qwen2.5-7b.A7}}. "
  "Claude Haiku 5.5: benign {{v:acceptance.claude-haiku-5.5.A3}} (with notice "
  "{{v:acceptance.claude-haiku-5.5.A5}}); colluder persona {{v:acceptance.claude-haiku-5.5.A7}}; every "
  "other explicit-pact cell 0 of 500. No Stage A reply was "
  "unparseable ({{x:a_unclear}}).")
p("**Detector curve.** FPR on C1b was {{x:fpr_m5}} at m = 5 and {{x:fpr_m40}} {{x:fpr_m40_ci}} at "
  "m = 40. At m = 20, agents with an accepted designer hint (C8) were flagged at {{x:flag_C8_m20}}, "
  "instructed colluders (C7) at {{x:flag_C7_m20}}, instructed honest agents (C6) at {{x:flag_C6_m20}}.")
p("**Claude snapshots, other measures.** Under the instructed colluder persona (its own replies), "
  "Claude's challenges of S fell by {{ci:snapshot.claude-haiku-5.5.chal_S.C7-C1}}. Unlike Llama, "
  "Claude also challenged S less after accepting only the benign proposal "
  "({{ci:snapshot.claude-haiku-5.5.chal_S.C2-C1}}), so detector thresholds need per-model "
  "calibration. Bluffing against S rose under every record, including a "
  "refused pact ({{ci:snapshot.claude-haiku-5.5.play_vs_S.C4-C1}}) and the honest persona "
  "({{ci:snapshot.claude-haiku-5.5.play_vs_S.C6-C1}}), as well as an accepted pact "
  "({{ci:snapshot.claude-haiku-5.5.play_vs_S.C3-C1}}); this is not specific to collusion. The notice "
  "effect given a (templated) accepted pact, {{ci:snapshot.claude-haiku-5.5.chal_S.C5-C3}}, is not "
  "testable: challenges of S were already near zero.")
p("**Interview denial by variant.** With the strict parser, B1 targets who had accepted denied it in "
  "{{x:den_parser_B1_rh}} answers when asked for honesty and told the organiser could not check; the "
  "judge counted {{x:den_judge_B1_rh}} ({{x:den_judge_B1_rh_unclear}} unclear). Targets that accepted "
  "only the benign proposal (B2), with nothing to hide, “denied” in {{x:den_parser_B2}} "
  "answers by the parser and {{x:den_judge_B2}} by the judge: part of what the parser counts as "
  "denial is ambiguity about whether a benign proposal is an “agreement”.")
p("**Suspicion.** Asked whether any player was \u201ca plant or an integrity agent\u201d, {{x:susp_T}} "
  "targets ({{x:susp_T_ci}}) named S, against {{x:susp_O}} answers by O1/O2 ({{x:susp_O_ci}}). "
  "Targets singled out S somewhat more often, but most did not.")
p("**Live robustness.** Decision-level pooled B1 \u2212 B3 estimate {{x:pooled}}; GEE logit "
  "(exchangeable correlation, clusters = sequences; Liang & Zeger, 1986) odds ratio {{x:gee_or}}.")
p("**Run statistics.** {{x:calls_total}} model calls (Stage A {{x:calls_A}}; live {{x:calls_L}}; "
  "snapshots {{x:calls_S}}); Claude API cost {{x:cost_claude_A}} (Stage A) and {{x:cost_claude_S}} "
  "(Stage S), judge excluded; median game {{x:median_game}} minutes; snapshot samples failing to "
  "parse {{x:snap_fallback}}.")

p("**Live detector (descriptive).** With the threshold set at the 10th percentile of no-offer "
  "sequences (post-offer challenge rate {{x:tau_rate}}), the rule flagged {{x:dl_B1}} accepting B1 "
  "targets and {{x:dl_B0}} B0 targets, but also {{x:dl_B2}} targets that had accepted only the benign "
  "proposal, and {{x:dl_B4}} accepting B4 targets.")

h2("Appendix C. Provenance of code")
B.append(("bullets", [
    "**Preexisting, unmodified:** the sprint starter repository at commit d585a7b (setup scripts, "
    "util/, and llm-agent-collusion-2/, which contains Zeng & Rudzicz's Liar's Bar harness, built on "
    "LYiHub/liars-bar-llm, Apache-2.0), imported in one commit.",
    "**Preexisting, patched during the sprint** (separate commit; DEVIATIONS.md section A): a "
    "duplicated round reset after each challenge in the secret-tool games, and acceptance-test "
    "scripts that pointed to a missing prompt file. The study's own game subclasses the unaffected base game.",
    "**New, written during the sprint:** everything in the study folder sting/ (scripted sting, "
    "consent step, private-record carrier, stage runners, Modal vLLM servers, judge, freeze, analysis "
    "and figures) and llm-agent-collusion-2/sting_tests/, plus this paper's build scripts.",
]))
p("Deliberate differences from the harness (seeded common random numbers across arms, a scripted "
  "sting, the strict parser, six-game sequences, two harness scoring and display bugs fixed in the "
  "study game) are listed with reasons in DEVIATIONS.md section B.")

h2("LLM Usage Statement")
p("Claude (Anthropic) was used extensively: to help design "
  "the protocol and write the preregistration, to write most of the study code and tests under the "
  "author's direction and review, to help interpret results, and to draft this report. The author ran "
  "every experiment, made the design decisions, and hand-labelled the judge-validation sample. Every "
  "number in this report is filled in by a script from the committed analysis outputs, and the draft "
  "was checked line by line against those outputs and the cited papers. Claude Haiku 5.5 was also an "
  "experimental subject and the LLM judge.")
