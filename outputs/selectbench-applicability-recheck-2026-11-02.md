# SelectBench applicability refresh

Primary sources checked again with TinyFish and direct repository retrieval:
- https://github.com/lovetaro/selectbench
- https://arxiv.org/html/2610.24124v1

The current GitHub head returned by the public API is
`1932c55c17033923511e611d100c25e8ecf96f2f`, committed20October2026, initial
public release. The retrieved README and commit metadata are preserved in
`work/selectbench-readme-recheck-2026-11-02.md` and
`work/selectbench-commit-recheck-2026-11-02.json`.

The evaluator consumes SDF/SMILES small molecules, evaluates on/off receptor
pockets with Vina or optional Boltz small-molecule affinity scoring, and reports
small-molecule quality/selectivity metrics. It is not a protein-minibinder
experimental accuracy dataset or a direct evaluator for our60-aa sequences.
No SelectBench code was installed or docking score added to this campaign.

Applicable ideas are fixed sampling budgets, explicit on/off-target endpoints,
separate quality dimensions and known-ligand similarity disclosure. Applying
those principles to protein binders still requires compatible protein assays,
appropriate structural predictors and an independently justified off-target
panel. The existing campaign is not expanded to new targets by this review.
