# Submission and three-minute demonstration

## First thirty seconds

Lead with: **“Your agent can refuse in its final answer after it has already read another customer's record. We inspect what it did.”** Show the response beside the unauthorized tool action. If this particular live run discloses the protected order visibly, describe it honestly as a visible failure; do not force the hidden-failure claim onto every run.

## Suggested video sequence (about 2 minutes 45 seconds)

| Time | Screen / narration |
|---|---|
| 0:00–0:20 | State the developer problem; show an actual recorded response and trace comparison. |
| 0:20–0:45 | Indirect injection investigation: benign request for O3001, retrieved untrusted note, later O2001 lookup. |
| 0:45–1:05 | Deterministic ownership verdict, source/unsafe event evidence, and critical step. Explain temporal attribution accurately. |
| 1:05–1:25 | Show the accepted shorter trigger and empirical rerun history in the JSON export. |
| 1:25–1:55 | Replay the trigger. Baseline must reproduce the requested failure; protected run must complete with no configured violations. |
| 1:55–2:20 | Save the server-verified case, rerun it, and show persistent evidence. |
| 2:20–2:35 | Historical counts with denominators and the controlled-sandbox limitation. |
| 2:35–2:45 | Nemotron's three runtime roles through Nebius, independent oracle, and working demo/repository links. |

Model calls may take minutes. Capture a genuine completed run beforehand and edit waiting time out, clearly labeling time cuts. If an LLM rerun does not reproduce, explain stochastic non-reproduction; retry visibly or use another clearly labeled genuine captured run. Do not substitute scripted test doubles for a live product demo. AFL-3/AFL-4 are local cases; a clean public deployment needs cases created through live verification.

## Prioritized submission checklist

1. Publish a public repository containing the MIT license, setup guide, and reproducible artifacts. This workspace did not initially contain Git metadata; publication is still outstanding. Verify exclusions before the first commit and check any existing remote history for secrets.
2. Deploy and independently test a working build with server credentials, persistence and spend controls. Provide judge access instructions and maintain free access through judging.
3. Publish an English demo video no longer than three minutes; add actual repository, demo and video URLs to README and submission.
4. Submit a concrete problem/implementation/impact description and **feedback on Nebius and NVIDIA technologies**. If work predates the submission period, describe substantial updates. Confirm eligibility and ownership in the official submission flow.
5. Rerun a timestamped benchmark against the final code, retain full artifacts/provenance, and add legitimate-task utility cases. Keep the historical results labeled as historical.

The event's [official rules](https://nebiusglobalaihackathon.devpost.com/rules) specify runtime Nebius/NVIDIA use, a public licensed repository, a short public video, accessible test build, sponsor feedback and four equally weighted judging dimensions. Check the current rules before submitting. This document uses the user's longer rubric for preparation, not an official scoring formula.

## Feedback notes to complete from real experience

The code confirms that the OpenAI-compatible interface allowed one shared client for adversarial generation, tool decisions and minimizer proposals. The repository also shows why model generation is separated from deterministic evaluation. Describe actual setup friction, JSON-decision behavior, latency, cost and SDK experience from your run records. The old virtualenv was broken locally, which is an environment issue rather than evidence of a Nebius service defect.

No unsupported latency, throughput, cost, service reliability, model superiority, customer validation or GPU-utilization claims are supplied. The required feedback section needs the owner's real observations.
