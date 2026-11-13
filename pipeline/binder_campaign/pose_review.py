"""Independent mapped-coordinate diagnostics; requires NumPy and Bio.PDB."""
import numpy as np
from Bio.PDB import Superimposer
from Bio.PDB.Atom import Atom
from Bio.PDB.MMCIF2Dict import MMCIF2Dict

from .structure import AA3


def read_pair(path, target_sequence, binder_sequence, positions):
    data = MMCIF2Dict(str(path))
    xyz = np.array([data['_atom_site.Cartn_x'], data['_atom_site.Cartn_y'], data['_atom_site.Cartn_z']], dtype=float).T
    names = np.array(data['_atom_site.label_atom_id'])
    ids = np.array(data['_atom_site.label_asym_id'])
    residues = np.array(data['_atom_site.label_seq_id'])
    components = np.array(data['_atom_site.label_comp_id'])
    elements = np.array(data['_atom_site.type_symbol'])
    ca = names == 'CA'
    sequences = {c: ''.join(AA3[n] for n in components[ca & (ids == c)]) for c in dict.fromkeys(ids.tolist())}
    tc = [c for c, s in sequences.items() if s == target_sequence]
    bc = [c for c, s in sequences.items() if s == binder_sequence]
    if len(sequences) != 2 or len(tc) != 1 or len(bc) != 1 or tc == bc or not np.isfinite(xyz).all():
        raise ValueError('Ambiguous sequence mapping or nonfinite coordinates')
    target_ids = residues[ca & (ids == tc[0])]
    if [int(r) for r in target_ids] not in [positions, list(range(1, len(positions) + 1))] \
            or [int(r) for r in residues[ca & (ids == bc[0])]] != list(range(1, len(binder_sequence) + 1)):
        raise ValueError('Residue numbering is not exact sequence order or declared positions')
    mapping = dict(zip(target_ids, positions))
    ti = np.where((ids == tc[0]) & (elements != 'H') & (elements != 'D'))[0]
    bi = np.where((ids == bc[0]) & (elements != 'H') & (elements != 'D'))[0]
    distances = np.linalg.norm(xyz[ti, None, :] - xyz[bi][None, :, :], axis=-1)
    contacts = sorted({mapping[residues[ti[i]]] for i in np.where((distances < 5).any(axis=1))[0]})
    return {'target_ca': xyz[ca & (ids == tc[0])], 'binder_ca': xyz[ca & (ids == bc[0])],
            'positions': positions, 'target_contacts_lt_5A': contacts,
            'heavy_atom_pairs_lt_2A': int((distances < 2).sum()), 'min_heavy_distance_A': float(distances.min())}


def align_pair(fixed, moving, positions):
    a = fixed['target_ca'][[fixed['positions'].index(p) for p in positions]]
    b = moving['target_ca'][[moving['positions'].index(p) for p in positions]]
    atoms = lambda xs: [Atom('CA', x, 0., 1., ' ', ' CA ', i, element='C') for i, x in enumerate(xs)]
    fit = Superimposer()
    fit.set_atoms(atoms(a), atoms(b))
    rot, trans = fit.rotran
    expected = fixed['binder_ca']
    rmsd = float(np.sqrt(np.mean(np.sum((moving['binder_ca'] @ rot + trans - expected) ** 2, axis=1))))
    bm, am = b.mean(0), a.mean(0)
    u, _, vt = np.linalg.svd((b - bm).T @ (a - am))
    if np.linalg.det(u @ vt) < 0:
        u[:, -1] *= -1
    independent = float(np.sqrt(np.mean(np.sum(((moving['binder_ca'] - bm) @ (u @ vt) + am - expected) ** 2, axis=1))))
    if not np.isclose(rmsd, independent, atol=1e-6, rtol=0):
        raise ValueError('Bio.PDB and direct-SVD alignment disagree')
    return {'target_fit_rmsd_A': float(fit.rms), 'target_aligned_binder_ca_rmsd_A': rmsd}


def target_region_differences(fixed, moving, anchors):
    """Expose target variability outside the reference core; never silently trim it."""
    a = fixed['target_ca'][[fixed['positions'].index(p) for p in anchors]]
    b = moving['target_ca'][[moving['positions'].index(p) for p in anchors]]
    atoms = lambda xs: [Atom('CA', x, 0., 1., ' ', ' CA ', i, element='C') for i,x in enumerate(xs)]
    fit = Superimposer()
    fit.set_atoms(atoms(a), atoms(b))
    rot, trans = fit.rotran
    differences = np.linalg.norm(moving['target_ca'] @ rot + trans - fixed['target_ca'], axis=1)
    return [{'target_interval': [lo,hi], 'rmsd_A': float(np.sqrt(np.mean(differences[lo-1:hi]**2))),
             'maximum_CA_displacement_A': float(differences[lo-1:hi].max())}
            for lo,hi in ((1,20),(21,36),(37,231),(232,236))]
