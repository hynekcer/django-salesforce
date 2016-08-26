# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Automatic table creation is not supported by the Salesforce backend.
"""
from django.conf import settings
from django.db.backends.base.creation import BaseDatabaseCreation

import logging
log = logging.getLogger(__name__)


class DatabaseCreation(BaseDatabaseCreation):
    def __init__(self, *args, **kwargs):
        super(DatabaseCreation, self).__init__(*args, **kwargs)
        self.sf_orig_settings_dict = None

    def create_test_db(self, verbosity=1, autoclobber=False, serialize=True, keepdb=False):
        # keepdb: ignored because Django can not create a SF database
        self.connection.is_in_test = True
        # if the test database is different
        if self.connection.settings_dict['TEST']:
            settings_dict = self.connection.settings_dict
            self.sf_orig_settings_dict = settings_dict.copy()
            self.connection.close()
            self.connection._sf_auth.del_token()
            self.connection._sf_auth._is_sandbox = None

            settings_dict.update(settings_dict['TEST'])
            settings.DATABASES[self.connection.alias].update(settings_dict['TEST'])
            if 'USER' in settings_dict['TEST'] and 'NAME' not in settings_dict['TEST']:
                settings_dict['NAME'] = settings_dict['USER']
                settings.DATABASES[self.connection.alias]['NAME'] = settings_dict['USER']
            del settings_dict['TEST']
            if 'TEST' in settings.DATABASES[self.connection.alias]:
                del settings.DATABASES[self.connection.alias]['TEST']

            if verbosity >= 1:
                test_db_repr = ''
                if verbosity >= 2:
                    test_database_name = self.connection.settings_dict['NAME']
                    test_db_repr = " ('%s')" % test_database_name
                log.info("Preparing configuration for the test database '%s'%s",
                         self.connection.alias, test_db_repr)
        test_database_name = self.connection.settings_dict['NAME']
        return test_database_name

    def destroy_test_db(self, old_database_name, verbosity=1, keepdb=False):
        # old_database_name: ignored because uses sf_orig_settings_dict
        # keepdb: ignored because Django can not create a SF database
        test_database_name = self.connection.settings_dict['NAME']
        if self.sf_orig_settings_dict:
            if verbosity >= 1:
                test_db_repr = ''
                if verbosity >= 2:
                    test_db_repr = " ('%s')" % test_database_name
                log.info("No test database to destroy for alias '%s'%s...",
                         self.connection.alias, test_db_repr)
            self.connection._sf_auth.del_token()
            self.connection._sf_auth._is_sandbox = None
            self.connection.is_in_test = False
            self.connection.settings_dict.clear()
            self.connection.settings_dict.update(self.sf_orig_settings_dict)
            settings.DATABASES[self.connection.alias].clear()
            settings.DATABASES[self.connection.alias].update(self.sf_orig_settings_dict)
        # self.connection.settings_dict['NAME'] = old_database_name

    def test_db_signature(self):
        settings_dict = self.connection.settings_dict
        return (
            settings_dict['HOST'],
            settings_dict['ENGINE'],
            settings_dict['USER']
        )
