"""Mock requests for Salesforce (REST/SOAP API to database)

Principial differences to other packages: (therefore not used "requests-mock" etc.)
- The same query should have different results before and after insert, update, delete
- This module has several modes:
  "record" mode useful for re-writing small integration tests to create mock tests
  "playback" mode useful for running the tests fast
  "mixed" mode is used like a silent "record" mode that is prepared to be
      switched to "record" mode inside the same session, e.g if a test test is
      extended by additional requests

    properties of modes:
        2 sources or requests: application / recorded
        2 sources or responses: Force.com server / recorded

        need authentize before session?: (bool)
        record raw data or anonimize all ID
        record the traffic or to check and terminate at the first difference or
            to translate the historyrepla?
        cleanup after error or wait?
        a difference should be reported, but it an exception should not be raised before tearDown?
        * from application to server: * like a normal test
                                      * record all
                                      * check
                                      * check and record after difference
        * from playback to server: (check that the Force.com API is not changed)
        * nothing to server: response from playback: * only report differences
                                                     * stop a different request
                                                     * switch to server (replay and translate history)
        compare recorded requests
        compare test data

        Use raw recorded traffic or to try to find a nice formated equivalent record?
Parameters
    request_type: (None, 'application/json',... '*') The type '*' is for
        requests where the type and data should not be checked.
    data:  The recommended types are (str, None) A "dict" is possible, but
        it is not explicit enough for some data types.
    json:  it is unused and will be probably deprecated.
           It can be replaced by "json.dumps(request_json)"
"""
import json
import re
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
            expected = self.expected[self.index]
            msg = "Difference at request index %d (from %d)" % (self.index, len(self.expected))
            response = expected.request(method, url, data=data, testcase=self.testcase,
                                        msg=msg, **kwargs)
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
                    output.append("req=%r" % data)
                if response.text:
                    output.append("resp=%r" % response.text)

                request_type = kwargs.get('headers', {}).get('Content-Type', '')
                response_type = response.headers.get('Content-Type', '')
                basic_type = request_type or response_type
                if basic_type.startswith('application/json'):
                    request_class = MockJsonRequest
                else:
                    request_class = MockRequest
                    output.append("request_type=%r" % request_type)

                if response_type and (response_type != basic_type or request_class is MockRequest):
                    output.append("response_type=%r" % response_type)
                if response.status_code != 200:
                    output.append("status_code=%d" % response.status_code)
                print("=== MOCK RECORD {testcase}\n{class_name}(\n    {params})\n===".format(
                      class_name=request_class.__name__,
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
    """Recorded Mock request to be compared and response to be used

    for some unit tests offline
    If the parameter 'request_type' is '*' then the request is not tested
    """
    default_type = None

    def __init__(self, method, url,
                 req=None, resp=None,
                 request_json=None,
                 request_type=None, response_type=None,
                 status_code=200):
        self.method = method
        self.url = url
        self.request_data = req
        self.response_data = resp
        self.request_json = request_json
        self.request_type = request_type or (self.default_type if method not in ('GET', 'DELETE') else '') or ''
        self.response_type = response_type
        self.status_code = status_code

    def request(self, method, url, data=None, testcase=None, **kwargs):
        """Compare the request to the expected. Return the expected response."""
        if testcase is None:
            raise TypeError("Required keyword argument 'testcase' not found")
        msg = kwargs.pop('msg', None)
        testcase.assertEqual(method.upper(), self.method.upper())
        testcase.assertEqual(url, self.url, msg=msg)
        if self.response_data:
            response_class = MockJsonResponse if self.default_type == APPLICATION_JSON else MockResponse
        else:
            response_class = MockResponse
        if data or json:
            request_type = kwargs.get('headers', {}).pop('Content-Type', '')
        response = response_class(self.response_data,
                                  status_code=self.status_code,
                                  resp_content_type=self.response_type)
        if 'json' in self.request_type:
            testcase.assertJSONEqual(data, self.request_data, msg=msg)
        elif 'xml' in self.request_type:
            testcase.assertXMLEqual(data, self.request_data, msg=msg)
        elif self.request_type != '*':
            testcase.assertEqual(data, self.request_data, msg=msg)
        if self.request_type != '*':
            request_json = kwargs.pop('json', None)
            testcase.assertEqual(request_json, self.request_json, msg=msg)
        if self.request_type != '*':
            testcase.assertEqual(request_type.split(';')[0], self.request_type.split(';')[0], msg=msg)
        kwargs.pop('timeout', None)
        assert kwargs.pop('verify', True) is True
        if 'json'in kwargs and kwargs['json'] is None:
            del kwargs['json']
        if 'headers' in kwargs and not kwargs['headers']:
            del kwargs['headers']
        if kwargs:
            print("KWARGS = %s (msg=%s)" % (kwargs, msg), url)  # TODO
        return response


class MockJsonRequest(MockRequest):
    """Mock JSON request/response for some unit tests offline"""
    default_type = APPLICATION_JSON


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
        if not self._outcome.errors or self._outcome.errors[-1][0] is not self or not self._outcome.errors[-1][1]:
            self.assertEqual(session.index, len(session.expected), "Not all expected requests has been used")
        connection._sf_session, connection._sf_auth = self.save_session_auth
        super(MockTestCase, self).tearDown()

    def mock_add_expected(self, expected_requests):
        self.sf_connection._sf_session.add_expected(expected_requests)


# class MockXmlRequest - only with different default content types


class MockResponse(object):
    """Mock response for some unit tests offline"""
    default_type = None

    def __init__(self, text, resp_content_type=None, status_code=200):
        self.text = text
        self.status_code = status_code
        self.content_type = resp_content_type if resp_content_type is not None else self.default_type

    def json(self, parse_float=None):
        return json.loads(self.text, parse_float=parse_float)

    @property
    def headers(self):
        return {'Content-Type': self.content_type} if self.content_type else {}


class MockJsonResponse(MockResponse):
    default_type = APPLICATION_JSON


# Undocumented - useful for tests


def case_safe_sf_id(id_15):
    """
    Equivalent to Salesforce CASESAFEID()

    Convert a 15 char case-sensitive Id to 18 char case-insensitive Salesforce Id
    or check the long 18 char ID.

    Long  18 char Id are from SFDC API and from Apex. They are recommended by SF.
    Short 15 char Id are from SFDC formulas if omitted to use func CASESAFEID(),
    from reports or from parsed URLs in HTML.
    The long and short form are interchangable as the input to Salesforce API or
    to django-salesforce. They only need to be someway normalized if they are
    used as dictionary keys in a Python application code.
    """
    if not id_15:
        return None
    if len(id_15) not in (15, 18):
        raise TypeError("The string %r is not a valid Force.com ID")
    suffix = []
    for i in range(0, 15, 5):
        weight = 1
        digit = 0
        for ch in id_15[i:i + 5]:
            if ch not in '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz':
                raise TypeError("The string %r is not a valid Force.com ID")
            if ch.isupper():
                digit += weight
            weight *= 2
        suffix.append(chr(ord('A') + digit) if digit < 26 else str(digit - 26))
    out = ''.join(suffix)
    if len(id_15) == 18 and out != id_15[15:]:
        raise TypeError("The string %r is not a valid Force.com ID")
    return id_15[:15] + out


def check_sf_api_id(id_18):
    """
    Check the 18 characters long API ID, no exceptions
    """
    try:
        return case_safe_sf_id(id_18)
    except TypeError:
        return None


def extract_ids(data_text, data_type=None):
    """
    Extract all Force.com ID from REST/SOAP/SOQL request/response (for mock tests)

    Output: iterable of all ID and their positions
    Parameters: data_type:  can be in ('rest', 'soap', 'soql', None),
                    where None is for any unknown type
    """
    id_pattern = r'([0-9A-Za-z]{18})'
    PATTERN_MAP = {None: r'[">\']{}["<\']',
                   'rest': '"{}"',
                   'soap': '>{}<',
                   'soql': "'{}'"
                   }
    pattern = PATTERN_MAP[data_type].format(id_pattern)
    for match in re.finditer(pattern, data_text):
        txt = match.group(1)
        if case_safe_sf_id(txt):
            yield txt, (match.start(1), match.end(1))
