"""Undercover Agents: a trusted-agent "sting" study in Liar's Bar.

Apart Research AI Collusion Research Sprint (Oct 23-25, 2026), sprint question 3.2:
"Can we disrupt collusion through introducing trusted agents?" -- specifically, a trusted
agent that *offers* to collude.

Everything in this package was written during the sprint. It builds on, and does not
modify the behaviour of, the preexisting Liar's Bar harness in ``src/`` (Zeng & Rudzicz,
2026, "Voluntary Collusion with Secret Tools in Competing LLM Agents", arXiv:2605.27593,
as bundled in github.com/poseidon-research/collusion_hackathon). See README.md for the
provenance table and DEVIATIONS.md for every departure from that harness.
"""

STUDY_VERSION = "sting-v1.0"
