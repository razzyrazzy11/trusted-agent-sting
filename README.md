# Undercover Agents: a trusted-agent sting study in Liar's Bar

Author: Razvan Sacara (with Apart Research).

Apart Research AI Collusion Research Sprint (October 23-25, 2026), sprint question 3.2: can a trusted
agent that *offers* to collude expose and deter collusion between LLM agents? A scripted "sting" player
in the Liar's Bar harness privately offers another LLM agent a mutual non-challenge pact. The study
measures who accepts, who acts on it, how well a re-query audit built on the sting flags pact-takers at a
fixed false-positive rate (the preregistration and code call it the "detector"), and whether an integrity
notice deters collusion or only hides it.

**Status: complete.** The paper is [`paper/out/undercover_agents.pdf`](paper/out/undercover_agents.pdf)
(Word source alongside). Its answer to question 3.2 is *partly*: the sting exposes agents whose play
changes after its offer, and announcing stings deters acceptance of that offer, but in replayed decisions
neither the notice nor a warning from the sting measurably weakened a pact already accepted from another
player. Preregistered analyses are in `llm-agent-collusion-2/Collusion_Liars_Bar/sting_results/`
(`summary.md`, `results.json`, `claims.json`, `tables/`); post hoc analyses, each planned in
`DEVIATIONS.md` section D before its data, are in `sting_results/posthoc/` and `sting_results/posthoc_ext/`.
Raw run logs and suspicion transcripts are not in the repository (shared on request).

| File | What it is |
|---|---|
| [`sting/README.md`](llm-agent-collusion-2/Collusion_Liars_Bar/sting/README.md) | Runbook: setup, the Modal servers, every stage, costs, schedule |
| [`sting/PREREG.md`](llm-agent-collusion-2/Collusion_Liars_Bar/sting/PREREG.md) | Pre-registration: hypotheses, estimands, tests, sample sizes, go/no-go |
| [`sting/DEVIATIONS.md`](llm-agent-collusion-2/Collusion_Liars_Bar/sting/DEVIATIONS.md) | Every departure from the harness and every design change, with reasons |
| [`sting/TEXTS.md`](llm-agent-collusion-2/Collusion_Liars_Bar/sting/TEXTS.md) | Every text the preregistered study shows the agents, verbatim (the post hoc K3/K4 messages from S are in `sting/posthoc_coalition.py`) |
| [`paper/`](paper/) | The paper: `content.py` (text), `paper_numbers.py` (every number, resolved from the result files), `make_figures.py`, `build.py`; outputs in `paper/out/` |

## Verify and rebuild without any model calls

```bash
cd llm-agent-collusion-2 && uv sync --locked                       # the study's locked environment (uv.lock)
uv pip install -r Collusion_Liars_Bar/sting/requirements.txt
cd Collusion_Liars_Bar && ../.venv/bin/python -m sting freeze --check   # MATCH: protocol unchanged since the freeze
(cd ../sting_tests && ../.venv/bin/python -m pytest -q)                 # 59 tests
cd ../.. && llm-agent-collusion-2/.venv/bin/python paper/check_numbers.py  # 364 numbers match the committed paper
pip install -r paper/requirements-lock.txt                              # to rebuild the document itself:
python3 paper/make_figures.py && python3 paper/build.py   # needs LibreOffice (soffice) and poppler (pdftotext)
```

The first four checks run on every push ([`.github/workflows/checks.yml`](.github/workflows/checks.yml)),
on Python 3.12; the paper was built on Python 3.13 with the versions in `paper/requirements-lock.txt`.
`paper/build.py` resolves every number in the text from the committed result files (the list is
`paper/out/number_sources.md`), asserts every result-dependent claim, and stops if the main text exceeds
8 pages or the abstract leaves 150-250 words.

**Citing.** [`CITATION.cff`](CITATION.cff) (GitHub's "Cite this repository") points to the paper. Each
submitted version of the paper is tagged `submission-v*` (latest: `submission-v1`); the preregistration is
tagged `prereg-v1`.

## Quick start (Linux, or WSL on Windows)

```bash
git clone https://github.com/razzyrazzy11/trusted-agent-sting && cd trusted-agent-sting
cp compute.env.example compute.env      # add ANTHROPIC_API_KEY and HF_TOKEN (see the runbook)
./setup.sh llm-agent-collusion-2        # needs uv: https://docs.astral.sh/uv/
```

The repository is private during judging (access on request). Then follow the runbook from "Setup (once)". Models: Llama-3.1-8B-Instruct and Qwen2.5-7B-Instruct on the
study's own vLLM servers on Modal, Claude Haiku 5.5 through the Anthropic API.

## Provenance

- The second commit imports, unmodified, the parts of the sprint starter repository this study uses:
  [poseidon-research/collusion_hackathon](https://github.com/poseidon-research/collusion_hackathon) at
  commit `d585a7b` (`setup.sh`, `COMPUTE.md`, `compute.env.example`, `.gitignore`, `util/`,
  `llm-agent-collusion-2/`). The starter's README is kept unedited as [`STARTER_README.md`](STARTER_README.md);
  its other project folders and `literature/` are omitted, so its links to them do not resolve here.
- The Liar's Bar harness in `llm-agent-collusion-2/` is Zeng & Rudzicz (2026), "Voluntary Collusion with
  Secret Tools in Competing LLM Agents" (arXiv:2605.27593), under the Apache-2.0 licence.
- Every later commit is separate: first the bug fixes to preexisting harness files, then the new study
  code in `llm-agent-collusion-2/Collusion_Liars_Bar/sting/` and `llm-agent-collusion-2/sting_tests/`,
  then (after the data) the results, the paper in `paper/`, and the citation file and CI checks.

## License

[`LICENSE`](LICENSE) (Apache-2.0) covers the code written for this study. Imported code keeps its own
terms: `llm-agent-collusion-2/` carries its own Apache-2.0 license; `util/` and the root setup files come
from the starter repository, which has no license file, so check with the sprint organizers before making
this repository public.
