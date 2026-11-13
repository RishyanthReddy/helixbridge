import unittest
from binder_campaign.budget import admission


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.ledger={'gpu_seconds_cap':5400,'max_concurrent_gpus':2,
                     'jobs':[{'job_id':'1','limit_seconds':300}]}

    def test_running_and_pending_work_reserve_their_remaining_hard_limit(self):
        observations={'1':{'state':'RUNNING','elapsed_seconds':20}}
        self.assertEqual(admission(self.ledger,observations,300)['reserved_gpu_seconds'],280)
        self.ledger['jobs'].append({'job_id':'2','limit_seconds':300})
        observations['2']={'state':'PENDING','elapsed_seconds':0}
        with self.assertRaisesRegex(ValueError,'Concurrent'):
            admission(self.ledger,observations,300)

    def test_failed_work_consumes_budget_and_missing_accounting_cannot_admit(self):
        observations={'1':{'state':'FAILED','elapsed_seconds':5300}}
        with self.assertRaisesRegex(ValueError,'budget'):
            admission(self.ledger,observations,300)
        with self.assertRaisesRegex(ValueError,'cover'):
            admission(self.ledger,{},300)

    def test_ambiguous_submission_intent_blocks_another_submission(self):
        self.ledger['unresolved_submission']={'task':'x'}
        with self.assertRaisesRegex(ValueError,'Unresolved'):
            admission(self.ledger,{'1':{'state':'COMPLETED','elapsed_seconds':100}},300)

    def test_node_configuration_extension_cannot_disappear_from_reservation(self):
        self.ledger['gpu_seconds_cap']=800
        observations={'1':{'state':'RUNNING','elapsed_seconds':350,'remaining_seconds':200}}
        with self.assertRaisesRegex(ValueError,'budget'):
            admission(self.ledger,observations,300)
        observations['1']['remaining_seconds']=100
        self.assertEqual(admission(self.ledger,observations,300)['reserved_gpu_seconds'],100)
        observations['1']['remaining_seconds']=-1
        with self.assertRaisesRegex(ValueError,'remaining'):
            admission(self.ledger,observations,300)
