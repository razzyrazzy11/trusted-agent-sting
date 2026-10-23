# Undercover Agents: a trusted-agent sting study in Liar's Bar

Apart Research AI Collusion Research Sprint (October 23-25, 2026), sprint question 3.2: can a trusted
agent that *offers* to collude expose and deter collusion between LLM agents? A scripted "sting" player
in the Liar's Bar harness privately offers another LLM agent a mutual non-challenge pact. The study
measures who accepts, who acts on it, how well the sting works as a detector at a fixed false-positive
rate, and whether an integrity notice deters collusion or only hides it.

| File | What it is |
|---|---|
| [`sting/README.md`](llm-agent-collusion-2/Collusion_Liars_Bar/sting/README.md) | Runbook: setup, the Modal servers, every stage, costs, schedule |
| [`sting/PREREG.md`](llm-agent-collusion-2/Collusion_Liars_Bar/sting/PREREG.md) | Pre-registration: hypotheses, estimands, tests, sample sizes, go/no-go |
| [`sting/DEVIATIONS.md`](llm-agent-collusion-2/Collusion_Liars_Bar/sting/DEVIATIONS.md) | Every departure from the harness and every design change, with reasons |
| [`sting/TEXTS.md`](llm-agent-collusion-2/Collusion_Liars_Bar/sting/TEXTS.md) | Every text the study shows the agents, verbatim |

## Quick start (Linux, or WSL on Windows)

```bash
git clone https://github.com/razzyrazzy11/trusted-agent-sting && cd trusted-agent-sting
cp compute.env.example compute.env      # add ANTHROPIC_API_KEY and HF_TOKEN (see the runbook)
./setup.sh llm-agent-collusion-2        # needs uv: https://docs.astral.sh/uv/
```

Then follow the runbook from "Setup (once)". Models: Llama-3.1-8B-Instruct and Qwen2.5-7B-Instruct on the
study's own vLLM servers on Modal, Claude Haiku 5.5 through the Anthropic API.

## Provenance

- The second commit imports, unmodified, the parts of the sprint starter repository this study uses:
  [poseidon-research/collusion_hackathon](https://github.com/poseidon-research/collusion_hackathon) at
  commit `d585a7b` (`setup.sh`, `COMPUTE.md`, `compute.env.example`, `.gitignore`, `util/`,
  `llm-agent-collusion-2/`). The starter's README is kept as [`STARTER_README.md`](STARTER_README.md); its
  nine other projects are omitted.
- The Liar's Bar harness in `llm-agent-collusion-2/` is Zeng & Rudzicz (2026), "Voluntary Collusion with
  Secret Tools in Competing LLM Agents" (arXiv:2605.27593), built on LYiHub/liars-bar-llm (Apache-2.0).
- Every later commit is separate: first the bug fixes to preexisting harness files, then the new study
  code in `llm-agent-collusion-2/Collusion_Liars_Bar/sting/` and `llm-agent-collusion-2/sting_tests/`.

## License

[`LICENSE`](LICENSE) (Apache-2.0) covers the code written for this study. Imported code keeps its own
terms: `llm-agent-collusion-2/` carries its own Apache-2.0 license; `util/` and the root setup files come
from the starter repository, which has no license file, so check with the sprint organizers before making
this repository public.
