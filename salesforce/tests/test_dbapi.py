from django.db import connections
from django.test.utils import override_settings
from django.test.testcases import TestCase
from django.utils.six import text_type
from salesforce.dbapi import driver
from salesforce.backend.test_helpers import sf_alias
from salesforce.dbapi.mocksf import MockJsonRequest, MockTestCase


# test cases


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


@override_settings(SF_MOCK_MODE='mixed')
class TestMock(MockTestCase):
    def prepare_expected(self):
        self.mock_add_expected(MockJsonRequest(
            'GET', 'mock:///services/data/v37.0/query/?q=SELECT+Name+FROM+Contact+LIMIT+1',
            response_data=(
                '{"totalSize": 1, "done": true, "records": [{'
                '  "attributes": {"type": "Contact",'
                '                 "url": "/services/data/v37.0/sobjects/Contact/003A000000wJICkIAO"},'
                '  "Name": "django-salesforce test"}]}')))

    @override_settings(SF_MOCK_MODE='playback')
    def test_mock_playback(self):
        self.prepare_expected()
        # test
        cur = connections[sf_alias].cursor()
        cur.execute("SELECT Name FROM Contact LIMIT 1")
        self.assertEqual(list(cur.fetchall()), [['django-salesforce test']])

    def test_mock_unused_playback(self):
        self.prepare_expected()
        self.assertRaisesRegexp(AssertionError, "Not all expected requests has been used", self.tearDown)
        connections[sf_alias]._sf_session.index += 1  # mock a consumed request

    @override_settings(SF_MOCK_MODE='record')
    def test_mock_record(self):
        # test
        cur = connections[sf_alias].cursor()
        cur.execute("SELECT Name FROM Contact LIMIT 1")
        row, =  cur.fetchall()
        self.assertEqual(len(row), 1)
        self.assertIsInstance(row[0], text_type)
