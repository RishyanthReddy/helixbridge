import importlib.util
from pathlib import Path
import unittest

try:
    import pandas as pd
    import Bio
except ImportError:
    pd = None


@unittest.skipIf(pd is None, 'Requires isolated validation dependencies')
class ScreenGroupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / 'scripts/validate-screen-groups.py'
        spec = importlib.util.spec_from_file_location('groups', path)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_shared_backbone_is_purged_across_target_boundary(self):
        frame = pd.DataFrame({'uuid':['a','b','c'], 'target':['held','train','train'],
                              'sequence':['ACDEFGHIKL','YYYYYYYYYY','PPPPPPPPPP']})
        prov = pd.DataFrame({'uuid':['a','b','c'], 'prov_root_backbone_id':['bb1','bb1','bb2'],
                             'prov_parent_design_id':[None,None,None]})
        steps = pd.DataFrame(columns=['uuid','ancestor_design_id'])
        families,_ = self.module.build_families(frame,prov,steps)
        frame = frame.merge(families,on='uuid')
        train,held = self.module.fold_split(frame,'held')
        self.assertEqual(train.uuid.tolist(),['c'])
        self.assertFalse(set(train.family) & set(held.family))

    def test_high_sequence_similarity_connects_without_ancestry(self):
        frame = pd.DataFrame({'uuid':['a','b'], 'sequence':['ACDEFGHIKL','ACDEFGHIKA']})
        prov = pd.DataFrame({'uuid':['a','b'], 'prov_root_backbone_id':[None,None],
                             'prov_parent_design_id':[None,None]})
        steps = pd.DataFrame(columns=['uuid','ancestor_design_id'])
        families,links = self.module.build_families(frame,prov,steps)
        self.assertEqual(links,1)
        self.assertEqual(families.family.nunique(),1)

    def test_direct_parent_identifier_connects_to_the_named_design(self):
        frame = pd.DataFrame({'uuid':['a','b'], 'sequence':['AAAAAAAAAA','PPPPPPPPPP']})
        prov = pd.DataFrame({'uuid':['a','b'], 'full_name':['design_a','design_b'],
                             'prov_root_backbone_id':[None,None],
                             'prov_parent_design_id':[None,'design_a']})
        families,_ = self.module.build_families(frame,prov,pd.DataFrame(columns=['uuid','ancestor_design_id']))
        self.assertEqual(families.family.nunique(),1)

    def test_held_target_labels_cannot_change_its_selected_rule(self):
        rows = []
        for target in ['held','train1','train2']:
            for i in range(30):
                rows.append({'uuid':f'{target}{i}', 'family':f'{target}{i}', 'target':target,
                             'vendor_agreement':'both_bind' if i>14 else 'neither_bind',
                             'ef2full_seed0_target_rank':i/30, 'boltz2_seed0_target_rank':(29-i)/30,
                             'consensus_mean_seed0':.5, 'consensus_min_seed0':min(i,29-i)/30})
        frame = pd.DataFrame(rows)
        first = self.module.held_target_folds(frame,'vendor_concordant').set_index('held_target')
        frame.loc[frame.target=='held','vendor_agreement']='both_bind'
        second = self.module.held_target_folds(frame,'vendor_concordant').set_index('held_target')
        self.assertEqual(first.loc['held','chosen_rule'],second.loc['held','chosen_rule'])


if __name__ == '__main__':
    unittest.main()
