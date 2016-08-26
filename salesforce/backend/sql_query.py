"""Customized descentants of django.db.models.sql.query"""
from django.db import connections
from django.db.models import Count
from django.db.models.sql import Query, RawQuery, constants

from salesforce.dbapi.driver import CursorWrapper


class SalesforceRawQuery(RawQuery):
    def clone(self, using):
        return SalesforceRawQuery(self.sql, using, params=self.params)

    def get_columns(self):
        if self.cursor is None:
            self._execute_query()
        converter = connections[self.using].introspection.table_name_converter
        if self.cursor.rowcount > 0:
            return [converter(col) for col in self.cursor.first_row.keys() if col != 'attributes']
        # TODO hy: A more general fix is desirable with rewriting more code.
        return ['Id']  # originally [SF_PK] before Django 1.8.4

    def _execute_query(self):
        self.cursor = CursorWrapper(connections[self.using], self)
        self.cursor.execute(self.sql, self.params)

    def __repr__(self):
        return "<SalesforceRawQuery: %s; %r>" % (self.sql, tuple(self.params))

    def __iter__(self):
        # import pdb; pdb.set_trace()
        for row in super(SalesforceRawQuery, self).__iter__():
            yield [row[k] for k in self.get_columns()]


class SalesforceQuery(Query):
    """
    Override aggregates.
    """
    def __init__(self, *args, **kwargs):
        super(SalesforceQuery, self).__init__(*args, **kwargs)
        self.is_query_all = False
        self.first_chunk_len = None
        self.max_depth = 1

    def clone(self, klass=None, memo=None, **kwargs):
        query = Query.clone(self, klass, memo, **kwargs)
        query.is_query_all = self.is_query_all
        return query

    def has_results(self, using):
        q = self.clone()
        compiler = q.get_compiler(using=using)
        return bool(compiler.execute_sql(constants.SINGLE))

    def set_query_all(self):
        self.is_query_all = True

    def get_count(self, using):
        """
        Performs a COUNT() query using the current filter constraints.
        """
        obj = self.clone()
        obj.add_annotation(Count('pk'), alias='x_sf_count', is_summary=True)
        number = obj.get_aggregation(using, ['x_sf_count'])['x_sf_count']
        if number is None:
            number = 0
        return number
