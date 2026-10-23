# Undercover Agents: a trusted-agent sting study in Liar's Bar

Apart Research AI Collusion Research Sprint (Oct 23-25, 2026), question 3.2: *a trusted agent that
offers to collude has not yet been tested.* A scripted "sting" confederate sits at a Liar's Bar table
as an ordinary player, privately offers another LLM agent a mutual non-challenge pact, and we measure
who accepts (Stage A), who acts on it (Stage S snapshots, Stage L live games), whether the sting
works as a detector at a known false-positive rate, and whether an integrity notice deters collusion
or only hides it.

- **Protocol:** [`PREREG.md`](PREREG.md) (hypotheses, estimands, tests, sample sizes, go/no-go).
- **Every departure from the harness:** [`DEVIATIONS.md`](DEVIATIONS.md).
- **Every text an agent sees that the study added:** [`TEXTS.md`](TEXTS.md) (generated from `texts.py`).

## Provenance: new vs preexisting

| Path | Status |
|---|---|
| `llm-agent-collusion-2/Collusion_Liars_Bar/src/`, `prompts/`, the starter repo | **Preexisting** (Zeng & Rudzicz 2026, via poseidon-research/collusion_hackathon @ `d585a7b`; Apache-2.0 upstream LYiHub/liars-bar-llm) |
| `src/game/game_secret_channel.py`, `src/game/game_secret_hint.py`, `src/test/test_secret_*_acceptance.py` | Preexisting, **patched during the sprint** (bug fixes only; DEVIATIONS.md section A; separate commit) |
| `Collusion_Liars_Bar/sting/` (all files) | **New, written during the sprint** |
| `llm-agent-collusion-2/sting_tests/` | **New, written during the sprint** |

No code was written before the sprint. The git history separates the preexisting baseline (`d585a7b`),
the harness bug fixes, and the new study code.

## Setup (once)

```bash
# from the repo root (collusion_hackathon/)
cp compute.env.example compute.env        # add NEBIUS_API_KEY and OPENROUTER_API_KEY
#   OPENROUTER_API_KEY is required for gpt-4.1-mini (Stages A and S); Llama/Qwen run on Nebius.
#   Leave LLM_MODEL UNSET: it forces one model into every seat and role.
./setup.sh llm-agent-collusion-2
cd llm-agent-collusion-2 && source .venv/bin/activate
uv pip install -r Collusion_Liars_Bar/sting/requirements.txt   # statsmodels for the GEE check
cd Collusion_Liars_Bar                     # every command below runs from here
```

## Step 0 - zero-cost dry run (5 minutes, $0)

```bash
(cd ../sting_tests && python -m pytest -q)          # 38 tests, ~40 s
python -m sting stage-a  --stub
python -m sting live     --stub --pilot && python -m sting checkpoint --runs sting_runs_stub
python -m sting live     --stub
python -m sting snapshots --stub
python -m sting judge    --runs sting_runs_stub --stub
python -m sting analyze  --runs sting_runs_stub     # -> sting_results_stub/ (stamped STUB DATA)
```

Stub outputs go to `sting_runs_stub/` and `sting_results_stub/`, are stamped
**"STUB DATA - NOT RESULTS"**, and the stages refuse to mix stub and real data in one folder. The stub
has planted effects; the pipeline test checks they are recovered and that the nulls stay null.

## Steps 1-7 - the real study

| Step | Command | Calls | Cost (est.) | Wall clock (est.) |
|---|---|---|---|---|
| 1. Freeze | `python -m sting freeze`, then commit + `git tag prereg-v1`; paste the hash into PREREG.md | - | - | 5 min |
| 2. Stage A | `python -m sting stage-a` | 3,300 | < $1 | 15-30 min |
| 3. Pilot + go/no-go | `python -m sting live --pilot` then `python -m sting checkpoint` | ~10k | < $1 | 30-45 min |
| 4. Stage L (main) | `python -m sting live` (resumes the pilot; 60 sequences at LIVE_N) | ~70k | ~$3-5 | 2-3 h at 6 workers |
| 5. Stage S | `python -m sting snapshots` (needs Stage A and >= 15 finished sequences) | ~17k | ~$7 | 1-2 h |
| 6. Judge + labels | `python -m sting judge`; `python -m sting labels export`; hand-label `hand_label`; `python -m sting labels kappa` | few hundred | < $0.5 | 45 min (human) |
| 7. Analysis | `python -m sting analyze` | - | - | 1 min |

Cost assumptions (planning only; the pipeline records real token counts): ~1,500 input and ~150
output tokens per call; OpenRouter list prices per million tokens (input/output) Llama-3.1-8B
$0.02/$0.04, Qwen2.5-7B $0.10/$0.20, gpt-4.1-mini $0.40/$1.60; Nebius prices unverified. Total
~$15, well under the $150 cap; the spare budget covers an optional live replication with
gpt-4.1-mini (`python -m sting live --model gpt-4.1-mini --arms B1 B3 --seeds 0-9`, ~$20).

Rate limits: concurrency is about `workers x (1 + reflect_workers)` calls in flight (default
6 x 5 = 30). If the provider throttles, lower `--workers`; this changes timing only, never results.

## Schedule to the deadline (Sunday 23:59 AoE = Monday 11:59 UTC)

| When (UTC) | Do |
|---|---|
| Fri 21:00-23:00 | Step 0 dry run; Step 1 freeze; Step 2 Stage A |
| Fri 23:00-Sat 01:00 | Step 3 pilot (runs unattended) |
| Sat morning | `checkpoint` -> GO/NO-GO (pre-registered rule, PREREG section 9); GO -> Step 4 |
| Sat afternoon | Step 5 snapshots (once >= 15 sequences are done); Step 6 judge and hand labels |
| Sat evening | Step 7 analysis; start the paper from `sting_results/summary.md` and `claims.json` |
| Sun | Write the paper; re-run `analyze` after any late data; submit early, resubmit with the same title if needed |

## Outputs and where the paper's numbers come from

`python -m sting analyze` writes `sting_results/`:

- `summary.md` - every hypothesis, positive control, contrast and health statistic.
- `claims.json` - every number the paper may cite, with CI, n and the stage it came from. **Cite only
  numbers from this file** (fabricated results disqualify a sprint submission).
- `tables/*.csv|md` - the table view of every figure.
- `figures/fig1_design` ... `fig5_detector` (PNG + PDF), one per hypothesis.

Raw data: `sting_runs/` (Stage A replies, live decisions with the actual challenger and fallbacks,
events, probes, every LLM call with tokens and latency, the harness's own per-game records).

## Publish vs withhold

Publish: all code, all prompts and offer texts verbatim (`TEXTS.md`; Zeng & Rudzicz already publish
stronger collusion offers), aggregate data, decision logs and the analysis. The genuine dual-use
concern is the *sting-detectability* findings - which cues let a colluder recognise a plant - so the
paper discusses them at the level of findings in the Limitations and Dual-Use / Ethical
Considerations appendix, without a step-by-step evasion guide; raw suspicion-probe transcripts are
shared on request. Follow Apart's guidance to disclose sensitive results privately first.

## Reproducibility

Seeds fix names, seat-arrangement order, deals, target cards, bullets, first players and the sting's
plays and challenges (common random numbers across arms: the same seed gives the same table in every
arm until play diverges). Provider sampling is not seedable. `meta.json` in each sequence records the
config, names, the offer and reply, per-game results, call and token counts, the git commit and
Python version.

## Known harness limitations (preexisting, not fixed)

- `Collusion_Liars_Bar/__init__.py` imports a module missing from the repo (`src.game.game_commute`),
  so the package itself cannot be imported; the study never imports it.
- The secret-channel series' `--enable-memory` does not carry anything across games (players are
  rebuilt each game); the study uses its own private-record carrier instead.
- Zeng's colluding pair (Llama-3-8B, Mistral-7B) is substituted in the starter repo by Llama-3.2-3B
  and Ministral-8B.
