# All error types described in DB API 2 are implemented the same way as in
# Django (1.10 to 2.18)., otherwise some exceptions are not correctly reported in it.
from . import log
import sys
PY3 = sys.version_info[0] == 3


class Error(Exception if PY3 else StandardError):  # NOQA: StandardError undefined on PY3
    pass


class InterfaceError(Error):
    pass  # should be raised directly


class DatabaseError(Error):
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


class DataError(SalesforceError):
    pass


class OperationalError(SalesforceError):
    pass


class IntegrityError(SalesforceError):
    pass


class InternalError(SalesforceError):
    pass


class ProgrammingError(SalesforceError):
    pass


class NotSupportedError(SalesforceError):
    pass
