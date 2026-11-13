# HelixBridge

Team research starting point for the Changjiang Cup 2026 protein-design challenge.

**Start here:** [current status](docs/STATUS.md), [team guide](docs/TEAM.md), [experiment queue](docs/NEXT.md).

The repository contains the existing design/screening code, selected research reports, small public target inputs, tests and a new Modal adapter. Historical runs used Earth L40S GPUs. The default Modal example deliberately reproduces a historical IL7Ra rehearsal. It does not create a competition-ready submission. Current official target ranges are kept separately from the frozen historical inputs.

## Install and check locally

Python 3.12 and Git are required. From the repository root:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python scripts/offline-demo.py
(cd pipeline && python -m unittest discover -s tests -v)
(cd pipeline && python -m binder_campaign --help)
```

The offline example runs a real subprocess through our runner, validates its output and verifies safe resume. It needs no model, token or GPU.

## Small Modal rehearsal

Each operator configures their own local profile. Credentials belong in `~/.modal.toml`, never in this repository. These commands prompt privately for credentials:

```sh
modal token set --profile my-profile
MODAL_PROFILE=my-profile modal billing summary
MODAL_PROFILE=my-profile modal run modal_app.py --stage prepare
MODAL_PROFILE=my-profile modal run modal_app.py --stage generate --run-id alice-seed43-001 --seed 43
MODAL_PROFILE=my-profile modal run modal_app.py --stage evaluate --run-id alice-seed43-001
```

Run `prepare` once per workspace to cache public pinned weights using a CPU worker. The other two stages each request one GPU (L40S preferred, A10G or A100 fallback), use a 15-minute worker timeout, and do not automatically retry. Preparation may take several minutes. Billable setup and worker time must be checked in Modal billing; model timing alone is not total cost. Account credits and caches are separate between workspaces.

Generation uses pinned RFD4-Proteina; evaluation uses Boltz-2 and directional ipSAE. Results and structure archives are saved under `results/<run-id>/`, which is ignored by Git. The worker also retains outputs on the workspace's `helixbridge-model-cache` Volume. Reusing an experiment ID with existing outputs is refused. This is a reproducibility pilot; see STATUS for observed qualification and limitations.

## New competition targets

```sh
cd pipeline
python -m binder_campaign prepare-targets --config config/targets-2026-11-13.json --output data/current-targets
```

This retrieves public UniProt intervals and checks endpoints. Use the **13 November configuration** for new preparation. `config/targets.json`, Earth task JSONs, historical target MSA and reference structure are frozen research inputs. The legacy task JSONs contain Earth paths and cannot be launched unchanged on a teammate's laptop or Modal. Read the guide before editing them.

## Repository map

| Path | Role |
|---|---|
| `pipeline/binder_campaign/` | Task records, resume/output checks, sequence and structure review |
| `pipeline/scripts/`, `pipeline/slurm/` | Existing Earth-specific model adapters, audits and experiments |
| `pipeline/config/` | Historical tasks plus separately dated current target manifest |
| `modal_app.py` | Small sequential generation/refolding rehearsal |
| `examples/il7ra-rehearsal/` | Frozen public target reference and historical target-only MSA |
| `outputs/` | Selected historical reports and research notes |
| `docs/` | Current handoff, provenance, official target snapshot and next tasks |

No experimental binding, KD, official admission score, private-database novelty certificate or submission eligibility is established by predicted confidence. All example candidate work is research-only. Upstream code/weights are fetched from their original sources under their respective licenses; see [third-party sources](docs/THIRD_PARTY.md).
