# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Salesforce database backend for Django.
"""

import logging
import sys
import threading

from django.conf import settings
from requests.adapters import HTTPAdapter

from salesforce.auth import SalesforceAuth
from salesforce.backend.client import DatabaseClient
from salesforce.backend.creation import DatabaseCreation
from salesforce.backend.validation import DatabaseValidation
from salesforce.backend.operations import DatabaseOperations
from salesforce.backend import introspection
from salesforce.dbapi.base import SessionEncap
from salesforce.dbapi.exceptions import IntegrityError, DatabaseError, SalesforceError  # NOQA - TODO
from salesforce.dbapi import driver as Database, get_max_retries
# from django.db.backends.signals import connection_created

from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.backends.base.features import BaseDatabaseFeatures

__all__ = ('DatabaseWrapper', 'DatabaseError', 'SalesforceError',)
log = logging.getLogger(__name__)

connect_lock = threading.Lock()


class DatabaseFeatures(BaseDatabaseFeatures):
    """
    Features this database provides.
    """
    allows_group_by_pk = True
    supports_unspecified_pk = False
    can_return_id_from_insert = False
    has_bulk_insert = True
    # TODO If the following would be True, it requires a good relation name resolution
    supports_select_related = False
    # Though Salesforce doesn't support transactions, the setting
    # `supports_transactions` is used only for switching between rollback or
    # cleaning the database in testrunner after every test and loading fixtures
    # before it, however SF does not support any of these and all test data must
    # be loaded and cleaned by the testcase code. From the viewpoint of SF it is
    # irrelevant, but due to issue #28 (slow unit tests) it should be True.
    supports_transactions = True

    # Never use `interprets_empty_strings_as_nulls=True`. It is an opposite
    # setting for Oracle, while Salesforce saves nulls as empty strings not vice
    # versa.


class DatabaseWrapper(BaseDatabaseWrapper):
    """
    Core class that provides all DB support.
    """
    vendor = 'salesforce'
    # Operators [contains, startswithm, endswith] are incorrectly
    # case insensitive like sqlite3.
    operators = {
        'exact': '= %s',
        'iexact': 'LIKE %s',
        'contains': 'LIKE %s',
        'icontains': 'LIKE %s',
        # 'regex': 'REGEXP %s',  # unsupported
        # 'iregex': 'REGEXP %s',
        'gt': '> %s',
        'gte': '>= %s',
        'lt': '< %s',
        'lte': '<= %s',
        'startswith': 'LIKE %s',
        'endswith': 'LIKE %s',
        'istartswith': 'LIKE %s',
        'iendswith': 'LIKE %s',
    }

    Database = Database

    def __init__(self, settings_dict, alias=None):
        if alias is None:
            alias = getattr(settings, 'SALESFORCE_DB_ALIAS', 'salesforce')
        if not settings_dict['NAME']:
            settings_dict['NAME'] = settings_dict['USER'] or alias
        super(DatabaseWrapper, self).__init__(settings_dict, alias)
        self.features = DatabaseFeatures(self)
        self.ops = DatabaseOperations(self)
        self.client = DatabaseClient(self)
        self.creation = DatabaseCreation(self)
        self.introspection = introspection.DatabaseIntrospection(self)
        self.validation = DatabaseValidation(self)
        self._sf_session = None
        # configurable class Salesforce***Auth - combined with validate_setttings()
        self._sf_auth = SalesforceAuth.create_subclass_instance(db_alias=self.alias,
                                                                settings_dict=self.settings_dict)
        # debug attributes and test attributes
        self.debug_silent = False
        self.last_chunk_len = None  # uppdated by Cursor class
        self.is_in_test = None
        # The SFDC database is connected as late as possible if only tests
        # are running. Some tests don't require a connection.
        # import pdb; pdb.set_trace()
        if not getattr(settings, 'SF_LAZY_CONNECT', 'test' in sys.argv):
            self.make_session()

    def make_session(self):
        """Authenticate and get the name of assigned SFDC data server"""
        with connect_lock:
            if self._sf_session is None:
                sf_session = SessionEncap()
                sf_session.auth = self._sf_auth
                sf_instance_url = sf_session.auth.instance_url  # property: usually get by login request
                sf_requests_adapter = HTTPAdapter(max_retries=get_max_retries())
                sf_session.mount(sf_instance_url, sf_requests_adapter)
                # Additional headers do work, but these 'compression' and 'keep-alive'
                # are use by the requests package by default. So, no difference
                # sf_session.headers.update({'Accept-Encoding': 'gzip, deflate', 'Connection': 'keep-alive'})
                self._sf_session = sf_session

    @property
    def sf_session(self):
        if self._sf_session is None:
            self.make_session()
        return self._sf_session

    def get_connection_params(self):
        settings_dict = self.settings_dict
        params = settings_dict.copy()
        params.update(settings_dict['OPTIONS'])
        return params

    def get_new_connection(self, conn_params):
        # only simulated a connection interface without connecting really
        return Database.connect(**conn_params)

    def init_connection_state(self):
        # import pdb; pdb.set_trace()
        pass  # nothing to init

    def _set_autocommit(self, autocommit):
        # SF REST API uses autocommit, but until rollback it is not a
        # serious problem to ignore autocommit off
        pass

    def cursor(self, query=None):
        """
        Return a fake cursor for accessing the Salesforce API with SOQL.
        """
        from salesforce.dbapi.driver import CursorWrapper
        cursor = CursorWrapper(self, query)
        # cursor = Database.Cursor(self)
        return cursor

    def quote_name(self, name):
        """
        Do not quote column and table names in the SOQL dialect.
        """
        return name

    @property
    def is_sandbox(self):
        if self._sf_auth._is_sandbox is None:
            cur = self.cursor()
            cur.set_row_factory(dict)
            cur.execute("SELECT IsSandbox FROM Organization")
            self._sf_auth._is_sandbox = cur.fetchone()['IsSandbox']
        return self._sf_auth._is_sandbox
