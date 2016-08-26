"""Test for sandbox and restricted writable "live" tests on production db"""
from unittest import SkipTest
from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.test import TestCase
from salesforce.backend.test_helpers import sf_alias
from salesforce.test import live_deny_if_write, live_skip_if_write, live_allow, live_skip
from salesforce.testrunner.example.models import Contact


class BaseSanboxTest(TestCase):
    """Base class with methods for tests - no test here"""
    @classmethod
    def setUpClass(cls):
        super(BaseSanboxTest, cls).setUpClass()
        cls.contact = Contact.objects.all()[0]

    def assertCanWrite(self):
        con = connections[sf_alias]
        save_is_sandbox = con._sf_auth._is_sandbox
        con._sf_auth._is_sandbox = False
        try:
            self.contact.save()
        finally:
            con._sf_auth._is_sandbox = save_is_sandbox

    def assertWriteRaises(self, exc):
        con = connections[sf_alias]
        save_is_sandbox = con._sf_auth._is_sandbox
        con._sf_auth._is_sandbox = False
        try:
            # this can catch ImproperlyConfigured exception, while assertRaises can not
            try:
                self.contact.save()
            except exc:
                pass
            else:
                self.fail("Exception %r has not been raised as expected" % exc)
        finally:
            con._sf_auth._is_sandbox = save_is_sandbox

    def assertWriteSkipped(self):
        con = connections[sf_alias]
        save_is_sandbox = con._sf_auth._is_sandbox
        con._sf_auth._is_sandbox = False
        try:
            try:
                self.contact.save()
            except SkipTest:
                pass
            else:
                self.fail("The test has not been skipped as expected")
        finally:
            con._sf_auth._is_sandbox = save_is_sandbox

# -- tests start here


class NonSandboxTest(BaseSanboxTest):
    def test_can_not_write_in_test(self):
        self.assertWriteRaises(ImproperlyConfigured)

    @live_allow
    def test_can_write_in_test_live_allow(self):
        self.assertCanWrite()

    @live_skip_if_write
    def test_skip_in_test_live_skip(self):
        self.assertWriteSkipped()

    def test_combined_context_manager(self):
        """
        Verify that the permissions can be changed in a part of code
        """
        self.assertWriteRaises(ImproperlyConfigured)
        with live_allow():
            self.assertCanWrite()
        self.assertWriteRaises(ImproperlyConfigured)

    def test_can_write_if_outside_test(self):
        con = connections[sf_alias]
        con.is_in_test = False
        try:
            self.assertCanWrite()
        finally:
            con.is_in_test = True


@live_allow
class NonSandboxAllowTest(BaseSanboxTest):
    """Test nested decorators, if the top rule is "allow"."""
    def setUp(self):
        self.assertCanWrite()

    def test_can_write_in_test(self):
        self.assertCanWrite()

    @live_deny_if_write
    def test_can_not_write_in_test_override_deny(self):
        self.assertWriteRaises(ImproperlyConfigured)


@live_skip
class NonSandboxSkipTest(BaseSanboxTest):
    @live_allow
    def test_skip_cant_be_overriden(self):
        self.assertWriteSkipped()


@live_deny_if_write
class NonSandboxDenyTest(BaseSanboxTest):
    @live_allow
    def setUp(self):
        self.assertCanWrite()

    def tearDown(self):
        self.assertWriteRaises(ImproperlyConfigured)

    def test_that_setup_passed_and_teardown_failed(self):
        pass  # tested in the setUp
