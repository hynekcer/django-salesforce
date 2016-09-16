# django-salesforce

"""
A set of tools to deal with Salesforce actions that
cannot or can hardly be implemented using the generic
relational database abstraction.

The Salesforce REST API is missing a few endpoints that
are available in the SOAP API. We are using `beatbox` as
a workaround for those specific actions (such as Lead-Contact
conversion).
"""

from django.db import connections
from salesforce.dbapi.exceptions import DatabaseError, InterfaceError
from salesforce.dbapi.soap import soap_enabled, get_soap_client
import salesforce


def convert_lead(lead, converted_status=None, **kwargs):
    """
    Convert `lead` using the `convertLead()` endpoint exposed
    by the SOAP API.

    Parameters:
    `lead` -- a Lead object that has not been converted yet.
    `converted_status` -- valid LeadStatus value for a converted lead.
        Not necessary if only one converted status is configured for Leads.

    kwargs: additional optional parameters according docs
    https://developer.salesforce.com/docs/atlas.en-us.api.meta/api/sforce_api_calls_convertlead.htm
    e.g. `accountId` if the Lead should be merged with an existing Account.

    Return value:
        {'accountId':.., 'contactId':.., 'leadId':.., 'opportunityId':.., 'success':..}

    -- BEWARE --
    The current implementation won't work in case your `Contact`,
    `Account` or `Opportunity` objects have some custom **and**
    required fields. This arises from the fact that `convertLead()`
    is only meant to deal with standard Salesforce fields, so it does
    not really care about populating custom fields at insert time.

    One workaround is to map a custom required field in
    your `Lead` object to every custom required field in the target
    objects (i.e., `Contact`, `Opportunity` or `Account`). Follow the
    instructions at

    https://help.salesforce.com/apex/HTViewHelpDoc?id=customize_mapleads.htm

    for more details.
    """
    if not soap_enabled:
        raise InterfaceError("To use convert_lead, you'll need to install the Beatbox library.")

    accepted_kw = set(('accountId', 'contactId', 'doNotCreateOpportunity',
                       'opportunityName', 'overwriteLeadSource', 'ownerId',
                       'sendNotificationEmail'))
    assert all(x in accepted_kw for x in kwargs)

    db_alias = lead._state.db
    if converted_status is None:
        converted_status = connections[db_alias].introspection.converted_lead_status
    soap_client = get_soap_client(db_alias)

    # convert
    kwargs['leadId'] = lead.pk
    kwargs['convertedStatus'] = converted_status
    response = soap_client.convertLead(kwargs)

    ret = dict((x._name[1], str(x)) for x in response)

    if "errors" in str(ret):
        raise DatabaseError("The Lead conversion failed: {0}, leadId={1}".format(
                            ret['errors'], ret['leadId']))

    return ret


def set_highest_api_version(db_aliases):
    """Set the highest version of Force.com API supported by all databases in db_aliases
    """
    from salesforce.backend.query import CursorWrapper
    if not isinstance(db_aliases, (list, tuple)):
        db_aliases = [db_aliases]
    max_version = max(CursorWrapper(connections[db_alias]).versions_request()[-1]['version']
                      for db_alias in db_aliases)
    setattr(salesforce, 'API_VERSION', max_version)
