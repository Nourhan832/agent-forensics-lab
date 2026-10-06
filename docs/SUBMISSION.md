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

## Current submission state

The live app is deployed at [agent-forensics-lab.fly.dev](https://agent-forensics-lab.fly.dev/). The final UI is frozen, and the repository privacy audit passed. The repository remains private pending explicit publication approval. Frozen benchmark evidence and its provenance remain preserved; no new benchmark is required for this documentation pass.

## Remaining submission checklist

1. Make the existing licensed repository public after explicit approval; preserve the verified privacy exclusions and sanitized public evidence.
2. Publish the final English YouTube demonstration under three minutes and add its actual URL to README and Devpost. No public video URL is recorded yet.
3. Complete Devpost fields: **Best Apps and Agents**, project features/implementation/impact, repository/demo/video URLs, judge testing instructions, and factual Nebius/NVIDIA feedback. Confirm eligibility and ownership; explain significant updates only if the project predates the submission period. Maintain free judge access through judging.

The event's [official rules](https://nebiusglobalaihackathon.devpost.com/rules) specify runtime Nebius/NVIDIA use, a public licensed repository, a short public video, accessible test build, sponsor feedback and four equally weighted judging dimensions. Check the current rules before submitting. This document uses the user's longer rubric for preparation, not an official scoring formula.

## Technology feedback

Nebius Token Factory supplied the OpenAI-compatible inference endpoint for live agent execution, replay, minimization, and controlled multi-model evaluation. NVIDIA Nemotron was the primary forensic-workflow model. A shared client integration and model access through the same provider/API layer supported the controlled Nemotron/Hermes/Qwen comparison. See the README technology feedback subsection for submission-ready wording.

Do not add latency, throughput, reliability, model-superiority, or compliance claims without supporting evidence.
