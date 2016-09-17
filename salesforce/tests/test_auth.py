# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

import logging
import requests

from django.test import TestCase
from django.conf import settings

from salesforce import auth
from salesforce.backend.test_helpers import default_is_sf, skipUnless, sf_alias

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
