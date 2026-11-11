"""Synthetic rules exercise the engine, never assert clinical validation."""
import unittest
import os
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from corecare.clinical_priority import ClinicalRequest, recommend_priority


class ClinicalPriorityTests(unittest.TestCase):
    def protocol(self):
        return dict(name='Synthetic protocol', version='test-1', reference='TEST ONLY approval reference',
                    clinicalValidationReference='TEST ONLY validation fixture', approvedBy='Synthetic reviewer',
                    approvedAt='2026-01-01T00:00:00Z', approvalAttested=True, requiredFields=['urgency'],
                    rules=[dict(id='synthetic-critical', priority='CRITICAL', explanation='Synthetic structured risk match.',
                                conditions=[dict(field='riskIndicators', operator='contains', value='TEST_RISK')]),
                           dict(id='synthetic-low', priority='LOW', explanation='Synthetic routine match.',
                                conditions=[dict(field='urgency', operator='equals', value='Routine')])])

    def request(self, **changes):
        return ClinicalRequest(**dict(dict(urgency='Routine', requiredService='TEST SERVICE', protocol=self.protocol()), **changes))

    def test_no_protocol_no_default(self):
        result=recommend_priority(self.request(protocol=None))
        self.assertIsNone(result['priority']);self.assertTrue(result['requires_review'])

    def test_missing_information_never_low_even_when_low_rule_matches(self):
        result=recommend_priority(self.request())
        self.assertIsNone(result['priority']);self.assertIn('riskIndicators',result['missing_fields'])

    def test_highest_matching_rule_and_explanations(self):
        result=recommend_priority(self.request(observations={'riskIndicators':['TEST_RISK']}))
        self.assertEqual(result['priority'],'CRITICAL');self.assertTrue(result['requires_review'])
        self.assertEqual(result['matched_rules'],['synthetic-critical','synthetic-low'])
        self.assertEqual(result['factors'][0]['field'],'riskIndicators')

    def test_no_match_requires_review(self):
        result=recommend_priority(self.request(urgency='Urgent',observations={'riskIndicators':['OTHER_SYNTHETIC_FLAG']}))
        self.assertIsNone(result['priority']);self.assertIn('No approved rule matched',result['explanation'])

    def test_vital_units_and_missing_evidence_fail_closed(self):
        protocol=self.protocol();protocol['rules'][0]['conditions']=[dict(field='vitals.synthetic',operator='gte',value=7,unit='TEST_UNIT')]
        for observations in [{},{'vitals':{'synthetic':{'value':8,'unit':'WRONG_UNIT'}}}]:
            self.assertIsNone(recommend_priority(self.request(protocol=protocol,observations=observations))['priority'])
        self.assertEqual(recommend_priority(self.request(protocol=protocol,observations={'vitals':{'synthetic':{'value':8,'unit':'TEST_UNIT'}}}))['priority'],'CRITICAL')

    def test_bridge_auth_and_rejection_of_operational_features(self):
        with patch.dict(os.environ,{'CORECARE_API_KEY':'clinical-test-key'}):
            client=TestClient(app)  # No storage/model lifecycle is needed for this stateless route.
            payload={'urgency':'Routine','requiredService':'Test'}
            self.assertEqual(client.post('/integration/clinical-priority',json=payload).status_code,401)
            headers={'X-API-Key':'clinical-test-key'}
            result=client.post('/integration/clinical-priority',json=payload,headers=headers)
            self.assertEqual(result.status_code,200);self.assertIsNone(result.json()['data']['priority'])
            for field in ['hospital_workload','delay_probability','patient_name']:
                self.assertEqual(client.post('/integration/clinical-priority',json={**payload,field:'not permitted'},headers=headers).status_code,422)
            protocol=self.protocol();protocol.pop('clinicalValidationReference')
            self.assertEqual(client.post('/integration/clinical-priority',json={**payload,'protocol':protocol},headers=headers).status_code,422)
            client.close()


if __name__=='__main__':
    unittest.main()
