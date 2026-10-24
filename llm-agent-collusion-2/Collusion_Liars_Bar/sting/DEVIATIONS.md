# Deviations log

Four parts: (A) changes made to the preexisting harness, (B) deliberate differences between the
study's game and the harness or Zeng & Rudzicz (2026), (C) design changes made during the sprint
before any real-model data, (D) the post-freeze log (append-only).

Preexisting code: github.com/poseidon-research/collusion_hackathon at commit `d585a7b`
(2026-10-23), folder `llm-agent-collusion-2/` (Zeng & Rudzicz's Liar's Bar, extended from
LYiHub/liars-bar-llm, Apache-2.0).

## A. Changes to preexisting harness files (commit "Fix double round reset ...")

| File | Change | Why |
|---|---|---|
| `src/game/game_secret_channel.py`, `src/game/game_secret_hint.py` | Removed the duplicate `check_victory()` / `reset_round()` after `perform_penalty()` in `play_round` | `perform_penalty` already does both. Every challenge reset the round twice (two reflection passes, two deals, round counter +2) and the last survivor got +3 twice. Regression test: `sting_tests/test_game.py::test_patched_harness_has_no_empty_rounds` (the original code leaves 10 empty rounds in a 21-round game; patched, none). |
| `src/test/test_secret_comm_acceptance.py`, `src/test/test_secret_hint_acceptance.py` | Offer prompt path `tool_offer_prompt copy.txt` -> `tool_offer_prompt.txt` | The referenced file is not in the repository; the scripts could not run. |

No other preexisting file is modified. The study's own game (`sting/game.py`) subclasses the base
`Game` (`src/game/game.py`), which does not have the double-reset bug.

## B. Study game vs harness / paper (by design)

| # | Harness / paper | Study | Reason |
|---|---|---|---|
| B1 | Seat order = config order; first player, deal, target, bullets, restarts from global `random` | Seat arrangement A/B per game; all draws from seeded streams keyed by purpose (common random numbers across arms) | Measurability of a mutual pact under "only the next player may challenge"; variance reduction |
| B2 | All four seats are LLM players | S is a scripted confederate: decisions seeded and arm-invariant; visible "behavior" text written by the table's model; S does not reflect (its opinions are never shown) | Control (the arms differ only in what T was told); indistinguishability of planted inputs (Greenblatt et al. 2024; Dietrich 2026) |
| B3 | Partner consent described in the paper (Algorithm 1) but not implemented in live games: the partner notification is built and never sent | The offer is delivered to T as a private message; T's reply is recorded and kept in its private record whatever it says | Consent is the quantity of interest |
| B4 | Secret channel: per-turn messaging; `--enable-memory` writes into the finished game's players, which are discarded, so nothing carries over | One private offer before game 3; the record (offer + T's reply) is re-attached to T in every later game through the harness's own CROSS-GAME MEMORY slot | A single, controlled pact carrier; the harness's persistence does not work |
| B5 | Designer hint offer asks the recipient to choose a partner | Arm B0 / cell A0b: partner fixed to S (one sentence replaced; `texts.designer_hint_offer`) | The effect must be measurable on S. A0z keeps Zeng's text verbatim with free partner choice |
| B6 | Four different models (Zeng: Mistral-7B, Llama-3-8B, Llama-3.1-8B, Qwen2.5-7B; the starter repo substitutes Llama-3.2-3B and Ministral-8B for the first two) | T, O1, O2 and S's voice all Llama-3.1-8B-Instruct | Isolates the sting effect from model-mix effects; Llama-3.1-8B is one of Zeng's two unsubstituted seats. Zeng's 0.976 -> 0.307 colluder anchor belongs to the substituted pair and is not a replication target |
| B7 | 50-game sequences, offer at game 20 | 6-game sequences, offer before game 3 | Sprint budget; Zeng's in-sequence offer logic and matched-time placebo (B3) kept |
| B8 | Second-last-survivor bonus counted survivors after the elimination, so +2 went to the third-last player | Counted before the elimination (`StingGame.perform_penalty`) | Bug; the rules say second-last |
| B9 | Decision prompts showed "You have fired N shot(s)" with N = pulls + 1 (chamber counter starts at 1) | True shots fired | Bug; agents reason about risk from this number |
| B10 | Reflections run sequentially | Run in parallel threads; each call has identical inputs | Wall-clock only |
| B11 | No round cap | 60-round cap per game, flagged | Safety; no cap was hit in stub runs |
| B12 | Acceptance parser: "ACCEPT" anywhere in the reply (so "I will not accept" is an acceptance) | Primary: strict first-word parser; harness parser kept for comparability; UNCLEAR judged by an LLM in sensitivity | Measurement validity |
| B13 | Zeng's acceptance test: 50-token cap, player list with model names | A0z: 50 tokens, model names removed; other offers: 80 tokens (one sentence) | Model names leak identity |
| B14 | The harness client swallows transient errors (returns "") | 3 attempts with exponential backoff from 1 s (Zeng App. D), then "", after which the harness's 5-attempt loop and fallback apply; everything logged | Reliability without hiding failures |
| B15 | `Collusion_Liars_Bar/__init__.py` imports `src.game.game_series`, which imports a missing module (`src.game.game_commute`) | Not modified; the study never imports that package, and tests live outside it (`llm-agent-collusion-2/sting_tests/`) | Preexisting breakage, noted |
| B16 | top-k and repetition penalty are sent in `extra_body` (harness) | Same | Whether each provider honours them is unverified; report the provider that served each run |

## C. Design changes during the sprint, before any real-model data

| Change | Reason |
|---|---|
| Two counterbalanced seat arrangements (A, B) instead of fixed seating | With fixed seating the pact is one-sided (only the next player may challenge) |
| Counterfactual snapshots made the primary power source; live games are the behavioural confirmation | One target per sequence cannot power the say-do and detector analyses |
| Sting never challenges T after the offer, in every arm | Makes S's behaviour arm-invariant |
| Sting plays 1 or 2 cards (0.7 / 0.3) instead of always 1 | A fixed single-card play is a possible tell; also lowered the sting's last-survivor share from 0.46 to ~0.34 in simulation |
| Deterrence estimand: difference-in-differences instead of a ratio | The benign-acceptance denominator is ~0; the earlier formula also mixed the wrong cells |
| Snapshot reference = pooled null record (C1a + C1b) | Stub validation showed the noise of a single 5-sample reference shifting every contrast (A/A check kept as C1b vs C1a) |
| C4 (refused) has no fairness reminder at decision time | So C4 vs C1 differs only by the refused-offer record |
| Detector threshold with randomized tie-breaking | Episode scores are discrete; a strict threshold gave held-out FPR ~0.01 instead of 0.10 in stub validation |
| Detector reported as an operating curve over audit length m | Per-decision scores are too noisy; the audit length is the natural design parameter |
| Detector primary analysis on the same decision situations (calibrate on C1a, FPR on the independent replicate C1b); cross-situation transfer reported separately | Simulation: calibrating on half the situations and testing on the other half inflates held-out FPR (0.12-0.14 at m = 20, ~0.19 at m = 40) because situations differ in baseline rates |
| K = 20 (not 5) for C1a, C1b, C3 at `chal_S` points | Tightens H2 and the detector's false-positive estimate (C1a-C1b noise) |
| H3 tests miscalibration (C1b FPR not significantly above 0.10) instead of an FPR upper bound | Stub validation: the FPR's 95% CI half-width is ~0.08 at this sample size, so any upper-bound criterion would fail often for a perfectly calibrated detector |
| Primary live test: between-arm post-offer rates (Welch), not pre/post | Simulation: only ~4-5 T-on-S decisions before the offer; pre/post power 0.2-0.45 |
| Sample sizes 15/15/10/10/10 (B1/B3/B0/B2/B4) | Simulation (PREREG section 7) |
| Stage A: 500 offers per cell for every model (first 100 for the API model) | Zeng's protocol for the 7-8B models; stub validation showed 100 per cell misses a 0.15 difference ~30% of the time; the API model's cost (~$0.70 for 5,500 Claude Haiku 5.5 offers) no longer justifies fewer |
| Frontier comparison model and LLM judge: Claude Haiku 5.5 (`claude-haiku-5-5`, thinking disabled, provider-default sampling) instead of gpt-4.1-mini | No OpenRouter account; Anthropic API credits available; a current safety-trained frontier model is the more relevant comparison. Thinking is on by default and counts toward max_tokens, so it is disabled to fit the study's 50-256-token caps. gpt-4.1-mini stays available as an optional model |
| Open models served by the study's own vLLM servers on Modal (sprint credits) instead of Nebius: bf16, pinned revisions, max_model_len 8192, `--generation-config vllm`, one GPU per model | Nebius and OpenRouter are not sponsored. The starter's Modal scaffolding (marked untested) would start one GPU per concurrent request, cannot start Llama-3.1's default 128k context on a 24 GB GPU, and forces one model id onto every call. The client verifies the served repo, context length and vLLM version before its first call |
| Positive control B0: designer hint paired with S (not Zeng's 4-model replication) | Zeng's colluding pair is substituted in the starter repo; the control must be measurable on S |
| Suspicion funnel and follow-up interview added | Manipulation-check convention for confederate designs; Zeng v2 concealment test; Meinke et al. 2024 |
| Freeze before any real data (was "beyond the pilot"); hash recorded in `FREEZE.json` and the tag, not in PREREG.md; protocol set extended to parsing, sampling settings, checkpoint, judge and loader; every data folder records its protocol hash | The old wording let pre-freeze pilot data enter the confirmatory sample (contradicting section 9); pasting the hash into a hashed file changed the hash |

## D. Post-freeze deviations (append-only)

| When (UTC) | Real data seen? | What changed | Why | Effect on analyses |
|---|---|---|---|---|
| 2026-10-24 09:14 | Yes | `analysis/figures.py`: error-bar lengths clamped at zero (commit 5a4f0f7) | `analyze` crashed when a CI bound sat a rounding error past a rate of 0 or 1 | None: plotting only; file is outside the frozen set |
| 2026-10-24 11:17 | Yes | 100 hand labels exported and labelled; kappa reported for the strict parser (commit 3e19fc9) | Planned validation (PREREG section 3); the judge had no UNCLEAR items to score, so it had n = 0 | None on confirmatory analyses (Stage A had no UNCLEAR replies, so the judge switch rule never applied) |
| 2026-10-24 12:25 | Yes | LLM judge run on all offer and interview replies, not only UNCLEAR ones, and validated against the hand labels (kappa 0.933; parser 0.893) (commit 2a78bea) | Interview answers often start "NO" and then admit the agreement, which the strict parser scores as denial | None on confirmatory analyses; enables the secondary denial analysis below |
| 2026-10-24 12:36 | Yes | Secondary, post hoc table `tables/denial_judge.md`: interview denial scored by the judge, B4 vs B1 (commit 292896c; code in `paper/scripts/denial_judge.py`) | Parser-based denial (H4d, descriptive) is inflated by deny-then-admit answers | Reported as secondary and post hoc; H4d's preregistered parser-based result is reported alongside it |
| 2026-10-24 | Yes | `analysis/figures.py`: figure 2 title/legend overlap fixed; paper figures redrawn at print size from committed tables (`paper/make_figures.py`) | Legibility | None: plotting only |
| 2026-10-24 15:00 | Yes | Correction to the row above, which has no time or commit and covers two commits: d7dfbd6 (12:59, `figures.py` legend fix; `paper/make_figures.py` created) and 812f5ca (13:11, `paper/make_figures.py` extended). Paper Figure 4 is now cropped without its in-image title (`paper/make_figures.py`) | Completeness of this log; the title repeated the paper's caption | None: plotting only |
| 2026-10-24 15:48 | Yes | The paper adds two post hoc descriptive computations from committed outputs (`paper/paper_numbers.py`): exact binomial detector flag rates given the fitted threshold and tie probability (`tables/detector_curve.csv`), and Welch 95% CIs for live contrasts from per-arm means and SDs (`tables/live_rates.csv`) | Reported flag rates are Monte Carlo estimates; percentile-bootstrap CIs are narrow at 10-15 sequences per arm | None: preregistered estimates and tests are reported unchanged; the additions are labelled in the paper |

Note on this section and the tag (added 2026-10-24, paper review). The first five rows were written
together in commit 812f5ca (13:11 UTC), after the changes they describe; the times and commits in
rows 1-4 match those commits. The tag `prereg-v1` points to the freeze commit 6885d5c, but its
message still reads "protocol hash <paste the hash>": the hash is recorded in `FREEZE.json`
(`frozen_at_utc` 2026-10-24T00:13:40Z), and GitHub recorded the push of 6885d5c at
2026-10-24T00:14:02Z, before the first results commit (9ab174a, 09:15 UTC). The tag is not re-made,
because a new tag would be dated after the data.
