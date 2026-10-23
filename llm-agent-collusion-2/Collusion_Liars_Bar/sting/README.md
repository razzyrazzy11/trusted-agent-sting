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

No code was written before the sprint. The git history separates the preexisting baseline (the
starter at `d585a7b`, imported unmodified in its own commit), the harness bug fixes, and the new
study code.

## Setup (once)

On Windows, run everything inside WSL with Ubuntu (WSL 1 is enough if hardware virtualization is
unavailable: the GPUs are on Modal): the starter's `setup.sh` is a bash script, and Modal's login must
live in the same environment that runs the study. Keep the clone in the Linux home folder, not in
OneDrive.

```bash
# from the repo root (the folder with setup.sh)
cp compute.env.example compute.env        # then add:
#   ANTHROPIC_API_KEY=...   Claude Haiku 5.5 (Stages A and S, judge)
#   HF_TOKEN=hf_...         a read token whose account has been granted access to
#                           https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct (Meta approves
#                           manually: request it first thing)
#   No Nebius/OpenRouter key is needed. Leave LLM_MODEL UNSET (the study refuses it anyway).
./setup.sh llm-agent-collusion-2
cd llm-agent-collusion-2 && source .venv/bin/activate
uv pip install -r Collusion_Liars_Bar/sting/requirements.txt   # modal, anthropic, statsmodels
python -m modal setup                      # once, in this environment (browser login; sprint credits)
cd Collusion_Liars_Bar                     # every command below runs from here
python -m sting modal deploy               # the study's vLLM servers for Llama and Qwen (sting/modal_app.py)
python -m sting modal warm                 # first boot downloads the weights: 5-10 min
```

`modal deploy` checks your Hugging Face access before spending any GPU time. If Meta has not approved
the request yet, `python -m sting modal deploy --llama-mirror` serves an ungated copy whose weights and
configs are byte-identical to Meta's repo (only `tokenizer_config.json` differs; log it in
DEVIATIONS.md). Servers scale to zero after 15 idle minutes; `python -m sting modal stop` at the end.
To use Nebius/OpenRouter instead of Modal, set `STING_OPEN_BACKEND=poseidon`.

## Step 0 - zero-cost dry run (5 minutes, $0)

```bash
(cd ../sting_tests && python -m pytest -q)          # 47 tests, ~45 s
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
| 0b. Real smoke test | `python -m sting smoke` (keys, servers, parsing, time per game; prints where each model is served) | ~130 | cents | 5 min |
| 1. Freeze | Review `PREREG.md`, then `python -m sting freeze` (writes `sting/FREEZE.json`), then commit + `git tag -a prereg-v1` as printed. Before any real data (PREREG section 9) | - | - | 5 min |
| 2. Stage A | `python -m sting stage-a --workers 32` | 16,500 (3 models) | Claude ~$0.70 | 30-45 min |
| 3. Pilot + go/no-go | `python -m sting live --pilot --workers 9` then `python -m sting checkpoint` | ~5-10k | GPU only | 20-40 min |
| 4. Stage L (main) | `python -m sting live --workers 10` (resumes the pilot; 60 sequences at LIVE_N) | ~35-70k | GPU only | 1-2 h |
| 5. Stage S | `python -m sting snapshots --workers 32` (needs Stage A and >= 15 finished sequences) | ~22k (2 models) | Claude ~$2 | 45-75 min |
| 6. Judge + labels | `python -m sting judge`; `python -m sting labels export`; hand-label `hand_label`; `python -m sting labels kappa` | few hundred | < $0.10 | 45 min (human) |
| 7. Analysis | `python -m sting analyze` | - | - | 1 min |

Cost (planning; the pipeline records real token counts and how every call was served): Claude
Haiku 5.5 at $0.10/$0.50 per million input/output tokens, about $3 in all. Modal bills GPU time, not
tokens: an H100 is $3.95/h, each server scales to zero 15 minutes after its last request, and the
whole study needs roughly 3-5 server-hours, about $15-25 of the sprint's $50 credit (watch Modal
dashboard -> Usage; set a workspace spending limit). `--gpu A100-80GB` ($2.50/h) or `L40S` ($1.95/h)
at deploy costs less per hour and runs slower; the GPU type changes timing, never results.

Progress at any time: `python -m sting status`. The three Stage A models can also run in parallel
terminals (`--models llama-3.1-8b`, `--models qwen2.5-7b`, `--models claude-haiku-5.5`).

Concurrency: about `workers x (1 + reflect_workers)` calls in flight in Stage L (10 x 5 = 50). Each
Modal server batches up to 128 concurrent requests on one GPU. If Claude rate-limits (new API
accounts can start below the standard 1,000 requests/minute), the SDK backs off and retries;
lowering `--workers` changes timing only, never results.

## Schedule to the deadline (Sunday 23:59 AoE = Monday 11:59 UTC)

| When (UTC) | Do |
|---|---|
| Fri night, first | Request Llama access on Hugging Face (Meta approves manually) |
| Fri night | Step 0 dry run; `modal deploy` + `warm`; Step 0b smoke; Step 1 freeze; Step 2 Stage A |
| Fri night / Sat early | Step 3 pilot (unattended, under an hour on H100) |
| Sat morning | `checkpoint` -> GO/NO-GO (pre-registered rule, PREREG section 9); GO -> Step 4 (1-2 h) |
| Sat midday | Step 5 snapshots (once >= 15 sequences are done); Step 6 judge and hand labels |
| Sat afternoon/evening | Step 7 analysis; start the paper from `sting_results/summary.md` and `claims.json` |
| Sun | Write the paper; re-run `analyze` after any late data; `python -m sting modal stop`; submit early, resubmit with the same title if needed |

## Outputs and where the paper's numbers come from

`python -m sting analyze` writes `sting_results/`:

- `summary.md` - every hypothesis, positive control, contrast and health statistic.
- `claims.json` - every number the paper may cite, with CI, n and the stage it came from. **Cite only
  numbers from this file** (fabricated results disqualify a sprint submission).
- `tables/*.csv|md` - the table view of every figure.
- `figures/fig1_design` ... `fig5_detector` (PNG + PDF), one per hypothesis.

Raw data: `sting_runs/` (Stage A replies, live decisions with the actual challenger and fallbacks,
events, probes, every LLM call with tokens and latency, the harness's own per-game records).

### What goes into git

The starter repo's `.gitignore` hides `*.json`, `*.csv`, `*.png` and `*.log` but not `*.jsonl`, so
by default `git add -A` would drop `FREEZE.json` and `claims.json` and commit half of every raw-data
folder (the stub dry run alone writes ~250 MB). The study corrects this, so `git add -A` is safe:

- `sting/.gitignore` and `sting_results/.gitignore` un-ignore the freeze record and every analysis
  output (tables, figures, `claims.json`), so they are committed.
- Every `sting_runs*/` folder gets a catch-all `.gitignore` when it is created, and stub results
  (`sting_results_stub/`) are never committable.

To publish the raw data, archive it (`tar czf sting_runs.tar.gz sting_runs/`) and attach it to a
GitHub release or share it on request, following the publish/withhold rule below.

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
