# Binder-design pipeline research for one L40S, 48 GB

> Competition update, November 1, 2026: the revealed brief changes the deadline to November 30, fixes five VHH and two minibinder tracks, and specifies ESMFold2/ipSAE screening for open-registration entries. See [the revealed-brief audit](changjiang-revealed-brief-2026-11-01.md) before using the historical competition assumptions below.

Research dates: October 13–14, 2026. Scope: the seven unique repositories originally supplied, additional open design engines, Kaggle and Colab resources, experimentally evaluated competitions, and datasets for evaluating candidate selection. This is a source and architecture review. No GPU inference, installation, or Earth-cluster benchmark was performed.

**Recommendation after the broader search**

Keep BindCraft2 as the first operational baseline, with the original BindCraft as an evidence-backed comparator. Benchmark Mosaic next. Choose one complementary generator from PXDesign, BoltzGen, and Proteina-Complexa after small, comparable L40S pilots. Build common candidate records and a shared evaluation workflow before adding a large web interface.

The first working campaign should have one generator, one separate complex predictor, explicit geometry checks, diversity selection, and complete provenance. A successful pilot means actual GPU execution, resumable jobs, correct chain/residue mapping, measured runtime and memory, and traceable exports. It does not mean experimentally demonstrated binding.

**What the winning submissions establish**

| Campaign | Evidence found | Reusable lesson | Qualification |
|---|---|---|---|
| Adaptyv EGFR round 1 | Organizer reports BindCraft's winning eligible design at approximately 491 nM. | AF2-guided design has genuine competition evidence. | Original BindCraft; do not attribute this result to BindCraft2. |
| Adaptyv EGFR round 2 | Cradle won overall using an optimized cetuximab variant; BindCraft received the de novo distinction. | Separate optimization of an existing binder from creation of a new interface. | Cradle's proprietary system is not a downloadable winning pipeline. |
| Adaptyv × muni TREM2 hackathon | Organizer attributes the best measured affinity, 1.11 nM, to Mosaic. | Mosaic deserves a serious pilot; PXDesign is another credible candidate. | Small selected cohorts and different team practices prevent a general model ranking. |
| GEM × Adaptyv RBX1 | Mandrake reports its ORBIT design bound at about 26 nM. | Structural context and target-specific preparation can determine whether a campaign works. | Team-reported result; no complete reusable ORBIT release verified in this search. |
| Public RBX1 pipeline by Reilly Osadchey | Documents seven designs shortlisted from 100 submissions and publishes pipeline code. | A useful example of joining generation, prediction, metrics and export. | Shortlisting is not confirmed binding; its README does not establish seven wet-lab hits. |
| Bits to Binders | Public experimental data and analysis for CD20-directed CAR binder designs. | Useful for studying diversity and the gap between structure scores and function. | CAR-cell enrichment and purified-protein affinity are different endpoints. |

Sources: [EGFR round 1 organizer analysis](https://www.adaptyvbio.com/blog/po102), [EGFR round 2 organizer analysis](https://www.adaptyvbio.com/blog/po104), [TREM2 organizer analysis](https://www.adaptyvbio.com/blog/agents-vs-humans), [Mandrake's RBX1 account](https://research.mandrake.bio/p/we-dont-even-design-binders), [public RBX1 pipeline](https://github.com/reillyosadchey/rbx1-binder-design), [Bits to Binders data](https://github.com/kosonocky/bits-to-binders).

For TREM2, Adaptyv reports 37 binders among 100 tested designs. Its tool table records Mosaic at 4/6 and PXDesign at 20/38. These are outcomes for the selected designs in that campaign, not expected hit rates for our targets. The small Mosaic denominator especially warrants restraint.

A separate Mosaic case study reports best-method outcomes of 8/10 for PD-L1 and 7/10 for IL7RA. The authors sampled 2,500 candidates per campaign before selecting ten. That sampling budget and the assay detection threshold matter when interpreting the percentages. [Mosaic case study](https://blog.escalante.bio/minibinder-design-is-just-not-that-hard/)

BoltzGen has substantial experimental evaluation, but the manuscript changed between versions. The newer v2 reports screening hits for nanobodies on six of ten novel targets and miniproteins on five of ten, after generation of 60,000 candidates per modality per target and selection of fifteen. These are target-coverage results from large campaigns, not a 60% per-sequence success probability. Use the newer manuscript when describing the evidence. [BoltzGen v2](https://www.biorxiv.org/content/10.1101/2025.11.20.689494v2.full)

**Tools worth considering, in order of use**

| Tool | Role | Decision for our project |
|---|---|---|
| BindCraft2 | Integrated binder generation and evaluation | Establish the first operational baseline; pin a revision and limit initial workers. |
| Original BindCraft | Mature design baseline with published and competition evidence | Preserve as a fallback/comparator if BC2 installation or behavior is problematic. |
| Mosaic | Flexible differentiable design with multiple model objectives | Highest-priority new research branch; begin from a benign public example. |
| PXDesign | Diffusion generator with Protenix and AF2-IG evaluation | Pilot as a complementary generator if installation effort is manageable. |
| BoltzGen | Integrated atomistic generation, refolding and selection | Strong alternative, conditional on driver/runtime compatibility. |
| Proteina-Complexa | Atomistic flow-based generation and inference-time search | Keep in the pilot shortlist; use measured efficiency to decide promotion. |
| RFdiffusion3 + SolubleMPNN | Modular backbone/sequence branch | Useful when structural conditioning calls for it; avoid adding by default merely to enlarge the stack. |
| mBER | VHH-specific design | Add if official format constraints and target biology favor nanobodies. |
| Boltz-2 | Complex prediction | Shared evaluator for AF2-generated candidates; retain full PAE and coordinate outputs. |
| ipSAE | Interface confidence calculation | Add as a component metric with explicit predictor, direction and cutoff metadata. |
| ProtFlow | Python workflow orchestration with Slurm support | Evaluate against a thin Slurm driver; existing competition usage makes it relevant. |
| Adaptyv protein-design-skills | Agent workflow instructions and compute wrappers | Use as a workflow reference, adapting cloud assumptions to Earth. |

Mosaic's maintainers explicitly caution that it requires tuning and can generate designs failing simple computational checks. Its MIT code provides a composable framework, not a universally tuned replacement for BindCraft. [Mosaic repository](https://github.com/escalante-bio/mosaic)

PXDesign supplies a local pipeline and a hosted server. Its own README emphasizes installation complexity and custom kernels; the hosted option is advertised as free, with additional quota available by application. This is a possible exploratory route, not an assumed entitlement or a reason to upload targets automatically. [PXDesign repository](https://github.com/bytedance/PXDesign)

ProtFlow explicitly supports Slurm and separate model environments; its EGFR tutorial joins RFdiffusion, LigandMPNN, Rosetta, ESMFold and ColabFold. It is distinct from Adaptyv's ProteinFlow data-processing library. [ProtFlow](https://github.com/mabr3112/ProtFlow), [binder tutorial](https://github.com/mabr3112/ProtFlow/blob/master/docs/source/tutorials/binder_design.rst)

**How the original seven repositories fit**

BindCraft2 and Complexa are engines. mBER is a specialist VHH engine. ProtDesign-MVP contributes transparent QC and analysis, with a very small real demonstration. ProteaFlow offers broad orchestration and a results interface. Ahhmedsamehh/BinderFlow is a Nextflow implementation whose current README states that real GPU inference and container builds remain unverified. Surface Atlas contributes evidence/provenance/reporting and uses separate tools for model execution.

The ProteaFlow BindCraft adapter targets the original BindCraft interface. A BC2 adapter must explicitly translate inputs and outputs. Its pocket-constrained Boltz path should not serve as our only independent pose check. [ProteaFlow integration code](https://github.com/mas-gu/binderflow/blob/main/generate_binders.py)

ProtDesign-MVP's distinction between binder-only best-fit RMSD and target-aligned binder RMSD is worth keeping. Its Cα contact comparison also avoids treating poly-glycine reference backbones and full-sidechain predictions as equivalent heavy-atom interfaces. Generalize its RFdiffusion assumptions before importing BC2 or atomistic generators. [ProtDesign-MVP](https://github.com/LiviaPei/ProtDesign-MVP)

**Kaggle, Colab and other platforms**

The search found [Tutorial3_RFDiffusion](https://www.kaggle.com/code/aivuhong/tutorial3-rfdiffusion), with a recorded successful P100 run. Kaggle's rendered page did not expose the full notebook through the browsing tool, so its implementation and scientific completeness remain unverified. It is an educational/resource lead, not evidence of a winning experimentally validated binder pipeline.

Kaggle also has reusable [Boltz-1 inference code](https://www.kaggle.com/code/youhanlee/boltz-1-inference-submission) and [winning RNA-folding write-ups](https://www.kaggle.com/competitions/stanford-rna-3d-folding/writeups/3rd-place-solution). These concern RNA structure prediction. They may help with notebook packaging, caching and diverse prediction selection, but their leaderboard outcomes do not validate protein-binder affinity or justify copying their RNA fine-tuning strategy.

I did not verify an openly reproducible Kaggle winner for an experimentally evaluated protein-binder competition. Public Colab notebooks and GitHub competition submissions were more directly relevant. With university GPU access, production should run under Slurm; notebooks can support inspection and small interactive tests.

Adaptyv's skills repository provides 24 Claude Code skills and Modal-oriented execution references. Its standard pipeline includes BoltzGen or RFdiffusion/MPNN plus structure validation and QC. Its published timing and pass-rate examples are planning estimates, not measurements on Earth. We can reuse workflow structure without depending on that agent runtime or paid cloud compute. [Skills](https://github.com/adaptyvbio/protein-design-skills), [standard pipeline](https://github.com/adaptyvbio/protein-design-skills/blob/main/docs/standard-pipeline.md)

Anthropic's public [binder-design dataset](https://huggingface.co/datasets/Anthropic/claude-protein-binder-design) supplies linked design provenance, predictor outputs and wet-lab records. It is useful for evaluator research. Its [inference optimization kits](https://github.com/anthropics/uplifting-biomolecular-modeling) are a separate reference release, primarily configured for H100 80 GB and explicitly unmaintained. Do not assume their acceleration modes work unchanged on L40S.

**Datasets we can use before spending GPU time**

| Dataset | Proposed use | Main limitation |
|---|---|---|
| Adaptyv EGFR rounds 1 and 2 | Test parsers, labels, metric direction and ranking behavior. | One target; mixes de novo and existing-binder optimization and includes controls. |
| TREM2 hackathon | Another target and contemporary methods with measured results. | Small, shortlisted sample; team and method are confounded. |
| Overath et al. meta-analysis | Evaluate simple ranking rules across targets. | Predictor-specific features and heterogeneous experimental sources. |
| Bits to Binders | Assess sequence redundancy, method diversity and functional outcomes. | Cell-based function differs from affinity screening. |
| Anthropic binder-design release | Study agreement between predictors/vendors and retain provenance. | Selection/campaign effects; missing or censored measurements require careful interpretation. |

The [Overath dataset record](https://zenodo.org/records/15722219) contains an approximately 82 MB feature table and separately archived predictions. It offers binary experimental labels, target IDs and source-publication IDs. We can start with tables rather than downloading all coordinates.

Its [meta-analysis](https://www.biorxiv.org/content/10.1101/2025.08.14.670059v2) reports stronger prioritization from interface-focused scores, particularly AF3 ipSAE, combined with orthogonal interface features. That result does not automatically validate the same numerical threshold for Boltz-2 or every target. Record model and metric definitions explicitly.

I downloaded and parsed the official EGFR result summaries as a basic evidence check. Round 1 has 202 table rows; round 2 has 402. These include controls and are not clean submission denominators. The round-2 file contains 55 `true`, 325 `false`, and 22 `unknown` binding labels. The Cradle winning row has KD approximately 1.207 nM. Unknown values must remain unknown; non-expression, no detected binding, assay failure and censored affinity need separate labels. These counts are a table audit, not a new performance benchmark. [Round 1 data](https://github.com/adaptyvbio/egfr_competition_1), [round 2 data](https://github.com/adaptyvbio/egfr_competition_2)

For any learned ranker, split by target and sequence family rather than random rows. Compare against simple baselines first. Use precision among the submitted top K and target coverage, while retaining failure and uncertainty categories. A random row split can reward memorizing related sequences or known binder families.

**Evaluation architecture**

Proposed flow:

```text
Official target / construct / assay requirements
  → reviewed structural context and mapped residues
  → generator-specific campaigns
  → common candidate records
  → cheap validity checks and deduplication
  → separate complex predictions
  → interface confidence + target-frame geometry + sequence liabilities
  → sequence / fold / binding-site clustering
  → reviewed, diverse submission shortlist
```

The common record should retain generator revision, checkpoint identity, settings, seed, target construct, chain mapping, original pose, all evaluation poses, runtime, peak memory and failure reasons. Preserve raw scores rather than only a composite rank.

The independence rule depends on the generator. Boltz-2 is a useful different-model check for AF2-generated designs. For Mosaic designs optimized through Boltz, Boltz-based scoring is partly circular; use an additional architecture for finalists, such as AF2, RF3, Chai or a compatible Protenix configuration. These predictors can share training data, so agreement still does not establish affinity.

Main metrics: binder fold consistency; binder pose after target alignment; actual interface contacts; interface PAE/ipSAE; clashes; buried surface/shape descriptors where available; obvious sequence liabilities; and novelty/diversity. Compare interface metrics within matched construct and prediction settings. Large interfaces or high confidence alone are not sufficient selection objectives.

Use unconstrained predictions for the primary pose cross-check. Constrained/template-guided predictions can answer other questions, but label them separately. Preserve target MSA inputs and reuse them where appropriate; binder single-sequence input should be an explicit design choice.

Boltz's affinity head is for small-molecule ligands. Do not use it to report protein-binder KD. [Boltz input documentation](https://github.com/jwohlwend/boltz/blob/main/docs/prediction.md#properties-affinity)

**One L40S, 48 GB: operational constraints**

Start each new engine with a single active GPU process and batch size one, then raise concurrency only after observing memory. Generation and expensive evaluation should initially run sequentially within an allocation. Slurm must remain the device/resource authority. One physical card does not imply continuous availability.

BindCraft2 automatically packs workers onto visible cards. Its documentation warns that its host-memory cap reads node availability rather than the Slurm job limit. Set one worker initially and benchmark before increasing it. Its installer must match the compute-node driver. [BC2 installation guide](https://github.com/PacesaLab/BindCraft2/blob/main/docs/source/installation.md)

Current BoltzGen includes ESMFold2 scoring for polymer-binder protocols, approximately 33 GB of additional disk downloads, and a CUDA-13-compatible driver requirement. This is a software-stack constraint beyond having enough nominal VRAM. Pin and test the full protocol rather than assuming older tutorials match current main. [ESMFold2 integration](https://github.com/HannesStark/boltzgen/blob/main/docs/esmfold2.md)

The repository's H200 benchmark records roughly 15–29 GiB peak reserved memory for several small example workloads. Those measurements make limited L40S tests plausible, but do not establish L40S runtime or maximum target size. The documented timings must not be transferred directly across GPU models. [Benchmark artifact](https://github.com/HannesStark/boltzgen/blob/main/docs/benchmarks/esmfold2-h200-20261005.json)

Complexa's hardware reference labels its 40 GB protein-binder recommendation empirical. mBER reports testing on L40S and recommends at least 32 GB. Both are plausible pilots, subject to target and configuration. [Complexa hardware](https://github.com/NVIDIA-BioNeMo/Proteina-Complexa/blob/dev/skills/_shared/references/hardware.md), [mBER](https://github.com/manifoldbio/mber-open)

No model fitting guarantee is inferred from these documents. Backpropagation memory, complex length, recycles, samples, precision and retained outputs all affect feasibility. Benchmark wall-clock, compilation cost, reserved memory, CPU/RAM, and valid diverse outputs per GPU-hour.

**Competition-specific consequences**

The SJTU event's official details remain due November 1, with submissions November 15. Its published high-level goal is nanobody/minibinder design and experimental affinity ranking. [SJTU competition](https://aiprotein.sjtu.edu.cn/?lang=en)

The related Anthropic × Adaptyv competition already shows that requirements can go beyond affinity. Its EGFR challenge requests acidic-pH-selective binding plus mouse cross-reactivity; its TNF challenge requests the opposite pH direction. Ordinary co-folding does not establish pH-selectivity. If SJTU adopts related tasks, we will need challenge-specific evaluation hypotheses and submission categories rather than one universal ranking formula. Do not assume the two events share exact rules. [EGFR brief](https://proteinbase.com/competitions/anthropic-adaptyv-2026/challenges/egfr), [TNF brief](https://proteinbase.com/competitions/anthropic-adaptyv-2026/challenges/tnf-alpha)

**Licensing and release choices**

BC2 currently permits internal use and provision of outputs but restricts third-party hosted functionality. Complexa's upstream code is Apache 2.0, with NVIDIA Open Model License weights; its current model card states commercial readiness, conflicting with ProteaFlow's research-only summary. Mosaic and BoltzGen repositories are MIT, while individual dependencies retain their own terms. EGFR datasets have database-license terms separate from code. Review exact components when publishing or hosting.

Sources: [BC2 license](https://github.com/PacesaLab/BindCraft2/blob/main/LICENSE), [Complexa code](https://github.com/NVIDIA-BioNeMo/Proteina-Complexa/blob/dev/licenses/license_code.txt), [Complexa model card](https://github.com/NVIDIA-BioNeMo/Proteina-Complexa/blob/dev/assets/model_card/overview.md), [Mosaic license](https://github.com/escalante-bio/mosaic/blob/main/LICENSE), [BoltzGen license](https://github.com/HannesStark/boltzgen/blob/main/LICENSE).

**Recommended next implementation decision**

1. Prepare the common record and a minimal Slurm driver; compare ProtFlow if its runners reduce work.
2. Run a real BC2 pilot on a benign supplied example, preserving failures and resumability.
3. Reproduce a small benign Mosaic example and evaluate with a separate predictor.
4. Pilot one generative alternative. Prefer PXDesign if the local stack works; consider BoltzGen if its current scoring runtime fits the driver; retain Complexa as another candidate.
5. Compare time, memory and diverse computationally viable candidates under matched budgets. Promote at most two generators for the initial competition campaign.
6. Use public experimental tables to test ranking logic, without fitting a complicated model until simple baselines and held-out-target evaluation justify it.
7. Resolve target-specific format, functionality and submission limits from the November 1 brief.

This is a proposed implementation sequence. No installation, paid compute, assay purchase, target upload, or competition submission was made during this research.
