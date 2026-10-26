# Security policy

This repository is a finished research study (code, preregistration, results and paper), not a
maintained product. Please still report anything below; reports are welcome and taken seriously.

## What to report

- A secret, key or personal detail in the files or in the git history.
- A flaw in the code that could send credentials to the wrong place, expose a model server, or make a
  published result unsafe to reproduce.
- A dual-use concern about the published material: the offer texts in `sting/TEXTS.md`, or any cue that
  would let an agent recognise the trusted-agent sting (see Appendix A.2 of the paper, which says that any
  analysis of such cues should go first to the harness authors and the sprint organisers, in line with
  Apart Research's Responsible Disclosure Policy).

## Supported versions

Only the latest commit on `master`. The paper as submitted is tagged `submission-v*`; the
preregistration is tagged `prereg-v1`. Neither tag receives fixes, because the paper's numbers must not
change after submission (`python -m sting freeze --check` guards the preregistered protocol).

## How to report

Please do not put details in a public issue or pull request.

1. **Preferred: GitHub private vulnerability reporting.** Open the repository's **Security and quality**
   tab and choose **Report a vulnerability**.
2. **If the button is not shown,** open an issue titled "Security contact request" with no details, and a
   private channel will be arranged.

I will acknowledge a report as soon as I can; this is a one-person research project, so there is no
service-level commitment.

## Raw data

Raw game logs and suspicion-probe transcripts are deliberately not in the repository, because they show
which behaviours made agents suspect the sting. They are shared on request for safety research (the same
routes as above). The committed results are aggregate counts and rates only.
