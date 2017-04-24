from django.db import connections, router
from salesforce.dbapi.exceptions import InterfaceError
import salesforce

try:
    import beatbox
    soap_enabled = True
except ImportError:
    beatbox = None
    soap_enabled = False


def get_soap_client(db_alias, client_class=None):
    """
    Create the SOAP client for the current user logged in the db_alias

    The default created client is "beatbox.PythonClient", but an
    alternative client is possible. (i.e. other subtype of beatbox.XMLClient)
    """
    if not beatbox:
        raise InterfaceError("To use SOAP API, you'll need to install the Beatbox package.")
    if client_class is None:
        client_class = beatbox.PythonClient
    soap_client = client_class()

    # authenticate
    connection = connections[db_alias]
    # verify the authenticated connection, because Beatbox can not refresh the token
    connection.sf_session.refresh_auth(connection)
    auth_info = connections[db_alias].sf_session.auth

    access_token = auth_info.get_auth()['access_token']
    assert access_token[15] == '!'
    org_id = access_token[:15]
    url = '/services/Soap/u/{version}/{org_id}'.format(version=salesforce.API_VERSION,
                                                       org_id=org_id)
    soap_client.useSession(access_token, auth_info.instance_url + url)
    return soap_client


def get_db_for_model(model, op_type=None):
    if op_type in ('r', None):
        db_for_read = router.db_for_read(model)
    if op_type in ('w', None):
        db_for_write = router.db_for_read(model)
    if op_type is None and db_for_read != db_for_write:
        raise InterfaceError("The database for read and write should be the same "
                             "if the operation read or write is not specified")
    return db_for_read if op_type != 'w' else db_for_write
