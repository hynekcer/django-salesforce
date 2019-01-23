"""
Dummy Salesforce driver that simulates some parts of DB API 2

https://www.python.org/dev/peps/pep-0249/
should be independent on Django.db
and if possible should be independent on django.conf.settings
Code at lower level than DB API should be also here.
"""
import datetime
import decimal
import logging
import socket
import sys
import threading
import types
import warnings

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

apilevel = "2.0"
# threadsafety = ...

# uses '%s' style parameters
paramstyle = 'format'

API_STUB = '/services/data/v35.0'

# Values of seconds are with 3 decimal places in SF, but they are rounded to
# whole seconds for the most of fields.
SALESFORCE_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%f+0000'

request_count = 0  # global counter

connect_lock = threading.Lock()


class RawConnection(object):
    """
    parameters:
        settings_dict:  like settings.SADABASES['salesforce'] in Django
        alias:          important if the authentication should be shared for more thread
        errorhandler: function with following signature
            ``errorhandler(connection, cursor, errorclass, errorvalue)``
        use_introspection: bool
    """

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
        self.alias = alias
        self.errorhandler = errorhandler
        self.use_introspection = use_introspection if use_introspection is not None else True  # TODO
        self.settings_dict = settings_dict

        self._sf_session = None

        if errorhandler:
            warnings.warn("DB-API extension errorhandler used")
            # TODO implement it by a context manager around handle_api_exceptions (+ this warning)
            raise NotSupportedError

        # The SFDC database is connected as late as possible if only tests
        # are running. Some tests don't require a connection.
        if not getattr(settings, 'SF_LAZY_CONNECT', 'test' in sys.argv):  # TODO don't use argv
            self.make_session()

    # Methods close() and commit() can be safely ignored, because everything is
    # committed automatically and the REST API is stateless.

    # pylint:disable=no-self-use
    def close(self):
        pass

    def commit(self):
        pass

    def rollback(self):
        log.info("Rollback is not implemented.")

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


Connection = RawConnection


# DB API function
def connect(**params):
    return Connection(**params)


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


def rest_api_url(sf_session, service, *args):
    """Join the URL of REST_API

    Examples: rest_url(sf_session, "query?q=select+id+from+Organization")
              rest_url(sf_session, "sobject", "Contact", id)
    """
    return '{base}/services/data/v{version}/{service}{slash_args}'.format(
        base=sf_session.auth.instance_url,
        version=salesforce.API_VERSION,
        service=service,
        slash_args=''.join('/' + x for x in args)
    )


def handle_api_exceptions(url, session_method, *args, **kwargs):
    """Call REST API and handle exceptions
    Params:
        session_method:  requests.get or requests.post...
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
        response = session_method(url, *args, **kwargs_in)
    # TODO some timeouts can be rarely raised as "SSLError: The read operation timed out"
    except requests.exceptions.Timeout:
        raise SalesforceError("Timeout, URL=%s" % url)
    if response.status_code == 401:  # Unauthorized
        # Reauthenticate and retry (expired or invalid session ID or OAuth)
        data = response.json()[0]
        if data['errorCode'] == 'INVALID_SESSION_ID':
            token = session_method.__self__.auth.reauthenticate()
            if 'headers' in kwargs:
                kwargs['headers'].update(dict(Authorization='OAuth %s' % token))
            try:
                response = session_method(url, *args, **kwargs_in)
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
    verbose = not getattr(getattr(_cursor, 'db', None), 'debug_silent', False)
    if 'json' not in response.headers.get('Content-Type', ''):
        raise OperationalError("HTTP error code %d: %s" % (response.status_code, response.text))
    # Other Errors are reported in the json body
    data = response.json()[0]
    if response.status_code == 404:  # ResourceNotFound
        if (session_method.__func__.__name__ == 'delete') and data['errorCode'] in (
                'ENTITY_IS_DELETED', 'INVALID_CROSS_REFERENCE_KEY'):
            # It is a delete command and the object is in trash bin or
            # completely deleted or it only could be a valid Id for this type
            # then is ignored similarly to delete by a classic database query:
            # DELETE FROM xy WHERE id = 'something_deleted_yet'
            return None
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
    raise SalesforceError('%s' % data, data, response, verbose)


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
