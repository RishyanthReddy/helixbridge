# Status at the team handoff

Updated 13 November 2026. Verification results are in `VERIFICATION.md`.

## Established work

- Existing source snapshot: commit recorded in `source-provenance.json`. All tracked source files were preserved, along with the unfinished lead-repair preparation script. The original working repository remains untouched.
- Task runner, artifact hashes, validated resume, sequence checks, safe extraction and benchmark-analysis tests are present.
- Historical Earth experiments include BindCraft2 controls, RFD4 generation, ESMFold2 and Boltz-2 prediction, interface/pose review, seed repeats, a site-diversity pilot, a BoltzGen reserve and constrained repair of a research lead. Selected reports are in `../outputs/`.
- The latest repair report identifies a provisional computational follow-up. Neither that variant nor any example in this repository is a validated binder or eligible submission.
- Two supplied Modal tokens authenticated successfully to separate workspaces. No token is included here. Current remaining credits are not established by the billing summary.

## Target and rule updates

Current official deployed target records were fetched on 13 November; source URL and checksum are in `official-targets-2026-11-13.json`. The target configuration is in `../pipeline/config/targets-2026-11-13.json`.

| Target | Current interval | Change from historical configuration |
|---|---|---|
| EGFR | 1–645 | None |
| TNF-alpha | 77–233 | None |
| GLP1R | 24–432 | Old input was21–139 |
| TfR1 | 89–760 | None |
| TL1A | 72–251 | None |
| TNFR1 | 30–211 | Old input began at1 |
| IL7Ra | 21–239 | Old input was1–236 |

Tag metadata is retained in the current manifest. The frozen generation reference covers only37–231. Historical refolding used1–236, so current-target re-evaluation and a new target MSA are required before interpreting results for this competition. Do not trim an old MSA blindly and call it a current-condition evaluation.

The public rules specify novelty thresholds of at least80% aligned coverage and at most70% identity. Organizer clarification supplied by the captain names MMseqs2, query-length coverage and gaps counted as differences; the reference database is private. A public local sequence check cannot certify organizer eligibility.

## Limits and next work

- The small historical RFD4 generation→Boltz-2/ipSAE Modal path passed. All35 tests and the offline example also passed from a fresh clone. See VERIFICATION.
- Earth scripts retain original machine paths and historical settings. Their presence is source preservation, not a claim of general portability.
- Full evidence archives, downloaded repositories, benchmark tables and model checkpoints are intentionally excluded. Selected historical report links may refer to those original local archives; they are not promised as included files. New evidence is downloaded from each Modal run.
- Updated official-target prediction, complete portable pose/context audits, exact official-screen settings, broader ranking validation, VHH qualification, other target campaigns and official export remain unfinished.
