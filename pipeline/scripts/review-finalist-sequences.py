"""Review four existing research follow-ups against local sequences and mapped poses."""
import argparse
import csv
import itertools
import json
from pathlib import Path
import sys

import numpy as np
from Bio.Align import PairwiseAligner
from Bio.PDB import MMCIFParser, ShrakeRupley

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest, write_json
from binder_campaign.sequence_review import overlap_diagnostic, sequence_diagnostic
from binder_campaign.structure import AA3

parser = argparse.ArgumentParser()
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--output-dir', type=Path, required=True)
args = parser.parse_args()
workspace = args.workspace.resolve()
out = args.output_dir.resolve()
if out.exists():
    raise ValueError('Use a fresh review directory')
evidence = workspace / 'outputs/execution-evidence'
corpus_dir = evidence / 'finalist-reference-corpus-v1'
sources = {}


def record_source(path, expected=None):
    actual = digest(path)
    if expected is not None and actual != expected:
        raise ValueError('Source changed: ' + str(path))
    sources[str(path.relative_to(workspace))] = actual
    return path


def read(path):
    return json.loads(record_source(path).read_text())


manifest = read(corpus_dir / 'manifest.json')
for name, expected in manifest['sources'].items():
    record_source(workspace / name, expected)
for name, expected in manifest['outputs'].items():
    record_source(corpus_dir / name, expected)
corpus = read(corpus_dir / 'corpus.json')
if len(corpus['rows']) != manifest['row_count']:
    raise ValueError('Reference row count changed')
followup_path = workspace / 'outputs/controlled-campaign-review-2026-11-02-v4/REHEARSAL_ONLY_followups.csv'
selected = list(csv.DictReader(record_source(followup_path).open(newline='')))
if len(selected) != 4 or any(row['submission_eligible'] != 'false' for row in selected):
    raise ValueError('Expected exactly four research-only follow-ups')
target = read(workspace / 'pipeline/data/targets/il7ra/manifest.json')
uniprot = read(workspace / 'pipeline/data/targets/sources/P16871.json')
annotation = [{'position': f['location']['start']['value'],
               'evidence': f.get('evidences', [])}
              for f in uniprot['features'] if f['type'] == 'Glycosylation'
              and f['location']['start']['value'] <= 236]
pool = []
for folder in ['rfd4-il7ra', 'rfd4-il7ra-high', 'rfd4-il7ra-high-s43', 'rfd4-il7ra-high-s44',
               'mosaic-il7ra', *(f'rfd4-il7ra-campaign-s{x}' for x in range(101, 113))]:
    path = evidence / ('mosaic-il7ra-design-v1/candidates.json' if folder == 'mosaic-il7ra'
                       else f'{folder}-v1/candidates.json')
    row = read(path)['candidates'][0]
    pool.append({**row, 'campaign': folder})
by_id = {r['candidate_id']: r for r in pool}
aligner = PairwiseAligner(mode='global', match_score=1, mismatch_score=0,
                          open_gap_score=0, extend_gap_score=0)


def structure_context(path, sequence):
    structure = MMCIFParser(QUIET=True, auth_chains=False, auth_residues=False).get_structure('complex', str(path))
    model = structure[0]
    chains = list(model)
    seqs = {chain.id: ''.join(AA3[r.resname] for r in chain if 'CA' in r) for chain in chains}
    tc = [c for c in chains if seqs[c.id] == target['sequence']]
    bc = [c for c in chains if seqs[c.id] == sequence]
    if len(chains) != 2 or len(tc) != 1 or len(bc) != 1 or tc[0].id == bc[0].id:
        raise ValueError('Ambiguous pose chain mapping')
    tc, bc = tc[0], bc[0]
    target_atoms = [a for a in tc.get_atoms() if a.element not in {'H', 'D'}]
    binder_atoms = [a for a in bc.get_atoms() if a.element not in {'H', 'D'}]
    ta, ba = np.array([a.coord for a in target_atoms], dtype=float), np.array([a.coord for a in binder_atoms], dtype=float)
    if not np.isfinite(ta).all() or not np.isfinite(ba).all():
        raise ValueError('Non-finite coordinates')
    if len(list(tc)) != 236 or len(list(bc)) != len(sequence):
        raise ValueError('Incomplete residue mapping')
    distances = np.linalg.norm(ta[:, None, :] - ba[None, :, :], axis=-1)
    contacts = sorted({target_atoms[i].parent.id[1] for i in np.where((distances < 5).any(axis=1))[0]})
    # Solvent accessibility on unmodified predicted coordinates; no glycan or disulfide inference.
    sr = ShrakeRupley(probe_radius=1.4, n_points=960)
    sr.compute(model, level='A')
    motifs = sequence_diagnostic(sequence)
    positions = sorted(set(motifs['cysteine_positions'] + [r['position'] for r in motifs['N_glycosylation_sequons']]))
    site_data = []
    target_coords = np.array([a.coord for a in target_atoms])
    for position in positions:
        residue = bc[(' ', position, ' ')]
        name = 'SG' if sequence[position - 1] == 'C' else 'ND2'
        if name not in residue:
            raise ValueError('Required motif atom missing')
        atom = residue[name]
        site_data.append({'binder_position': position, 'amino_acid': sequence[position - 1],
                          'atom': name, 'atom_sasa_complex_A2': float(atom.sasa),
                          'atom_min_target_heavy_distance_A': float(np.linalg.norm(target_coords - atom.coord, axis=1).min()),
                          'residue_min_target_heavy_distance_A': float(min(np.linalg.norm(target_coords - a.coord, axis=1).min()
                              for a in residue if a.element not in {'H', 'D'}))})
    glycan_context = []
    for entry in annotation:
        residue = tc[(' ', entry['position'], ' ')]
        if residue.resname != 'ASN' or 'ND2' not in residue:
            raise ValueError('Target sequon mapping changed')
        glycan_context.append({**entry, 'min_unmodified_ND2_to_binder_heavy_A':
                               float(np.linalg.norm(ba - residue['ND2'].coord, axis=1).min())})
    return {'structure_sha256': digest(path), 'target_chain': tc.id, 'binder_chain': bc.id,
            'target_contact_positions_lt_5A': contacts,
            'signal_peptide_contact_positions': [p for p in contacts if p <= 20],
            'heavy_atom_pairs_lt_2A': int((distances < 2).sum()),
            'binder_motif_atom_geometry': site_data, 'target_glycosylation_annotation_geometry': glycan_context,
            'sasa_method': 'Bio.PDB ShrakeRupley; 1.4 A probe; 960 points; unmodified complete complex',
            'scope': 'Predicted unmodified geometry only; no occupancy, glycan clashes, disulfide state or expression guarantee'}


results = []
for selected_row in selected:
    row = by_id[selected_row['candidate_id']]
    sequence = row['sequence']
    if sequence != selected_row['sequence']:
        raise ValueError('Selected sequence changed')
    checks = []
    for reference in corpus['rows']:
        diagnostic = overlap_diagnostic(sequence, reference['sequence'])
        lcs = float(aligner.score(sequence, reference['sequence']))
        checks.append({'source': reference['source'], 'id': reference['id'], 'target': reference['target'],
                       **diagnostic, 'lcs_fraction_of_longer': lcs / max(len(sequence), len(reference['sequence']))})
    top = sorted(checks, key=lambda r: (-r['longest_identical_contiguous_length'], -r['lcs_fraction_of_longer'],
                                      r['source'], r['id']))[:5]
    closest_lcs = sorted(checks, key=lambda r: (-r['lcs_fraction_of_longer'], r['source'], r['id']))[:5]
    pool_checks = [{'candidate_id': other['candidate_id'], **overlap_diagnostic(sequence, other['sequence'])}
                   for other in pool if other['candidate_id'] != row['candidate_id']]
    review_path = evidence / f'{row["campaign"]}-review-v1/review.json'
    review = read(review_path)
    context_path = review_path.parent / 'target-context-audit.json'
    context = read(context_path)
    if review['candidate_id'] != row['candidate_id'] or review['sequence'] != sequence \
            or context['review_sha256'] != digest(review_path):
        raise ValueError('Review identity changed')
    poses = {}
    for model in ('esmfold2', 'boltz'):
        path = evidence / f'{row["campaign"]}-{model}-v1/prediction/model.cif'
        record_source(path, review['predictions'][model]['model_cif_sha256'])
        poses[model] = structure_context(path, sequence)
        if poses[model]['target_contact_positions_lt_5A'] != context['poses'][model]['target_contact_positions_lt_5a']:
            raise ValueError('Independent contact calculation disagrees')
        if poses[model]['heavy_atom_pairs_lt_2A'] != review['predictions'][model]['contacts']['heavy_atom_pairs_lt_2A']:
            raise ValueError('Independent heavy-atom check disagrees')
        for reported in context['poses'][model]['target_sequon_geometry']:
            measured = next(g for g in poses[model]['target_glycosylation_annotation_geometry'] if g['position'] == reported['position'])
            if not np.isclose(measured['min_unmodified_ND2_to_binder_heavy_A'],
                              reported['min_nd2_to_binder_heavy_atom_angstrom'], atol=1e-4):
                raise ValueError('Independent sequon distance check disagrees')
    results.append({'candidate_id': row['candidate_id'], 'generation_seed': row['generator_audit']['seed'],
        'sequence': sequence, 'sequence_diagnostics': sequence_diagnostic(sequence),
        'public_reference_comparison': {'rows_compared': len(checks), 'top_exact_contiguous_matches': top,
            'top_lcs_matches': closest_lcs, 'exact_duplicates': [r for r in checks if r['exact_duplicate']],
            'over_90pct_contiguous_flags': [r for r in checks if r['over_90pct_contiguous_in_either_direction']],
            'interpretation': 'A limited-corpus diagnostic only. Contiguous 100% overlap uses a strict >90% coverage check in either direction; official gapped/coverage handling is unspecified. LCS is permissive and is not alignment identity or homology.'},
        'internal_pool_comparisons': pool_checks, 'poses': poses, 'submission_eligible': False})
out.mkdir(parents=True)
write_json(out / 'sequence-context-review.json', {'research_followups': results,
    'public_corpus_rows': manifest['row_count'], 'public_corpus_unique_sequences': manifest['unique_sequences'],
    'internal_pool_count': len(pool), 'uniprot_entry_audit': uniprot['entryAudit'],
    'scope': 'Local evaluation only; no candidate sequence uploaded; global novelty and cross-team duplicates remain unresolved',
    'submission_eligible_count': 0})
write_json(out / 'manifest.json', {'sources': sources, 'outputs': {
    'sequence-context-review.json': digest(out / 'sequence-context-review.json')}, 'script_sha256': digest(__file__)})
print(json.dumps({'status': 'reviewed', 'followups': len(results), 'corpus_rows': len(corpus['rows']),
    'exact_public_duplicates': sum(len(r['public_reference_comparison']['exact_duplicates']) for r in results),
    'over_90pct_public_flags': sum(len(r['public_reference_comparison']['over_90pct_contiguous_flags']) for r in results)}))
