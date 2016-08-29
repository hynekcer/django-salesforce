import json
from django.db import connections
from django.test.testcases import TestCase
from django.utils.six import text_type
from salesforce.auth import MockAuth
from salesforce.backend.test_helpers import sf_alias
from salesforce.dbapi import driver


class MockRequestsSession(object):
    """Prepare mock session with expected requests + responses history

    data:  iterable of MockJsonRequest
    testcase:  testcase for assertion
    """

    def __init__(self, history, testcase, auth=None):
        self.index = 0
        self.history = history
        self.testcase = testcase
        self.auth = MockAuth('dummy alias', {'USER': ''}, _session='dummy login session')

    def request(self, method, url, data=None, **kwargs):
        response = self.history[self.index].request(method, url, data=data, testcase=self.testcase, **kwargs)
        self.index += 1
        return response

    def get(self, url, **kwargs):
        return self.request('GET', url, **kwargs)

    def post(self, url, data=None, json=None, **kwargs):
        return self.request('POST', url, data=data, json=json, **kwargs)

    def patch(self, url, data=None, **kwargs):
        return self.request('PATCH', url,  data=data, **kwargs)

    def delete(self, url, **kwargs):
        return self.request('DELETE', url, **kwargs)


class MockJsonRequest(object):
    """Mock response for some unit tests offline"""
    def __init__(self, method, url, request_json=None, response_json=None,
                 response_type='application/json', status_code=200
                 ):
        self.method = method
        self.url = url
        self.request_json = request_json
        self.response_json = response_json
        self.response_type = response_type
        self.status_code = status_code

    def request(self, method, url, data=None, testcase=None, **kwargs):
        testcase.assertEqual(method.upper(), self.method.upper())
        testcase.assertEqual(url, self.url)
        if data:
            testcase.assertJSONEqual(data,  self.request_json)
        else:
            testcase.assertEqual(data,  self.request_json)
        kwargs.pop('timeout')
        assert kwargs.pop('verify') is True
        if kwargs:
            print("KWARGS = %s" % kwargs)  # TODO
        return MockJsonResponse(self.response_json, status_code=self.status_code, resp_content_type=self.response_type)


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


class MockTest(TestCase):
    def test_mock(self):
        connection = connections[sf_alias]
        # import pdb; pdb.set_trace()
        save_session = connection._sf_session
        save_auth = connection._sf_auth

        method, url = 'GET', 'mock:///services/data/v37.0/query/?q=SELECT+Name+FROM+Contact+LIMIT+1'
        response_json = ('{"totalSize": 1, "records": [{'
                         '"attributes": {"type": "Contact", "url": "/services/data/v37.0/sobjects/Contact/003A000000wJICkIAO"},'
                         '"Name": "django-salesforce test"}], "done": true}')
        history = [MockJsonRequest(method, url, response_json=response_json)]
        connection._sf_session = MockRequestsSession(history, self)
        connection._sf_auth = connection._sf_session.auth
        try:
            cur = connection.cursor()
            cur.execute("SELECT Name FROM Contact LIMIT 1")
            self.assertEqual(list(cur.fetchall()), [['django-salesforce test']])
        finally:
            connection._sf_session = save_session
            connection._sf_auth = save_auth
