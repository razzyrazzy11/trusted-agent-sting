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
| Stage A: 500 offers per cell for the open 7-8B models (100 for gpt-4.1-mini) | Zeng's protocol; stub validation showed 100 per cell misses a 0.15 difference ~30% of the time |
| Positive control B0: designer hint paired with S (not Zeng's 4-model replication) | Zeng's colluding pair is substituted in the starter repo; the control must be measurable on S |
| Suspicion funnel and follow-up interview added | Manipulation-check convention for confederate designs; Zeng v2 concealment test; Meinke et al. 2024 |
| Freeze before any real data (was "beyond the pilot"); hash recorded in `FREEZE.json` and the tag, not in PREREG.md; protocol set extended to parsing, sampling settings, checkpoint, judge and loader; every data folder records its protocol hash | The old wording let pre-freeze pilot data enter the confirmatory sample (contradicting section 9); pasting the hash into a hashed file changed the hash |

## D. Post-freeze deviations (append-only)

| When (UTC) | Real data seen? | What changed | Why | Effect on analyses |
|---|---|---|---|---|
| | | | | |
