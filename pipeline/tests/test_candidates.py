import csv
import json
from pathlib import Path
import tempfile
import unittest
from binder_campaign.candidates import import_bc2, import_rfd4, export_draft
from binder_campaign.runner import digest


class CandidateTests(unittest.TestCase):
    def test_rfd4_rehearsal_rejects_changed_pose_or_wrong_target_and_cannot_be_exported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            structure = root / 'model.cif'
            structure.write_text('data_fixture')
            target = root / 'target.json'
            target.write_text(json.dumps({'id':'il7ra','format':'minibinder','min_length':40,'max_length':100}))
            audit = {'reference_audit':{'role':'reference_rehearsal_only','target_id':'il7ra'},
                     'generated_structure':str(structure), 'generated_sha256':digest(structure),
                     'binder_sequence':'A'*60, 'code_revision':'pinned', 'seed':42,
                     'target_chain':'A', 'binder_chain':'B'}
            source = root / 'audit.json'
            source.write_text(json.dumps(audit))
            records = root / 'records.json'
            imported = import_rfd4(source,target,records)
            self.assertFalse(imported[0]['submission_eligible'])
            with self.assertRaisesRegex(ValueError,'rehearsal'):
                export_draft(records,root/'draft.csv',[imported[0]['candidate_id']])
            structure.write_text('changed pose')
            with self.assertRaisesRegex(ValueError,'structure changed'):
                import_rfd4(source,target,records)
            audit['reference_audit']['target_id'] = 'different'
            source.write_text(json.dumps(audit))
            with self.assertRaisesRegex(ValueError,'target does not match'):
                import_rfd4(source,target,records)

    def test_real_bc2_layout_keeps_rejected_variant_pose_and_backbone_family(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            refolds = root / '2_Refolded'
            (refolds / 'Complexes').mkdir(parents=True)
            (root / 'campaign_metadata.json').write_text('{"seed":42}')
            table = refolds / '!_Refolded.csv'
            designs = ['trajectory1_candidate1', 'trajectory1_candidate2']
            for design in designs:
                (refolds / 'Complexes' / (design + '.cif')).write_text('data_' + design)
            with table.open('w', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(['design', 'Binder_Sequence', 'outcome', 'failed_filters'])
                writer.writerows([[designs[0], 'A'*60, 'rejected', 'i_pTM'],
                                  [designs[1], 'G'*60, 'rejected', 'i_pAE']])
            target = root / 'target.json'
            target.write_text(json.dumps({'id':'test', 'format':'minibinder', 'min_length':40, 'max_length':100}))
            records = import_bc2(table, target, root/'records.json', 'revision', 'reference_rehearsal')
            self.assertEqual([r['backbone_family_id'] for r in records], ['trajectory1', 'trajectory1'])
            self.assertNotEqual(records[0]['generator_structure_sha256'], records[1]['generator_structure_sha256'])
            self.assertEqual(records[1]['generator_structure'], str((refolds/'Complexes'/(designs[1]+'.cif')).resolve()))
            self.assertTrue(all(r['generator_metrics']['outcome'] == 'rejected' for r in records))
            self.assertTrue(all(r['independent_prediction_status'] == 'not_run' and not r['submission_eligible'] for r in records))

    def test_rehearsals_invalid_sequences_and_duplicates_cannot_leak_to_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); table=root/'table.csv'; manifest=root/'target.json'; output=root/'records.json'
            manifest.write_text(json.dumps({"id":"test","format":"minibinder","min_length":40,"max_length":100}))
            with table.open('w', newline='') as stream:
                writer=csv.writer(stream); writer.writerow(['Binder_Sequence'])
                writer.writerows([['A'*60],['A'*60],['A'*59+'X']])
            rows=import_bc2(table,manifest,output,'revision','reference_rehearsal')
            self.assertIn('exact_duplicate',rows[1]['qc_reasons'])
            self.assertIn('invalid_alphabet_or_multichain',rows[2]['qc_reasons'])
            with self.assertRaisesRegex(ValueError,'rehearsal'):
                export_draft(output,root/'draft.csv',[rows[0]['candidate_id']])

    def test_exit_zero_table_without_sequence_column_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); (root/'table.csv').write_text('score\n0.8\n')
            (root/'target.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'Binder_Sequence'):
                import_bc2(root/'table.csv',root/'target.json',root/'records.json','revision','reference_rehearsal')
