"""Mock requests for Salesforce (REST/SOAP API to database)

Principial differences to other packages: (therefore not used "requests-mock" etc.)
- The same query should have different results before and after insert, update, delete
- This module has several modes:
  "record" mode useful for re-writing small integration tests to create mock tests
  "playback" mode useful for running the tests fast
  "mixed" mode is used like a silent "record" mode that is prepared to be
      switched to "record" mode inside the same session, e.g if a test test is
      extended by additional requests

Parameters
    request_type: (None, 'application/json',... '*') The type '*' is for
        requests where the type and data should not be checked.
    data:  The recommended types are (str, None) A "dict" is possible, but
        it is not explicit enough for some data types.
    json:  it is unused and will be probably deprecated.
           It can be replaced by "json.dumps(request_json)"
"""
import json
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.test.testcases import TestCase
from salesforce.auth import MockAuth
from salesforce.backend.test_helpers import sf_alias

APPLICATION_JSON = 'application/json;charset=UTF-8'


# the first part are not test cases, but helpers for a mocked network: MockTestCase, MockRequest


class MockRequestsSession(object):
    """Prepare mock session with expected requests + responses history

    expected:   iterable of MockJsonRequest
    testcase:  testcase object (for consistent assertion)
    """

    def __init__(self, testcase, expected=(), auth=None, old_session=None):
        self.index = 0
        self.testcase = testcase
        self.expected = list(expected)
        self.auth = auth or MockAuth('dummy alias', {'USER': ''}, _session='dummy login session')
        self.old_session = old_session

    def add_expected(self, expected_requests):
        if isinstance(expected_requests, (list, tuple)):
            self.expected.extend(expected_requests)
        else:
            self.expected.append(expected_requests)

    def request(self, method, url, data=None, **kwargs):
        """Assert the request equals the expected, return historical response"""
        mode = getattr(settings, 'SF_MOCK_MODE', 'playback')
        if mode == 'playback':
            response = self.expected[self.index].request(method, url, data=data, testcase=self.testcase, **kwargs)
            self.index += 1
            return response
        elif mode in ('record', 'mixed'):
            if not self.old_session:
                raise ImproperlyConfigured(
                    'If set SF_MOCK_MODE="record" then the global value or value '
                    'in setUp method must be "mixed" or "record".')
            new_url = url.replace('mock://', self.old_session.auth.instance_url)
            response = self.old_session.request(method, new_url, data=data, **kwargs)
            if mode == 'record':
                print()
                output = []
                output.append("%r, %r" % (method, url))
                if data:
                    output.append("request_data=%r" % data)
                if response.text:
                    output.append("response_data=%r" % response.text)
                request_type = kwargs.get('headers', {}).get('Content-Type', '')
                if request_type != 'application/json' and data:
                    output.append("request_type=%r" % request_type)
                response_type = response.headers.get('Content-Type', '')
                if response_type != APPLICATION_JSON and response.text:
                    output.append("response_type=%r" % response_type)
                if response.status_code != 200:
                    output.append("status_code=%d" % response.status_code)
                print("=== MOCK RECORD {testcase}\nMockJsonRequest(\n    {params})\n===".format(
                      testcase=self.testcase,
                      params=',\n    '.join(output)
                      ))
            return response
        else:
            raise NotImplementedError("Not implemented SF_MOCK_MODE=%s" % mode)

    def get(self, url, **kwargs):
        return self.request('GET', url, **kwargs)

    def post(self, url, data=None, json=None, **kwargs):
        return self.request('POST', url, data=data, json=json, **kwargs)

    def patch(self, url, data=None, **kwargs):
        return self.request('PATCH', url, data=data, **kwargs)

    def delete(self, url, **kwargs):
        return self.request('DELETE', url, **kwargs)

    def mount(self, prefix, adapter):
        pass


class MockRequest(object):
    """Mock request/response for some unit tests offline

    If the parameter 'request_type' is '*' then the request is not tested
    """
    def __init__(self, method, url,
                 request_data=None, response_data=None,
                 request_json=None,
                 request_type='application/json', response_type=APPLICATION_JSON,
                 status_code=200):
        self.method = method
        self.url = url
        self.request_data = request_data
        self.response_data = response_data
        self.request_json = request_json
        self.request_type = request_type if (request_data or request_type == '*') else None
        self.response_type = response_type if response_data else None
        self.status_code = status_code

    def request(self, method, url, data=None, testcase=None, **kwargs):
        if testcase is None:
            raise TypeError("Required keyword argument 'testcase' not found")
        testcase.assertEqual(method.upper(), self.method.upper())
        testcase.assertEqual(url, self.url)
        if 'json' in (self.request_type or ''):
            testcase.assertJSONEqual(data, self.request_data)
        elif 'xml' in (self.request_type or ''):
            testcase.assertXMLEqual(data, self.request_data)
        elif self.request_type != '*':
            testcase.assertEqual(data, self.request_data)
        if self.request_type != '*':
            request_json = kwargs.pop('json', None)
            testcase.assertEqual(request_json, self.request_json)
        kwargs.pop('timeout', None)
        assert kwargs.pop('verify', True) is True
        if 'json'in kwargs and kwargs['json'] is None:
            del kwargs['json']
        if kwargs:
            print("KWARGS = %s" % kwargs)  # TODO
        return MockJsonResponse(self.response_data, status_code=self.status_code, resp_content_type=self.response_type)


class MockJsonRequest(MockRequest):
    """Mock JSON request/response for some unit tests offline"""
    pass  # parent defaults are ok


class MockTestCase(TestCase):
    """
    Test case that uses recorded requests/responses instead of network
    """
    def setUp(self):
        mode = getattr(settings, 'SF_MOCK_MODE', 'playback')
        super(MockTestCase, self).setUp()
        self.sf_connection = connection = connections[sf_alias]
        if mode != 'playback' and not connection._sf_session:
            # if the mode is 'record' or 'mixed' we must create a real
            # connection before mock
            connection.make_session()
        self.save_session_auth = connection._sf_session, connection._sf_auth
        connection._sf_session = MockRequestsSession(testcase=self, old_session=connection._sf_session)
        connection._sf_auth = connection._sf_session.auth

    def tearDown(self):
        connection = self.sf_connection
        session = connection._sf_session
        self.assertEqual(session.index, len(session.expected), "Not all expected requests has been used")
        connection._sf_session, connection._sf_auth = self.save_session_auth
        super(MockTestCase, self).setUp()

    def mock_add_expected(self, expected_requests):
        self.sf_connection._sf_session.add_expected(expected_requests)


# class MockXmlRequest - only with different default content types


class MockResponse(object):
    """Mock response for some unit tests offline"""
    def __init__(self, text, resp_content_type=APPLICATION_JSON, status_code=200):
        self.text = text
        self.status_code = status_code
        self.content_type = resp_content_type

    def json(self, parse_float=None):
        return json.loads(self.text, parse_float=parse_float)

MockJsonResponse = MockResponse
