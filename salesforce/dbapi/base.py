"""Base of REST API and SOAP API for Force.com (Salesforce)

"""
from collections import namedtuple
from requests import Session
from datetime import timedelta
import datetime
import pytz

# The worst shortest expected configurable session timeout is 15 minutes.
AUTH_SESSION_TIMEOUT = 900
# It controls here whether the validity of authentication token
# should be checked before request or is guaranted. SFDC declares that
# the session timer is updated if a new request comes after
# AUTH_SESSION_TIMEOUT / 2 seconds. Practically it is updated sooner, if
# the new request comes to Salesforce later than 300 seconds after the
# previous update.

# Safety margin for unexpected events like network delay, invalid clock etc.
AUTH_MARGIN_TIME = 180

RequestTimestamps = namedtuple("RequestTimestamps", ["start", "end", "sfdc"])


def parse_rfc_2616(timestamp_string):
    """Parse RFC 2616 timestamp from HTTP headers
    >>> parse_rfc_2616('Tue, 13 Sep 2016 15:34:51 GMT')
    datetime.datetime(2016, 9, 13, 15, 34, 51, tzinfo=<UTC>)
    """
    RFC_2616_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'
    timestamp = datetime.datetime.strptime(timestamp_string, RFC_2616_FORMAT)
    return timestamp.replace(tzinfo=pytz.utc)


def utcnow_tz():
    return datetime.datetime.utcnow().replace(tzinfo=pytz.utc)


class SessionEncap(Session):
    """
    Encapsulated authenticated requests session.
    """
    def __init__(self):
        super(SessionEncap, self).__init__()
        # "last_timestamps" is updated after authenticated requests
        # not after authentication errors or after network errors.
        self.last_timestamps = None

    def request(self, method, url, *args, **kwargs):
        start = utcnow_tz()
        response = super(SessionEncap, self).request(method, url, *args, **kwargs)
        if response.status_code < 400:  # not 401 "Unathorized"
            end = utcnow_tz()
            sfdc_time = parse_rfc_2616(response.headers['Date'])
            self.last_timestamps = RequestTimestamps(start=start, end=end, sfdc=sfdc_time)
        return response

    def refresh_auth(self, connection):
        """
        Check authentication whether the token can be expired or try it
        by a request that eventually can re-authenticate
        Parameter: connection (because we have a re-auth code for
                a connection not for a session)
        """
        # The authentication is verified before running the request if
        # a valid (not expired) session is not guaranteed.
        # It is counted with a safety margin for network delays. The prepared
        # request could be delayed by double value
        # of the preset timeout before it comes to SFDC in the worst case.
        if getattr(self.auth, 'can_reauthenticate', False):
            auth_guaranteed_until = []
            auth_issued_at = self.auth.auth_issued_at()
            if auth_issued_at:
                auth_guaranteed_until.append(auth_issued_at
                                             + timedelta(seconds=AUTH_SESSION_TIMEOUT))
            if self.last_timestamps:
                auth_guaranteed_until.append(self.last_timestamps.start
                                             + timedelta(seconds=AUTH_SESSION_TIMEOUT / 2))
            if not auth_guaranteed_until or utcnow_tz() > (max(auth_guaranteed_until)
                                                           - timedelta(seconds=AUTH_MARGIN_TIME)):
                connection.cursor().urls_request()


# Introspection info
# More info by query:
#     SELECT Id, CreatedDate, LastModifiedDate, LoginType, NumSecondsValid,
#            SessionSecurityLevel, SessionType, SourceIp, UsersId, UserType
#     FROM AuthSession

# Useless details about the connection
#    >>> cursor = connections['salesforce'].cursor()
#    >>> adapter = list(cursor.session.adapters.values())[0]
#    >>> pool = list(adapter.poolmanager.pools._container.values())[0]
#    >>> socket = pool.pool.queue[-1].sock
#    >>> socket
#    ... <ssl.SSLSocket fd=4, family=AddressFamily.AF_INET, type=2049, proto=6,
#    ...         laddr=('192.168.1.11', 50434), raddr=('96.43.145.32', 443)>
#    >>> socket._connected
#    ... True  # not important on broken connections, but missing remote
#    >>> socket._sslobj.version()
#    ... 'TLSv1.2'
#    >>> socket_sslobj.cipher()
#    ... ('AES256-GCM-SHA384', 'TLSv1/SSLv3', 256)
#    >>> socket
#    >>> socket
#    >>> pool.pool.queue[-1]._HTTPConnection__response.msg._headers
#    ... [('Date', 'Wed, 14 Sep 2016 09:33:22 GMT'),
#    ...  ('Sforce-Limit-Info', 'api-usage=20/5000000'),...]
#
#     OSError
#       ConnectionError
#         BrokenPipeError
#         ConnectionAbortedError  # possible?
#         ConnectionRefusedError  # possible?
#         ConnectionResetError
#       TimeoutError
#       requests.exceptions.ConnectionError   (IOError == OSError)
