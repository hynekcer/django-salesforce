"""
Dummy Salesforce driver that simulates part of DB API 2.0

https://www.python.org/dev/peps/pep-0249/

It can run without Django installed, but still Django is the main purpose.

Low level code for Salesforce is also here.
"""
import datetime
import decimal
import logging
import socket
import sys
import threading
import types
import warnings
import weakref
from collections import namedtuple
from itertools import islice

import pytz
import requests
from requests.adapters import HTTPAdapter

import salesforce
from salesforce.auth import SalesforcePasswordAuth
from salesforce.dbapi import get_max_retries
from salesforce.dbapi import settings  # i.e. django.conf.settings
from salesforce.dbapi.exceptions import (  # NOQA pylint: disable=unused-import
    Error, InterfaceError, DatabaseError, DataError, OperationalError, IntegrityError,
    InternalError, ProgrammingError, NotSupportedError, SalesforceError, PY3)

try:
    import beatbox  # pylint: disable=unused-import
except ImportError:
    beatbox = None

log = logging.getLogger(__name__)

# -- API global constants

apilevel = "2.0"  # see https://www.python.org/dev/peps/pep-0249

# Every thread should use its own database connection, because waiting
# on a network connection for query response would be a bottle neck within
# REST API.

# Two thread-safety models are possible:

# Create the connection by `connect(**params)` if you use it with Django or
# with another app that has its own thread safe connection pool. and
# create the connection by connect(**params).
threadsafety = 1

# Or create and access the connection by `get_connection(alias, **params)`
# if the pool should be managed by this driver. Then you can expect:
# threadsafety = 2

# (Both variants allow multitenant architecture with dynamic authentication
# where a thread can frequently change the organization domain that it serves.)


# This paramstyle uses '%s' parameters.
paramstyle = 'format'

# --- private global constants

# Values of seconds are with 3 decimal places in SF, but they are rounded to
# whole seconds for the most of fields.
SALESFORCE_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%f+0000'

# ---

request_count = 0  # global counter

connect_lock = threading.Lock()
thread_connections = threading.local()


class RawConnection(object):
    """
    parameters:
        settings_dict:  like settings.SADABASES['salesforce'] in Django
        alias:          important if the authentication should be shared for more thread
        errorhandler: function with following signature
            ``errorhandler(connection, cursor, errorclass, errorvalue)``
        use_introspection: bool
    """
    # pylint:disable=too-many-instance-attributes

    Error = Error
    InterfaceError = InterfaceError
    DatabaseError = DatabaseError
    DataError = DataError
    OperationalError = OperationalError
    IntegrityError = IntegrityError
    InternalError = InternalError
    ProgrammingError = ProgrammingError
    NotSupportedError = NotSupportedError

    def __init__(self, settings_dict, alias=None, errorhandler=None, use_introspection=None):

        # private members:
        self.alias = alias
        self.errorhandler = errorhandler
        self.use_introspection = use_introspection if use_introspection is not None else True  # TODO
        self.settings_dict = settings_dict
        self.messages = []

        self._sf_session = None
        self.api_ver = salesforce.API_VERSION
        self.debug_silent = False

        self._last_used_cursor = None  # weakref.proxy for single thread debugging

        if errorhandler:
            warnings.warn("DB-API extension errorhandler used")
            # TODO implement it by a context manager around handle_api_exceptions (+ this warning)
            raise NotSupportedError

        # The SFDC database is connected as late as possible if only tests
        # are running. Some tests don't require a connection.
        if not getattr(settings, 'SF_LAZY_CONNECT', 'test' in sys.argv):  # TODO don't use argv
            self.make_session()

    # -- public methods

    # Methods close() and commit() can be safely ignored, because everything is
    # committed automatically and the REST API is stateless.

    # pylint:disable=no-self-use
    def close(self):
        pass

    def commit(self):
        # "Database modules that do not support transactions should implement
        # this method with void functionality."
        pass

    def rollback(self):
        log.info("Rollback is not implemented.")
    # pylint:enable=no-self-use

    def cursor(self):
        return Cursor(self)

    # -- private attributes

    @property
    def sf_session(self):
        if self._sf_session is None:
            self.make_session()
        return self._sf_session

    def make_session(self):
        """Authenticate and get the name of assigned SFDC data server"""
        with connect_lock:
            if self._sf_session is None:
                sf_session = requests.Session()
                # TODO configurable class Salesforce***Auth
                sf_session.auth = SalesforcePasswordAuth(db_alias=self.alias,
                                                         settings_dict=self.settings_dict)
                sf_instance_url = sf_session.auth.instance_url
                sf_requests_adapter = HTTPAdapter(max_retries=get_max_retries())
                sf_session.mount(sf_instance_url, sf_requests_adapter)
                # Additional header works, but the improvement is immeasurable for
                # me. (less than SF speed fluctuation)
                # sf_session.header = {'accept-encoding': 'gzip, deflate', 'connection': 'keep-alive'}
                self._sf_session = sf_session

    def rest_api_url(self, *url_parts, **kwargs):
        """Join the URL of REST_API

        parameters:
            upl_parts:  strings that are joined to the url by "/".
                a REST url like https://na1.salesforce.com/services/data/v44.0/
                is usually added, but not if the first string starts with https://
            api_ver:  API version that should be used instead of connection.api_ver
                default. A special api_ver="" can be used to omit api version
                (for request to ask for available api versions)
        Examples: self.rest_api_url("query?q=select+id+from+Organization")
                  self.rest_api_url("sobject", "Contact", id, api_ver="45.0")
                  self.rest_api_url(api_ver="")   # versions request
        Output:

                  https://na1.salesforce.com/services/data/v44.0/query?q=select+id+from+Organization
                  https://na1.salesforce.com/services/data/v45.0/sobject/Contact/003DD00000000XYAAA
                  https://na1.salesforce.com/services/data
        """
        if url_parts and url_parts[0].startswith('https://'):
            return '/'.join(url_parts)
        api_ver = kwargs.pop('api_ver', None)
        assert not kwargs
        api_ver = api_ver if api_ver is not None else self.api_ver
        base = self.sf_session.auth.instance_url
        prefix = 'services/data' + ('/v{api_ver}'.format(api_ver=api_ver) if api_ver else '')
        return '/'.join((base, prefix) + url_parts)

    def handle_api_exceptions(self, method, *url_parts, **kwargs):
        """Call REST API and handle exceptions
        Params:
            method:  'HEAD', 'GET', 'POST', 'PATCH' or 'DELETE'
            url_parts: like in rest_api_url() method
            api_ver:   like in rest_api_url() method
            kwargs: other parameters passed to requests.request,
                but the usual important parameters are only
                    data=json.dumps(...)
                    headers={'Content-Type': 'application/json'}
        """
        # pylint:disable=too-many-branches
        global request_count  # used only in single thread tests - OK # pylint:disable=global-statement
        assert method in ('HEAD', 'GET', 'POST', 'PATCH', 'DELETE')
        api_ver = kwargs.pop('api_ver', None)
        cursor_context = kwargs.pop('cursor_context', None)
        url = self.rest_api_url(*url_parts, api_ver=api_ver)
        # The 'verify' option is about verifying TLS certificates
        kwargs_in = {'timeout': getattr(settings, 'SALESFORCE_QUERY_TIMEOUT', (4, 15)),
                     'verify': True}
        kwargs_in.update(kwargs)
        log.debug('Request API URL: %s', url)
        request_count += 1
        session = self.sf_session
        try:
            response = session.request(method, url, **kwargs_in)
        except requests.exceptions.Timeout:
            raise SalesforceError("Timeout, URL=%s" % url)
        if response.status_code == 401:  # Unauthorized
            # Reauthenticate and retry (expired or invalid session ID or OAuth)
            data = response.json()[0]
            if data['errorCode'] == 'INVALID_SESSION_ID':
                token = session.auth.reauthenticate()
                if 'headers' in kwargs:
                    kwargs['headers'].update(dict(Authorization='OAuth %s' % token))
                try:
                    response = session.request(method, url, **kwargs_in)
                except requests.exceptions.Timeout:
                    raise SalesforceError("Timeout, URL=%s" % url)

        # status codes help
        # https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/errorcodes.htm
        if response.status_code <= 304:
            # OK (200, 201, 204, 300, 304)
            return response

        # Error (400, 403, 404, 405, 415, 500)
        # TODO Remove this verbose setting after tuning of specific messages.
        #      Currently it is better more or less.
        verbose = not self.debug_silent
        if 'json' not in response.headers.get('Content-Type', ''):
            raise OperationalError("HTTP error code %d: %s" % (response.status_code, response.text))
        # Other Errors are reported in the json body
        data = response.json()[0]
        if response.status_code == 404:  # ResourceNotFound
            if (method == 'DELETE') and data['errorCode'] in ('ENTITY_IS_DELETED',
                                                              'INVALID_CROSS_REFERENCE_KEY'):
                # It is a delete command and the object is in trash bin or
                # completely deleted or it only could be a valid Id for this type
                # then is ignored similarly to delete by a classic database query:
                # DELETE FROM xy WHERE id = 'something_deleted_yet'
                return None  # TODO add a warning and add it to messages
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
        elif data['errorCode'] == 'METHOD_NOT_ALLOWED':  # 405
            raise SalesforceError('%s: %s %s' % (data['message'], method, url), data, response, verbose)
        # some kind of failed query
        raise SalesforceError('%s' % data, data, response, verbose)

    @property
    def last_used_cursor(self):
        try:
            return self._last_used_cursor()  # pylint:disable=not-callable
        except NameError:
            return None

    @last_used_cursor.setter
    def last_used_cursor(self, cursor):
        self._last_used_cursor = weakref.proxy(cursor)


Connection = RawConnection


# DB API function
def connect(**params):
    return Connection(**params)


def get_connection(alias, **params):
    if not hasattr(thread_connections, alias):
        setattr(thread_connections, alias, connect(alias=alias, **params))
    return getattr(thread_connections, alias)


class Cursor(object):
    """Cursor (local part is simple, remote part is stateless for small result sets)

    From SDFC documentation (combined from SOQL, REST, APEX)
    Query results are returned from SFDC by blocks of 2000 rows, by default.
    It is guaranted that the size of result block is not smaller than 200 rows,
    and not longer than 2000 rows. A remote locator remains open until all rows
    are consumed. A maximum of 10 open locators per user are allowed, otherwise
    the oldest locator (cursor) is deleted by SFDC. Query locators older than
    15 minutes are also deleted. The query locator works without transactions
    and it should be expected that the data after 2000 rows could affected by
    later updates and may not match the `where` condition.

    The local part of the cursor is only an index into the last block of 2000
    rows. The number of local cursors is unrestricted.

    Queries with binary fields Base64 (e.g. attachments) are returned by one row.
    the best it to get more rows without binary fields and then to query
    for complete rows, one by one.
    """

    # pylint:disable=too-many-instance-attributes
    def __init__(self, connection):
        # DB API attributes (public, ordered by documentation PEP 249)
        self.description = None
        self.rowcount = -1
        self.arraysize = 1  # writable, but ignored finally
        # db api extensions
        self.rownumber = None
        self.connection = connection
        self.messages = []
        self.lastrowid = None
        # private
        self._results = not_executed_yet()

    # -- DB API methods

    # .callproc(...)  noit implemented

    def close(self):
        self.connection = None

    def execute(self, operation, parameters=None):
        self._clean()
        sqltype = operation.split(None, 1)[0].upper()
        _ = sqltype  # NOQA
        # TODO
        if sqltype == 'SELECT':
            self.execute_select(operation, parameters)
            self.rowcount = 1
            self.description = ()
        else:
            raise ProgrammingError

    def executemany(self, operation, seq_of_parameters):
        self._clean()
        for param in seq_of_parameters:
            self.execute(operation, param)

    def __iter__(self):
        self._check()
        for row in self._results:
            yield row

    def fetchone(self):
        self._check()
        return next(self, None)

    def fetchmany(self, size=None):
        self._check()
        if size is None:
            size = self.arraysize
        return list(islice(self, size))

    def fetchall(self):
        self._check()
        return [row for row in self]

    # nextset()  not implemented

    def setinputsizes(self, sizes):
        pass  # this method is allowed to do nothing

    def setoutputsize(self, size, column=None):
        pass  # this method is allowed to do nothing

    # -- private methods

    def err_hand(self, errorclass, errorvalue):
        "call the errorhandler"
        self.connection.errorhandler(self.connection, self, errorclass, errorvalue)

    def _check(self):
        if not self.connection:
            raise InterfaceError("Cursor Closed")
        self.connection.last_used_cursor = self  # is a weakref

    def _clean(self):
        self.description = None
        self.rowcount = -1
        self.rownumber = None
        del self.messages[:]
        self.lastrowid = None
        self._results = not_executed_yet()
        self._check()

    def execute_select(self, operation, parameters):
        pass

    def handle_api_exceptions(self, method, *url_parts, **kwargs):
        return self.connection.handle_api_exceptions(method, *url_parts, cursor_context=self, **kwargs)


#                              The first two items are mandatory. (name, type)
CursorDescription = namedtuple('CursorDescription', 'name type_code '
                               'display_size internal_size precision scale null_ok')
CursorDescription.__new__.func_defaults = 7 * (None,)


def not_executed_yet():
    raise Connection.InterfaceError("called fetch...() before execute()")
    yield  # pylint:disable=unreachable


def signalize_extensions():
    """DB API 2.0 extension are reported by warnings at run-time."""
    warnings.warn("DB-API extension cursor.rownumber used")
    warnings.warn("DB-API extension connection.<exception> used")  # TODO
    warnings.warn("DB-API extension cursor.connection used")
    # not implemented DB-API extension cursor.scroll()
    warnings.warn("DB-API extension cursor.messages used")
    warnings.warn("DB-API extension connection.messages used")
    warnings.warn("DB-API extension cursor.next() used")
    warnings.warn("DB-API extension cursor.__iter__() used")
    warnings.warn("DB-API extension cursor.lastrowid used")
    warnings.warn("DB-API extension .errorhandler used")


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

# basic conversions


def register_conversion(type_, json_conv, sql_conv=None, subclass=False):
    json_conversions[type_] = json_conv
    sql_conversions[type_] = sql_conv or json_conv
    if subclass and type_ not in subclass_conversions:
        subclass_conversions.append(type_)


def quoted_string_literal(txt):
    """
    SOQL requires single quotes to be escaped.
    http://www.salesforce.com/us/developer/docs/soql_sosl/Content/sforce_api_calls_soql_select_quotedstringescapes.htm
    """
    try:
        return "'%s'" % (txt.replace("\\", "\\\\").replace("'", "\\'"),)
    except TypeError:
        raise NotImplementedError("Cannot quote %r objects: %r" % (type(txt), txt))


def date_literal(dat):
    if not dat.tzinfo:
        import time
        tz = pytz.timezone(settings.TIME_ZONE)
        dat = tz.localize(dat, is_dst=time.daylight)
    # Format of `%z` is "+HHMM"
    tzname = datetime.datetime.strftime(dat, "%z")
    return datetime.datetime.strftime(dat, "%Y-%m-%dT%H:%M:%S.000") + tzname


def arg_to_soql(arg):
    """
    Perform necessary SOQL quoting on the arg.
    """
    conversion = sql_conversions.get(type(arg))
    if conversion:
        return conversion(arg)
    for type_ in subclass_conversions:
        if isinstance(arg, type_):
            return sql_conversions[type_](arg)
    return sql_conversions[str](arg)


def arg_to_json(arg):
    """
    Perform necessary JSON conversion on the arg.
    """
    conversion = json_conversions.get(type(arg))
    if conversion:
        return conversion(arg)
    for type_ in subclass_conversions:
        if isinstance(arg, type_):
            return json_conversions[type_](arg)
    return json_conversions[str](arg)


# supported types converted from Python to SFDC

# conversion before conversion to json (for Insert and Update commands)
json_conversions = {}

# conversion before formating a SOQL (for Select commands)
sql_conversions = {}

subclass_conversions = []

# pylint:disable=bad-whitespace,no-member
register_conversion(int,             json_conv=str)
register_conversion(float,           json_conv=lambda o: '%.15g' % o)
register_conversion(type(None),      json_conv=lambda s: None,          sql_conv=lambda s: 'NULL')
register_conversion(str,             json_conv=lambda o: o,             sql_conv=quoted_string_literal)  # default
register_conversion(bool,            json_conv=lambda s: str(s).lower())
register_conversion(datetime.date,   json_conv=lambda d: datetime.date.strftime(d, "%Y-%m-%d"))
register_conversion(datetime.datetime, json_conv=date_literal)
register_conversion(datetime.time,   json_conv=lambda d: datetime.time.strftime(d, "%H:%M:%S.%f"))
register_conversion(decimal.Decimal, json_conv=float, subclass=True)
# the type models.Model is registered from backend, because it is a Django type

if not PY3:
    register_conversion(types.LongType, json_conv=str)
    register_conversion(types.UnicodeType,
                        json_conv=lambda s: s.encode('utf8'),
                        sql_conv=lambda s: quoted_string_literal(s.encode('utf8')))
# pylint:enable=bad-whitespace,no-member
