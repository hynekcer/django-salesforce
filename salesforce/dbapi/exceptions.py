# All error types described in DB API 2 are implemented the same way as in
# Django (1.10 to 2.18)., otherwise some exceptions are not correctly reported in it.
import sys
from . import log
PY3 = sys.version_info[0] == 3
# pylint:disable=too-few-public-methods


class SalesforceWarning(Exception):
    pass

class Error(Exception if PY3 else StandardError):  # NOQA: # pylint: disable=undefined-variable
    pass                                           # StandardError is undefined in PY3


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
        if data:
            data_0 = data[0]
            separ = ' '
            if '\n' in message:
                separ = '\n  '
                message = message.replace('\n', separ)
            if 'errorCode' in data_0:
                subreq = ''
                if 'referenceId' in data_0:
                    subreq = " (in subrequest '{}')".format(data_0['referenceId'])
                message = data_0['errorCode'] + subreq + separ + message
            if 'fields' in data_0:
                message += separ + 'FIELDS: {}'.format(data_0['fields'])
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
    pass  # e.g. network, auth


class IntegrityError(SalesforceError):
    pass  # e.g. foreign key


class InternalError(SalesforceError):
    pass


class ProgrammingError(SalesforceError):
    pass  # e.g sql syntax


class NotSupportedError(SalesforceError):
    pass
