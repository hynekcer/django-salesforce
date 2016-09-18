from django.test.testcases import TestCase
from salesforce.dbapi.mocksf import case_safe_sf_id, check_sf_api_id


class Id15To18Test(TestCase):
    def check_id(self, id_15, suffix_3):
        self.assertEqual(check_sf_api_id(id_15)[-3:], suffix_3)

    def test_id15_to_18(self):
        self.assertEqual(case_safe_sf_id('00A000000000000'), '00A000000000000EAA')
        self.assertEqual(case_safe_sf_id('00A000000000000EAA'), '00A000000000000EAA')
        self.assertEqual(case_safe_sf_id(None), None)

        self.check_id('000000000000000', 'AAA')
        self.check_id('00000000000000A', 'AAQ')
        self.check_id('0000A0000A0000A', 'QQQ')
        self.check_id('000A0000A0000A0', 'III')
        self.check_id('00A0000A0000A00', 'EEE')
        self.check_id('0A0000A0000A000', 'CCC')
        self.check_id('A0000A0000A0000', 'BBB')
        self.check_id('aAaAAaAaAAaAaAA', '000')
        self.check_id('AAAAAAAAAAAAAAA', '555')
        self.check_id('aaaaaaaaaaaaaaa', 'AAA')
        self.check_id('aaaaaaaaaaaaaaaAAA', 'AAA')

        self.assertRaises(TypeError, case_safe_sf_id, '00A000000000000AAA')
