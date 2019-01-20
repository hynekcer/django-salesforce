# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Salesforce object query and queryset customizations.  (like django.db.models.query)
"""

from __future__ import print_function

from django.core.serializers import python
from django.db import connections
from django.db.models import query
from django.db.models.sql.datastructures import EmptyResultSet

from salesforce.backend import DJANGO_20_PLUS
from salesforce.backend.utils import CursorWrapper, prep_for_deserialize
from salesforce.backend.compiler import SQLCompiler


# pylint:disable=too-few-public-methods
class SalesforceRawQuerySet(query.RawQuerySet):
    def __len__(self):
        if self.query.cursor is None:
            # force the query
            self.query.get_columns()
        return self.query.cursor.rowcount


class SalesforceModelIterable(query.BaseIterable):
    """
    Iterable that yields a model instance for each row.
    """

    def __iter__(self):
        """
        An iterator over the results from applying this QuerySet to the
        remote web service.
        """
        # pylint:disable=protected-access,too-many-locals
        queryset = self.queryset
        try:
            sql, params = SQLCompiler(queryset.query, connections[queryset.db], None).as_sql()
        except EmptyResultSet:
            # StopIteration
            return
        cursor = CursorWrapper(connections[queryset.db], queryset.query)
        cursor.execute(sql, params)

        only_load = queryset.query.get_loaded_field_names()
        load_fields = []
        # If only/defer clauses have been specified,
        # build the list of fields that are to be loaded.
        if not only_load:
            model_cls = queryset.model
            init_list = None
        else:
            fields = queryset.model._meta.concrete_fields
            for field in fields:
                model = field.model._meta.concrete_model
                if model is None:
                    model = queryset.model
                try:
                    if field.attname in only_load[model]:
                        # Add a field that has been explicitly included
                        load_fields.append(field.name)
                except KeyError:
                    # Model wasn't explicitly listed in the only_load table
                    # Therefore, we need to load all fields from this model
                    load_fields.append(field.name)

            init_list = []
            skip = set()
            for field in fields:
                if field.name not in load_fields:
                    skip.add(field.attname)
                else:
                    init_list.append(field.name)
            model_cls = queryset.model

        field_names = queryset.query.get_loaded_field_names()
        _ = field_names  # NOQA
        for res in python.Deserializer(
                x for x in
                (prep_for_deserialize(model_cls, r, queryset.db, init_list)
                 for r in cursor.results
                 )
                if x is not None
        ):
            # Store the source database of the object
            res.object._state.db = queryset.db
            # This object came from the database; it's not being added.
            res.object._state.adding = False

            if init_list is not None and len(init_list) != len(model_cls._meta.concrete_fields):
                raise NotImplementedError("methods defer() and only() are not implemented for Django 1.10 yet")

            yield res.object


class SalesforceQuerySet(query.QuerySet):
    """
    Use a custom SQL compiler to generate SOQL-compliant queries.
    """

    def __init__(self, *args, **kwargs):
        super(SalesforceQuerySet, self).__init__(*args, **kwargs)
        self._iterable_class = SalesforceModelIterable

    def iterator(self, chunk_size=2000):
        """
        An iterator over the results from applying this QuerySet to the
        database.
        """
        return iter(self._iterable_class(self))

    def query_all(self):
        """
        Allows querying for also deleted or merged records.
            Lead.objects.query_all().filter(IsDeleted=True,...)
        https://www.salesforce.com/us/developer/docs/api_rest/Content/resources_queryall.htm
        """
        if DJANGO_20_PLUS:
            obj = self._clone()
        else:
            obj = self._clone(klass=SalesforceQuerySet)  # pylint: disable=unexpected-keyword-arg
        obj.query.set_query_all()
        return obj

    def simple_select_related(self, *fields):
        """
        Simplified "select_related" for Salesforce

        Example:
            for x in Contact.objects.filter(...).order_by('id')[10:20].simple_select_related('account'):
                print(x.name, x.account.name)
        Restrictions:
            * This must be the last method in the queryset method chain, after every other
              method, after a possible slice etc. as you see above.
            * Fields must be explicitely specified. Universal caching of all related
              without arguments is not implemented (because it could be inefficient and
              complicated if some of them should be deferred)
        """
        if not fields:
            raise Exception("Fields must be specified in 'simple_select_related' call, otherwise it wol")
        for rel_field in fields:
            rel_model = self.model._meta.get_field(rel_field).related_model
            rel_attr = self.model._meta.get_field(rel_field).attname
            rel_qs = rel_model.objects.filter(pk__in=self.values_list(rel_attr, flat=True))
            fk_map = {x.pk: x for x in rel_qs}
            for x in self:
                rel_fk = getattr(x, rel_attr)
                if rel_fk:
                    setattr(x, '_{}_cache'.format(rel_field), fk_map[rel_fk])
        return self
