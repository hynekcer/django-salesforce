import logging
import sys

log = logging.getLogger(__name__)
PY3 = sys.version_info[0] == 3

# All error types described in DB API 2 are implemented the same way as in
# Django 1.8, otherwise some exceptions are not correctly reported in it.


class Error(Exception if PY3 else StandardError):
    pass


class InterfaceError(Error):
    pass  # should be raised directly


class DatabaseError(Error):
    pass


class DataError(DatabaseError):
    pass


class OperationalError(DatabaseError):
    pass


class IntegrityError(DatabaseError):
    pass


class InternalError(DatabaseError):
    pass


class ProgrammingError(DatabaseError):
    pass


class NotSupportedError(DatabaseError):
    pass


class SalesforceError(DatabaseError):
    """
    DatabaseError that usually gets detailed error information from SF response

    in the second parameter, decoded from REST, that frequently need not to be
    displayed.
    """
    def __init__(self, message='', data=None, response=None, verbose=False):
        DatabaseError.__init__(self, message)
        self.data = data
        self.response = response
        self.verbose = verbose
        if verbose:
            log.info("Error (debug details) %s\n%s", response.text,
                     response.__dict__)
