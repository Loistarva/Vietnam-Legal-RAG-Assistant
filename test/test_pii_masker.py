import copy
import json
import unittest
from monitoring.pii_masker import mask,mask_external_payload


class MaskerTests(unittest.TestCase):
    def test_synthetic_patterns(self):
        values=['sample.person@example.test','0912345678','+84 912 345 678','012345678901','123456789']
        for value in values:
            with self.subTest(value=value):self.assertNotIn(value,mask(value))

    def test_nested_secrets_and_no_mutation(self):
        value={'text':'Email sample@example.test; Bearer fake-bearer; sk-synthetic-fixture',
               'headers':{'Authorization':'private'},'OPENAI_API_KEY':'private-key',
               'nested':[{'refresh_token':'private-refresh','environment':{'X':'private-env'},
                          'text':'custom-fixture-secret'}],'phone':123456789,'id':123456789012}
        original=copy.deepcopy(value)
        result=json.dumps(mask(value,secrets=('custom-fixture-secret',)))
        for private in ['sample@example.test','fake-bearer','sk-synthetic-fixture','private',
                        'custom-fixture-secret','123456789']:
            self.assertNotIn(private,result)
        self.assertEqual(value,original)

    def test_non_pii_legal_identifiers_preserved(self):
        text='Luật 52/2014/QH13, Điều 8, ngày 2026-11-12'
        self.assertEqual(mask(text),text)

    def test_external_hook_returns_new_payload(self):
        payload={'messages':[{'role':'user','content':'sample@example.test'}]}
        masked=mask_external_payload(payload)
        self.assertEqual(masked['messages'][0]['content'],'[EMAIL]')
        self.assertEqual(payload['messages'][0]['content'],'sample@example.test')
