import logging
import sys

log = logging.getLogger(__name__)
PY3 = sys.version_info[0] == 3

# All error types described in DB API 2 are implemented the same way as in
# Django 1.8, otherwise some exceptions are not correctly reported in it.

Exception_ = Exception if PY3 else StandardError  # NOQA


class Error(Exception_):
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
    DatabaseError reported by Salesforce API (can be searched in their docs)

    https://developer.salesforce.com/docs/atlas.en-us.api.meta/api/sforce_api_calls_concepts_core_data_objects.htm
    by "SalesforceError 'errorCode'..." (uppercase code), the same codes
    for REST / SOAP API mostly:

    Parameters:
        message:  Only the message from Salesforce
        data:  A complete error response dictionary from SF with relevant information
                 {"message:... "errorCode":...}  and some apropriate keys, e.g.
                 {"message:... "errorCode":... "fields":...}
        response:  The requests.response object with status_code,
            response headers and the complete request
        verbosity:  Unexpected errors should be set verbose=1, expected
            errors in tests quiet (=0), debugging (=2).
        kwargs:  Additional info from django-salesforce

    """

    def __init__(self, message='', data=None, response=None, verbosity=1, **kwargs):
        # optimized for readability if verbosity==1 and message==None (default extraction)
        # no information should be repeated and nothing important omitted
        sample_text_length = 200
        if data:
            assert isinstance(data, dict), "parameter 'data' in SalesforceError  must be a dict"
            data_copy = data.copy()
        else:
            data_copy = None

        error_code = None
        if not message:  # extract a default message
            if data and 'message' in data:
                message = data_copy.pop('message')
            elif response:
                message = response.text[:sample_text_length]
            else:
                raise ProgrammingError("Not enough parameters to SalesforceError")

            if data:
                if 'errorCode' in data:  # REST API
                    error_code = data_copy.pop('errorCode')
                elif 'statusCode' in data:  # SOAP API
                    error_code = data_copy.pop('statusCode')
            if error_code:
                message = '%s %s' % (error_code, message)

        DatabaseError.__init__(self, message)
        self.data = data
        self.response = response
        self.verbosity = verbosity
        self.kwargs = kwargs

        if verbosity:
            out = ['SalesforceError']
            if message:
                if '^' in message and '\n' in message:
                    # due to position marker in SOQL sample
                    out.append('\n{}\n'.format(message))
                else:
                    out.append('"{}"'.format(message))
            if data:
                if data_copy:
                    out.append(repr(data_copy))
            if response:
                out.append('(http {})'.format(response.status_code))
            if not data and response:
                out.append(response.text[:sample_text_length])
            if kwargs:
                out.append(repr(kwargs))
            # verbosity 2
            if verbosity > 1 and response:
                out.append('\n' + repr(response.__dict__))
            # log
            if verbosity:
                log.info(' '.join('{}'.format(x) for x in out))
