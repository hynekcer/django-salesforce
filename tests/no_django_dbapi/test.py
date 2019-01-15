import unittest
import requests
import salesforce.testrunner.settings

sf_alias = 'salesforce'
settings_dict = salesforce.testrunner.settings.DATABASES[sf_alias]


class Test(unittest.TestCase):

    def test_no_django(self):
        self.assertRaises(ImportError, __import__, 'django.core')

    def test_auth_standard(self):
        import salesforce.auth
        salesforce.auth.SalesforcePasswordAuth(sf_alias, settings_dict=settings_dict)


class OAuthTest(unittest.TestCase):

    def validate_oauth(self, d):
        for key in ('access_token', 'id', 'instance_url', 'issued_at', 'signature'):
            if(key not in d):
                self.fail("Missing %s key in returned oauth data." % key)
            elif(not d[key]):
                self.fail("Empty value for %s key in returned oauth data." % key)

    def test_token_renewal(self):
        from salesforce import auth
        # _session=salesforce.backend.fake.base.FakeAuthSession()
        # _session.bind('default')
        _session = requests.Session()

        auth_obj = auth.SalesforcePasswordAuth(sf_alias, settings_dict=settings_dict,
                                               _session=_session)
        auth_obj.get_auth()
        self.validate_oauth(auth.oauth_data[sf_alias])
        old_data = auth.oauth_data

        self.assertIn(sf_alias, auth.oauth_data)
        auth_obj.del_token()
        self.assertNotIn(sf_alias, auth.oauth_data)

        _session.close()  # close to prevent ResourceWarning: unclosed <ssl.SSLSocket...>
        auth_obj.get_auth()
        self.validate_oauth(auth.oauth_data[sf_alias])

        self.assertEqual(old_data[sf_alias]['access_token'], auth.oauth_data[sf_alias]['access_token'])
        _session.close()
