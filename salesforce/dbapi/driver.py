"""
Dummy Salesforce driver that simulates some parts of DB API 2

https://www.python.org/dev/peps/pep-0249/
should be independent on Django.db
and if possible should be independent on django.conf.settings
Code at lower level than DB API should be also here.
"""
from collections import namedtuple
import requests
import socket
# import time
# import weakref
import logging

from django.conf import settings
from salesforce.dbapi.exceptions import (
    Error, DatabaseError, DataError, IntegrityError,
    InterfaceError, InternalError, NotSupportedError,
    OperationalError, ProgrammingError, SalesforceError,
)
try:
    import beatbox
except ImportError:
    beatbox = None


apilevel = "2.0"
# threadsafety = ...

# uses '%s' style parameters
paramstyle = 'format'

request_count = 0  # global counter

log = logging.getLogger(__name__)


def standard_errorhandler(connection, cursor, errorclass, errorvalue):
    "The errorhandler can be also used for warnings reporting"
    if cursor:
        cursor.messages.append(errorclass, errorvalue)
    elif connection:
        connection.messages.append(errorclass, errorvalue)
    else:
        pass  # maybe raise special
    if isinstance(errorclass, Error) and (isinstance(errorclass, InterfaceError) or
                                          filter(errorclass, errorvalue)):
        raise errorclass(errorvalue)
# ---


CursorDescription = namedtuple(
    'CursorDescription',
    'name, type_code, display_size, internal_size, precision, scale, null_ok'
)

# def date(year, month, day):
#    return datetime.date(year, month, day)
#
# def time(hour, minute, second):
#    return datetime.time(hour, minute, second)
#
# def timestamp(year, month, day, hour, minute, second):
#    return datetime.datetime(year, month, day, hour, minute, second)
#
# def DateFromTicks(ticks):
#     return Date(*time.localtime(ticks)[:3])
#
# def TimeFromTicks(ticks):
#     return Time(*time.localtime(ticks)[3:6])
#
# def TimestampFromTicks(ticks):
#     return Timestamp(*time.localtime(ticks)[:6])
#
# class DBAPITypeObject:
#     def __init__(self,*values):
#         self.values = values
#     def __cmp__(self,other):
#         if other in self.values:
#             return 0
#         if other < self.values:
#             return 1
#         else:
#             return -1

TODO = ['TODO']


class Cursor(object):

    # DB API methods  (except private "_*" names)

    def __init__(self, connection):
        # DB API attributes
        self.description = None
        self.rowcount = None
        self.lastrowid = None
        self.messages = []
        # static
        self.arraysize = 1
        # other
        self.connection = connection
        # self.connection = weakref.proxy(connection)

    def err_hand(self, errorclass, errorvalue):
        "call the errorhandler"
        self.connection.errorhandler(self.connection, self.cursor, errorclass, errorvalue)

    def _check(self):
        if not self.connection:
            raise InterfaceError("Cursor Closed")

    def _clean(self):
        self.description = None
        self.rowcount = -1
        self.lastrowid = None
        self.messages = []
        self._check()

    def close(self):
        self.connection = None

    def execute(self, operation, parameters):
        self._clean()
        sqltype = operation.split(None, 1)[0].upper()
        # TODO
        import pdb; pdb.set_trace()
        if TODO == 'SELECT':
            self.description = ()
        self.rowcount = TODO

    def executemany(self, operation, seq_of_parameters):
        self._clean()
        for param in seq_of_parameters:
            self.execute(operation, param)

    def fetchone(self):
        self._check()
        TODO

    def fetchmany(self, size=None):
        # size by SF
        # size = size or cursor.arraysize
        self._check()
        for x in TODO:
            pass

    def fetchall(self):
        self._check()
        for x in TODO:
            pass

    def setinputsizes(self):
        pass

    def setoutputsize(size, column=None):
        pass

    # other methods

        #   (name=,         # req
        #   type_code=,     # req
        #   display_size=,
        #   internal_size=,
        #   precision=,
        #   scale=,
        #   null_ok=)


class Connection(object):
    """
    params:
            connection params ...,
            errorhandler: function with following arguments
                    ``errorhandler(connection, cursor, errorclass, errorvalue)``
            use_introspection: bool
    """
    # close and commit can be safely ignored because everything is
    # committed automatically and REST is stateles. They are
    # unconditionally required by Django 1.6+.

    Error = Error
    InterfaceError = InterfaceError
    DatabaseError = DatabaseError
    DataError = DataError
    OperationalError = OperationalError
    IntegrityError = IntegrityError
    InternalError = InternalError
    ProgrammingError = ProgrammingError
    NotSupportedError = NotSupportedError

    # DB API methods

    def __init__(self, **params):
        self.errorhandler = params.pop('errorhandler', standard_errorhandler)
        self.use_introspection = params.pop('use_introspection', True)
        #...
        self._connection = True  #...

    def close(self):
        self._check()
        self._connection = None
        print("close..")

    def commit(self):
        self._check()

    def rollback(self):
        self._check()
        log.info("Rollback is not implemented.")

    def cursor(self):
        self._check()
        print("cursor ???")
        return Cursor(self)

    # other methods

    def _check(self):
        if not self._connection:
            raise InterfaceError("Connection Closed")

    def err_hand(self, errorclass, errorvalue):
        "call the errorhandler"
        self.errorhandler(self, None, errorclass, errorvalue)

    def put_metadata(self, data):
        """
        Put metadata from models to prefill metadate cache, insted of introspection.
        It is important for:
            relationship names
            Date, Time, Timestamp
        """
        pass


# DB API function
def connect(**params):
    return Connection(**params)


# LOW LEVEL


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
    # import pdb; pdb.set_trace()
    # print("== REQUEST %s | %s | %s | %s" % (url, f, args, kwargs))
    global request_count
    # The 'verify' option is about verifying SSL certificates
    kwargs_in = {'timeout': getattr(settings, 'SALESFORCE_QUERY_TIMEOUT', 3),
                 'verify': True}
    kwargs_in.update(kwargs)
    _cursor = kwargs_in.pop('_cursor', None)
    log.debug('Request API URL: %s' % url)
    request_count += 1
    try:
        response = f(url, *args, **kwargs_in)
    # TODO some timeouts can be rarely raised as "SSLError: The read operation timed out"
    except requests.exceptions.Timeout:
        raise SalesforceError("Timeout, URL=%s" % url)
    if response.status_code == 401:
        # Unauthorized (expired or invalid session ID or OAuth)
        data = response.json()[0]
        if(data['errorCode'] == 'INVALID_SESSION_ID'):
            token = f.__self__.auth.reauthenticate()
            if('headers' in kwargs):
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
    verbose = not getattr(getattr(_cursor, 'query', None), 'debug_silent', False)
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
    if(data['errorCode'] == 'INVALID_FIELD'):
        raise SalesforceError(data['message'], data, response, verbose)
    elif(data['errorCode'] == 'MALFORMED_QUERY'):
        raise SalesforceError(data['message'], data, response, verbose)
    elif(data['errorCode'] == 'INVALID_FIELD_FOR_INSERT_UPDATE'):
        raise SalesforceError(data['message'], data, response, verbose)
    elif(data['errorCode'] == 'METHOD_NOT_ALLOWED'):
        raise SalesforceError('%s: %s' % (url, data['message']), data, response, verbose)
    # some kind of failed query
    else:
        raise SalesforceError('%s' % data, data, response, verbose)
