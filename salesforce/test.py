"""
Support for "live" tests with SFDC database

The Tests than can write into a production SF database, called "live" tests.
The recommended way is to modify only objects created by the test.
"""
from functools import wraps
from django.conf import settings
from django.db import connections
from django.test.utils import override_settings

# SkipTest is an exception if no method or decorator can be used
from unittest import SkipTest  # NOQA

sf_alias = getattr(settings, 'SALESFORCE_DB_ALIAS', 'salesforce')


def sf_is_production(alias=None):
    """Check that the database is a SF production (not sandbox or alternative)"""
    # If a test runs on a non SF, e.g. on sqlite3, then it is also safe
    return getattr(connections[alias or sf_alias], 'sf_is_production', False)

# -- decorators - can be applied to method or class


def live_deny_if_write(callable=None):
    """Deny live test (decorator or context manager)"""
    ret = override_settings(SF_LIVE_TEST_POLICY='deny_if_write')
    return ret(callable) if callable else ret


def live_skip_if_write(callable=None):
    """Skip live test (decorator or context manager)"""
    ret = override_settings(SF_LIVE_TEST_POLICY='skip_if_write')
    return ret(callable) if callable else ret


def live_allow(callable=None):
    """Allow live test (decorator or context manager)"""
    ret = override_settings(SF_LIVE_TEST_POLICY='allow')
    return ret(callable) if callable else ret


def live_skip(callable):
    """Skip the test or the entire TestCase on "live" databases"""
    @wraps(callable)
    def wrapper(*args, **kwargs):
        if not sf_is_production():
            return callable(*args, **kwargs)
        else:
            raise SkipTest("Skipped test because the default SF database is a production one")
    return wrapper
