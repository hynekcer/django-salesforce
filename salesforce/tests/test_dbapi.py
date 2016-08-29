import json
from django.test.testcases import TestCase
from django.utils.six import text_type
from salesforce.dbapi import driver


class MockJsonResponse(object):
    """Mock response for some unit tests offline"""
    def __init__(self, text, status_code=200, resp_content_type='application/json'):
        self.text = text
        self.status_code = status_code
        self.content_type = resp_content_type

    def json(self, parse_float=None):
        return json.loads(self.text, parse_float=parse_float)


class FieldMapTest(TestCase):
    def test_field_map(self):
        self.assertEqual(str(driver.field_map['Account', 'Name']), 'example.Account.Name')
        self.assertEqual(repr(driver.field_map['Account', 'Name']), '<salesforce.fields.CharField: Name>')
        self.assertEqual(repr(type(driver.field_map['Account', 'Name'])), "<class 'salesforce.fields.CharField'>")

    def test_field_map_is_case_insensitive(self):
        self.assertEqual(driver.field_map['aCCOUNT', 'nAME'].column, 'Name')

    def test_field_map_description(self):
        self.assertEqual(driver.field_map.description(('Contact', 'FirstName')).name, 'FirstName')
        self.assertEqual(driver.field_map.description(('Contact', 'FirstName')).type_code, text_type)
        self.assertEqual(driver.field_map.description(('Contact', 'FirstName')).internal_size, 40)
