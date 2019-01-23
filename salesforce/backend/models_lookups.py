"""
Lookups  (like django.db.models.lookups, django.db.models.aggregates.Count)
"""
# pylint:disable=no-else-return
from django.db import models
import django.db.models.aggregates


class IsNull(models.lookups.IsNull):
    # The expected result base class above is `models.lookups.IsNull`.
    lookup_name = 'isnull'

    def as_sql(self, compiler, connection):
        if connection.vendor == 'salesforce':
            sql, params = compiler.compile(self.lhs)
            return ('%s %s null' % (sql, ('=' if self.rhs else '!='))), params
        else:
            return super(IsNull, self).as_sql(compiler, connection)


models.Field.register_lookup(IsNull)


class Range(models.lookups.Range):
    # The expected result base class above is `models.lookups.Range`.
    lookup_name = 'range'

    def as_sql(self, compiler, connection):
        if connection.vendor == 'salesforce':
            lhs, lhs_params = self.process_lhs(compiler, connection)
            rhs, rhs_params = self.process_rhs(compiler, connection)
            assert tuple(rhs) == ('%s', '%s')  # tuple in Django 1.11+, list in old Django
            assert len(rhs_params) == 2
            params = lhs_params + [rhs_params[0]] + lhs_params + [rhs_params[1]]
            # The symbolic parameters %s are again substituted by %s. The real
            # parameters will be passed finally directly to CursorWrapper.execute
            return '(%s >= %s AND %s <= %s)' % (lhs, rhs[0], lhs, rhs[1]), params
        else:
            return super(Range, self).as_sql(compiler, connection)


models.Field.register_lookup(Range)


def count_as_salesforce(self, *args, **kwargs):
    if (len(self.source_expressions) == 1 and
            isinstance(self.source_expressions[0], models.expressions.Value) and
            self.source_expressions[0].value == '*'):
        return 'COUNT(Id)', []
    else:
        # tmp = Count('pk')
        # args[0].query.add_annotation(Count('pk'), alias='__count', is_summary=True)
        # obj.add_annotation(Count('*'), alias='__count', is_summary=True
        # self.source_expressions[0] = models.expressions.Col('__count', args[0].query.model._meta.fields[0])  #'Id'
        return self.as_sql(*args, **kwargs)


setattr(django.db.models.aggregates.Count, 'as_salesforce', count_as_salesforce)
