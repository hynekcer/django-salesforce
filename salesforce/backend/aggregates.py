# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Aggregates like COUNT(), MAX(), MIN() are customized here.
"""
from django.db.models.aggregates import *  # NOQA
import django.db.models.aggregates


class Count(django.db.models.aggregates.Count):
    """
    A customized Count class that supports COUNT_DISTINCT(field_name).
    """
    def as_salesforce(self, compiler, connection):
        sql, params = super(Count, self).as_sql(compiler, connection)
        if self.extra['distinct']:
            sql = sql.replace('COUNT(DISTINCT ', 'COUNT_DISTINCT(')
        if '(*)' in sql:
            sql = sql.replace('(*)', '()')
        return sql, params
