# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

import io
import logging
import requests
import time

from django.test import TestCase
from django.conf import settings
from django.test.utils import override_settings

from salesforce import auth
from salesforce.backend.test_helpers import default_is_sf, skipUnless, sf_alias
from salesforce.dbapi.exceptions import AuthenticationError
from salesforce.tests.test_dbapi import MockRequestsSession, MockTestCase, MockRequest

try:
    from unittest import mock
except ImportError:
    try:
        import mock
    except ImportError:
        mock = None

log = logging.getLogger(__name__)


@skipUnless(default_is_sf, "Default database should be any Salesforce.")
class OAuthTest(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def validate_oauth(self, d):
        # 'signature' key is not in some auth backends
        for key in ('access_token', 'id', 'instance_url', 'issued_at'):
            if(key not in d):
                self.fail("Missing %s key in returned oauth data." % key)
            elif(not d[key]):
                self.fail("Empty value for %s key in returned oauth data." % key)

    def test_token_renewal(self):
        # import salesforce
        # _session=salesforce.backend.fake.base.FakeAuthSession()
        # _session.bind('default')
        _session = requests.Session()

        auth_obj = auth.SalesforceAuth.create_subclass_instance(sf_alias,
                                                                settings_dict=settings.DATABASES[sf_alias],
                                                                _session=_session)
        auth_obj.get_auth()
        self.validate_oauth(auth.oauth_data[sf_alias])
        old_data = auth.oauth_data

        self.assertIn(sf_alias, auth.oauth_data)
        auth_obj.del_token()
        self.assertNotIn(sf_alias, auth.oauth_data)

        auth_obj.get_auth()
        self.validate_oauth(auth.oauth_data[sf_alias])

        self.assertEqual(old_data[sf_alias]['access_token'], auth.oauth_data[sf_alias]['access_token'])

    @mock.patch('salesforce.auth.open', create=True)
    def test_force_com_cli_auth(self, mock_open):
        """Test Force.com CLI authentication by a mocked file"""
        auth_obj = auth.SalesforceAuth.create_subclass_instance(
            sf_alias,
            settings_dict={'ENGINE': 'salesforce.backend', 'AUTH': 'salesforce.auth.ForceComCliAuth',
                           'USER': 'me@example.com'},
            _session=requests.Session())
        mock_open.return_value = io.StringIO(
            u'{"AccessToken":"00A12000000a1Bc!...",'   # anonymized all
            u'"Id":"https://login.salesforce.com/id/00A12000000a1BcEAI/00512000001AxneAAC",'
            u'"UserId":"00512000001AxneAAC","InstanceUrl":"https://na3.salesforce.com",'
            u'"IssuedAt":"1473245937490","Scope":"full","IsCustomEP":false,"Namespace":"",'
            u'"ApiVersion":"","ForceEndpoint":0}')
        self.assertEqual(auth_obj.authenticate()['instance_url'], 'https://na3.salesforce.com')


class InvalidPasswordTest(MockTestCase):
    def setUp(self):
        super(InvalidPasswordTest, self).setUp()

    @skipUnless(mock, "mock pakage is required for this test")
    @override_settings(SF_MOCK_MODE='playback')
    def test_invalid_password_no_lock(self):
        """Verify SF is protected from flood of invalid logins"""
        #
        old_session = requests.Session()
        # the Mock(instance_url=...) was important for response recording
        old_session.auth = mock.Mock(instance_url='https://test.salesforce.com')
        # simulate 3 failed login requests
        mock_session = MockRequestsSession(self, old_session=old_session)
        settings_dict = {'ENGINE': 'salesforce.backend', 'HOST': 'mock://',
                         'CONSUMER_KEY': '...', 'CONSUMER_SECRET': '...',
                         'USER': 'me@example.com.sandbox', 'PASSWORD': 'bad password'}
        mock_session.add_expected(3 * [MockRequest(
            'POST', 'mock:///services/oauth2/token',
            response_text='{"error":"invalid_client_id","error_description":"client identifier invalid"}',
            request_type='*', response_type='', status_code=400,)])
        auth_obj = auth.SalesforceAuth.create_subclass_instance(
            sf_alias, settings_dict=settings_dict, _session=mock_session)

        # import pdb
        # pdb.set_trace()
        # auth_obj.authenticate()
        # invalid auth
        self.assertRaisesRegexp(AuthenticationError, '^OAuth failed', auth_obj.authenticate)
        # the same is rejected without retry
        self.assertRaisesRegexp(AuthenticationError, '^The same .* data .* failed in .* previous',
                                auth_obj.authenticate)
        # the retry is possible after a few minutes
        with mock.patch('salesforce.auth.time.time', return_value=time.time() + 10 * 60):
            self.assertRaisesRegexp(AuthenticationError, '^OAuth failed', auth_obj.authenticate)
        # a new password can be retried immediately
        auth_obj.settings_dict['PASSWORD'] = 'other bad password'
        self.assertRaisesRegexp(AuthenticationError, '^OAuth failed', auth_obj.authenticate)
        # verify that 3 reponses has been used
        self.assertEqual(mock_session.index, len(mock_session.expected), "Not all expected requests has been used")
