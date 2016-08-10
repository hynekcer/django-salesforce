# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Salesforce object manager.

Use a custom QuerySet to generate SOQL queries and results.
"""

from django.conf import settings
from django.db.models import manager
from django.db.utils import DEFAULT_DB_ALIAS

from salesforce import router


class SalesforceManager(manager.Manager):
    use_for_related_fields = True

    def get_queryset(self):
        """
        Returns a QuerySet which access remote SF objects.
        """
        if not router.is_sf_database(self.db):
            return super(SalesforceManager, self).get_queryset()
        else:
            from salesforce.backend.sql_query import SalesforceQuery
            from salesforce.backend.query import SalesforceQuerySet
            from salesforce.backend.compiler import SalesforceWhereNode
            q = SalesforceQuery(self.model, where=SalesforceWhereNode)
            return SalesforceQuerySet(self.model, query=q, using=self.db)

    def using(self, alias):
        if alias is None:
            if getattr(self.model, '_salesforce_object', False):
                alias = getattr(settings, 'SALESFORCE_DB_ALIAS', 'salesforce')
            else:
                alias = DEFAULT_DB_ALIAS
        return self.get_queryset().using(alias)

    def raw(self, raw_query, params=None, *args, **kwargs):
        if router.is_sf_database(self.db):
            from salesforce.backend import query
            q = query.SalesforceRawQuery(raw_query, self.db, params)
            return query.SalesforceRawQuerySet(raw_query=raw_query, model=self.model, query=q,
                                               params=params, using=self.db)
        else:
            return super(SalesforceManager, self).raw(raw_query, params, *args, **kwargs)

    def query_all(self):
        if router.is_sf_database(self.db):
            return self.get_queryset().query_all()
        else:
            return self.get_queryset()
