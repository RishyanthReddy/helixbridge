# Team guide

1. Clone the private repository, install Python 3.12 dependencies and run the offline example and tests in README.
2. Set your own Modal profile locally. Always supply `MODAL_PROFILE` in each command when more than one profile is configured. Each workspace has its own billing, model cache and results Volume. Two API tokens do not pool credits into a common balance.
3. Start with the frozen rehearsal, not a new target campaign. Prepare weights, generate one candidate, then evaluate that exact sequence. Keep all failures and all scores; do not quietly choose a favorable seed.
4. Use a unique run ID beginning with your name. Start at seed43 for reproduction. This historical adapter currently accepts seeds43/44/101–112; it is not a general campaign launcher.
5. Before rerunning, inspect the local result and remote Volume. Existing output directories are intentionally refused rather than overwritten. Do not delete a shared cache to solve a single failed run.
6. Record each attempt in a copy of `docs/experiment-template.csv`: operator, code revision, workspace/profile label, seed, input hashes, run ID, model versions, status, metrics, runtime, dashboard cost and output location. Never add tokens or personal identifiers to this table.
7. Work on a named branch, for example `experiment/alice-seed43`. Open a pull request with the change, exact commands and observed results. Upload small reviewed result summaries only. Full output archives remain outside Git; agree an access-controlled storage destination before sharing them.

## Two active operators

The captain configured two local account profiles outside the repository. Obtain the assigned credential privately from the captain or use an individual workspace invitation where supported. Each operator only needs one account. Token setup prompts in README avoid saving secrets in shell command history. Do not put the credential in screenshots, issues, commits, notebooks or shared logs.

## Interpreting the outputs

`generation.json` contains the generator's candidate sequence and provenance. `evaluate.json` contains an independent Boltz prediction and raw directional/symmetric-max ipSAE scores. High scores are computational confidence, not measured affinity. An evaluation failure must stay recorded as a failure, not be replaced with a score of zero or a successful status.

The current minimal Modal adapter does not yet run our entire Earth context/pose review or ESMFold2 path. Reuse those historical audits only after validating their paths and inputs. Historical prediction settings are not claimed to match the organizer's undisclosed implementation exactly.
