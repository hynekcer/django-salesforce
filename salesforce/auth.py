# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
oauth login support for the Salesforce API
"""

import base64
import hashlib
import hmac
import logging
import requests
import threading
from django.db import connections
from salesforce.backend import MAX_RETRIES
from salesforce.backend.driver import DatabaseError
from salesforce.backend.adapter import SslHttpAdapter
from requests.auth import AuthBase

# TODO hy: more advanced methods with ouathlib can be implemented, but
#      the simple doesn't require a special package.

log = logging.getLogger(__name__)

oauth_lock = threading.Lock()
# The static "oauth_data" is useful for efficient static authentication with
# multithread server, whereas the thread local data in connection.sf_session.auth
# are necessary if dynamic auth is used.
oauth_data = {}


class SalesforceAuth(AuthBase):
	"""
	Authentication object that encapsulates all auth settings and holds the auth token.

	It is sufficient to create a `connection` to SF data server instead of
	specific parameters for specific auth methods.

	required public methods:
        __ini__(db_alias, .. optional params, _session)  set what you think will be necessary
							A non-default `_session` for `requests` can be provided,
							especially for tests
		authenticate():		ask for a new token (customizable method)

		del_token():		forget token (both static and dynamic eventually)
	optional public (for your middleware)
		dynamic_start(access_token, instance_url):
							replace the static values by the dynamic
							(change the user and url dynamically)
		dynamic_end():		restore the previous static values
	private:
		get_token():		get a token and url saved here or ask for a new
		reauthenticate():	force to ask for a new token if allowed (for
							permanent authentication) (used after expired token error)
	callback for requests:
		__call__(r)

	An instance of this class can be supplied to the SF database backend connectin
	in order to customize default authentication. It will be saved to
		`connections['salesforce'].sf_session.auth`

		Use it typically at the beginning of Django request in your middleware by:
			connections['salesforce'].sf_session.auth.dynamic_start(access_token)

	http://docs.python-requests.org/en/latest/user/advanced/#custom-authentication
	"""

	def __init__(self, db_alias, settings_dict=None, _session=None):
		"""
		Set values for authentication
			Params:
				db_alias:  The database alias e.g. the default SF alias 'salesforce'.
				settings_dict: It is only important for the first connection.
						Should be taken from django.conf.DATABASES['salesforce'],
						because it is not known in connection.settings_dict initially.
				_session: only for tests
		"""
		self.db_alias = db_alias
		self.dynamic = None
		self.settings_dict = settings_dict or connections[db_alias].settings_dict
		self._session = _session or requests.Session()

	def authenticate(self):
		"""
		Authenticate to the Salesforce API with the provided credentials.

		This function will be called only if it is not in the cache.
		"""
		raise NotImplementedError("The authenticate method should be subclassed.")

	def get_auth(self):
		"""
		Cached value of authenticate() + the logic for the dynamic auth
		"""
		if self.dynamic:
			return self.dynamic
		elif self.settings_dict['USER'] == 'dynamic auth':
			return {'instance_url': self.settings_dict['HOST']}
		else:
			db_alias = self.db_alias
			with oauth_lock:
				if not db_alias in oauth_data:
					oauth_data[db_alias] = self.authenticate()
				return oauth_data[db_alias]

	def del_token(self):
		with oauth_lock:
			del oauth_data[self.db_alias]
		self.dynamic = None

	def __call__(self, r):
		"""Standard auth hook on the "requests" request r"""
		access_token = str(self.get_auth()['access_token'])
		r.headers['Authorization'] = 'OAuth %s' % access_token
		return r

	def reauthenticate(self):
		if self.dynamic is None:
			self.del_token()
			return str(self.get_auth()['access_token'])
		else:
			# It is expected that with dynamic authentication we get a token that
			# is valid at least for a few future seconds, because we don't get
			# any password or permanent permission for it from the user.
			raise DatabaseError("Dynamically authenticated connection can never reauthenticate.")

	@property
	def instance_url(self):
		return self.get_auth()['instance_url']

	def dynamic_start(self, access_token, instance_url=None):
		"""
		Set the access token dynamically according to the current user.
		"""
		self.dynamic = {'access_token': access_token, 'instance_url': instance_url}

	def dynamic_end(self):
		"""
		Clear the dynamic access token.
		"""
		self.dynamic = None


class SalesforcePasswordAuth(SalesforceAuth):
	"""
	Attaches OAuth 2 Salesforce Password authentication to the `requests` Session

	Static auth data are cached thread safe between threads.
	"""
	def authenticate(self):
		"""
		Authenticate to the Salesforce API with the provided credentials (password).
		"""
		# if another thread is in this method, wait for it to finish.
		# always release the lock no matter what happens in the block
		settings_dict = self.settings_dict
		url = ''.join([settings_dict['HOST'], '/services/oauth2/token'])

		log.info("attempting authentication to %s" % settings_dict['HOST'])
		self._session.mount(settings_dict['HOST'], SslHttpAdapter(max_retries=MAX_RETRIES))
		response = self._session.post(url, data=dict(
			grant_type		= 'password',
			client_id		= settings_dict['CONSUMER_KEY'],
			client_secret	= settings_dict['CONSUMER_SECRET'],
			username		= settings_dict['USER'],
			password		= settings_dict['PASSWORD'],
		))
		if response.status_code == 200:
			response_data = response.json()
			# Verify signature (not important for this auth mechanism)
			calc_signature = (base64.b64encode(hmac.new(
					key=settings_dict['CONSUMER_SECRET'].encode('ascii'),
					msg=(response_data['id'] + response_data['issued_at']).encode('ascii'),
					digestmod=hashlib.sha256).digest())).decode('ascii')
			if calc_signature == response_data['signature']:
				log.info("successfully authenticated %s" % settings_dict['USER'])
			else:
				raise RuntimeError('Invalid auth signature received')
		else:
			raise LookupError("oauth failed: %s: %s" % (settings_dict['USER'], response.text))
		return response_data
