from django.test import TestCase
from django.conf import settings
from django.db import connections
from salesforce.testrunner.example.models import User
from requests.exceptions import ConnectionError

# The test for `expectedFailure` decorator is put here, because it is not
# nice to see '(expected failures=1)' in the main results
from salesforce.backend.test_helpers import expectedFailureIf


class LazyTest(TestCase):
    def test_lazy_connection(self):
        """
        Verify that the plain access to SF connection object does not raise
        exceptions with SF_LAZY_CONNECT if SF is not accessible.
        """
        # verify that access to a broken connection does not raise exception
        sf_conn = connections['salesforce']
        # try to authenticate on a temporary broken host
        users = User.objects.all()
        with self.assertRaises(Exception) as cm:
            len(users[:5])
        exc = cm.exception
        self.assertIsInstance(exc, (ConnectionError, LookupError))
        # fix the host name and verify that the connection works now
        sf_conn.settings_dict.update(settings.ORIG_SALESFORCE_DB)
        self.assertGreater(len(users[:5]), 0)


class TestExpectedFailure(TestCase):
    @expectedFailureIf(False)
    def test_condition_false(self):
        assert True

    @expectedFailureIf(True)
    def test_condition_true(self):
        assert False
