"""
Dummy Salesforce driver that simulates some parts of DB API 2

https://www.python.org/dev/peps/pep-0249/
should be independent on Django.db
and if possible should be independent on django.conf.settings
Code at lower level than DB API should be also here.
"""
import logging
import socket

import requests

from salesforce.dbapi import settings  # i.e. django.conf.settings
from salesforce.dbapi.exceptions import (  # NOQA pylint: disable=unused-import
    Error, InterfaceError, DatabaseError, DataError, OperationalError, IntegrityError,
    InternalError, ProgrammingError, NotSupportedError, SalesforceError)

try:
    import beatbox
except ImportError:
    beatbox = None

log = logging.getLogger(__name__)

apilevel = "2.0"
# threadsafety = ...

# uses '%s' style parameters
paramstyle = 'format'

API_STUB = '/services/data/v35.0'

request_count = 0  # global counter


class Connection(object):
    # close and commit can be safely ignored because everything is
    # committed automatically and REST is stateles.

    # pylint:disable=no-self-use
    def close(self):
        pass

    def commit(self):
        pass

    def rollback(self):
        log.info("Rollback is not implemented.")


# DB API function
def connect(**params):  # pylint:disable=unused-argument
    return Connection()


# LOW LEVEL


# pylint:disable=too-many-arguments
def getaddrinfo_wrapper(host, port, family=socket.AF_INET, socktype=0, proto=0, flags=0):
    """Patched 'getaddrinfo' with default family IPv4 (enabled by settings IPV4_ONLY=True)"""
    return orig_getaddrinfo(host, port, family, socktype, proto, flags)


# patch to IPv4 if required and not patched by anything other yet
if getattr(settings, 'IPV4_ONLY', False) and socket.getaddrinfo.__module__ in ('socket', '_socket'):
    log.info("Patched socket to IPv4 only")
    orig_getaddrinfo = socket.getaddrinfo
    # replace the original socket.getaddrinfo by our version
    socket.getaddrinfo = getaddrinfo_wrapper

# ----


def handle_api_exceptions(url, f, *args, **kwargs):
    """Call REST API and handle exceptions
    Params:
        f:  requests.get or requests.post...
        _cursor: sharing the debug information in cursor
    """
    # pylint:disable=too-many-branches
    global request_count  # used only in single thread tests - OK # pylint:disable=global-statement
    # The 'verify' option is about verifying SSL certificates
    kwargs_in = {'timeout': getattr(settings, 'SALESFORCE_QUERY_TIMEOUT', (4, 15)),
                 'verify': True}
    kwargs_in.update(kwargs)
    _cursor = kwargs_in.pop('_cursor', None)
    log.debug('Request API URL: %s', url)
    request_count += 1
    try:
        response = f(url, *args, **kwargs_in)
    # TODO some timeouts can be rarely raised as "SSLError: The read operation timed out"
    except requests.exceptions.Timeout:
        raise SalesforceError("Timeout, URL=%s" % url)
    if response.status_code == 401:
        # Unauthorized (expired or invalid session ID or OAuth)
        data = response.json()[0]
        if data['errorCode'] == 'INVALID_SESSION_ID':
            token = f.__self__.auth.reauthenticate()
            if 'headers' in kwargs:
                kwargs['headers'].update(dict(Authorization='OAuth %s' % token))
            try:
                response = f(url, *args, **kwargs_in)
            except requests.exceptions.Timeout:
                raise SalesforceError("Timeout, URL=%s" % url)

    if response.status_code in (200, 201, 204):
        return response

    # TODO Remove this verbose setting after tuning of specific messages.
    #      Currently it is better more or less.
    # http://www.salesforce.com/us/developer/docs/api_rest/Content/errorcodes.htm
    verbose = not getattr(getattr(_cursor, 'db', None), 'debug_silent', False)
    if 'json' not in response.headers.get('Content-Type', ''):
        raise OperationalError("HTTP error code %d: %s" % (response.status_code, response.text))
    else:
        # Errors are reported in the body
        data = response.json()[0]
    if response.status_code == 404:  # ResourceNotFound
        if (f.__func__.__name__ == 'delete') and data['errorCode'] in (
                'ENTITY_IS_DELETED', 'INVALID_CROSS_REFERENCE_KEY'):
            # It is a delete command and the object is in trash bin or
            # completely deleted or it only could be a valid Id for this type
            # then is ignored similarly to delete by a classic database query:
            # DELETE FROM xy WHERE id = 'something_deleted_yet'
            return None
        else:
            # if this Id can not be ever valid.
            raise SalesforceError("Couldn't connect to API (404): %s, URL=%s"
                                  % (response.text, url), data, response, verbose
                                  )
    if data['errorCode'] == 'INVALID_FIELD':
        raise SalesforceError(data['message'], data, response, verbose)
    elif data['errorCode'] == 'MALFORMED_QUERY':
        raise SalesforceError(data['message'], data, response, verbose)
    elif data['errorCode'] == 'INVALID_FIELD_FOR_INSERT_UPDATE':
        raise SalesforceError(data['message'], data, response, verbose)
    elif data['errorCode'] == 'METHOD_NOT_ALLOWED':
        raise SalesforceError('%s: %s' % (url, data['message']), data, response, verbose)
    # some kind of failed query
    else:
        raise SalesforceError('%s' % data, data, response, verbose)
