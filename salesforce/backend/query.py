# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Salesforce object query and queryset customizations.
"""
# TODO hynekcer: class CursorWrapper should
#      be moved to salesforce.dbapi.driver at the next big refactoring
#      (Evenso some low level internals of salesforce.auth should be moved to
#      salesforce.dbapi.driver.Connection)

from __future__ import print_function
import datetime
import pytz

from django.conf import settings
from django.core.serializers import python
from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.db.models import query
from django.db.models.sql.datastructures import EmptyResultSet

from salesforce import DJANGO_110_PLUS
from salesforce.dbapi.driver import DatabaseError   , CursorWrapper
from salesforce.backend.compiler import SQLCompiler
from salesforce.fields import SF_PK

if not DJANGO_110_PLUS:
    from django.db.models.query_utils import deferred_class_factory


# Values of seconds are with 3 decimal places in SF, but they are rounded to
# whole seconds for the most of fields.
SALESFORCE_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%f+0000'
DJANGO_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f-00:00'


def prep_for_deserialize_inner(model, record, init_list=None):
    fields = dict()
    for x in model._meta.fields:
        if not x.primary_key and (not init_list or x.name in init_list):
            if x.column.endswith('.Type'):
                # Type of generic foreign key
                simple_column, _ = x.column.split('.')
                fields[x.name] = record[simple_column]['Type']
            else:
                # Normal fields
                if not x.column in record:
                    import pdb; pdb.set_trace()
                field_val = record[x.column]
                # db_type = x.db_type(connection=connections[using])
                if(x.__class__.__name__ == 'DateTimeField' and field_val is not None):
                    d = datetime.datetime.strptime(field_val, SALESFORCE_DATETIME_FORMAT)
                    d = d.replace(tzinfo=pytz.utc)
                    if settings.USE_TZ:
                        fields[x.name] = d.strftime(DJANGO_DATETIME_FORMAT)
                    else:
                        tz = pytz.timezone(settings.TIME_ZONE)
                        d = tz.normalize(d.astimezone(tz))
                        fields[x.name] = d.strftime(DJANGO_DATETIME_FORMAT[:-6])
                else:
                    fields[x.name] = field_val
    return fields


def prep_for_deserialize(model, record, using, init_list=None):
    """
    Convert a record from SFDC (decoded JSON) to dict(model string, pk, fields)
    If fixes fields of some types. If names of required fields `init_list `are
    specified, then only these fields are processed.
    """
    # TODO the parameter 'using' is not currently important.
    attribs = record.pop('attributes')  # NOQA unused

    mod = model.__module__.split('.')
    if(mod[-1] == 'models'):
        app_label = mod[-2]
    elif(hasattr(model._meta, 'app_label')):
        app_label = getattr(model._meta, 'app_label')
    else:
        raise ImproperlyConfigured("Can't discover the app_label for %s, you must specify it via model meta options.")

    if len(record.keys()) == 1 and model._meta.db_table in record:
        # this is for objects with ManyToManyField and OneToOneField
        while len(record) == 1:
            record = list(record.values())[0]
            if record is None:
                return None

    fields = prep_for_deserialize_inner(model, record, init_list=init_list)

    if init_list and set(init_list).difference(fields).difference([SF_PK]):
        raise DatabaseError("Not found some expected fields")

    return dict(
        model='.'.join([app_label, model.__name__]),
        pk=record.pop('Id'),
        fields=fields,
    )


class SalesforceRawQuerySet(query.RawQuerySet):
    def __len__(self):
        if self.query.cursor is None:
            # force the query
            self.query.get_columns()
        return self.query.cursor.rowcount


class SalesforceQuerySet(query.QuerySet):
    """
    Use a custom SQL compiler to generate SOQL-compliant queries.
    """
    def iterator(self):
        """
        An iterator over the results from applying this QuerySet to the
        remote web service.
        """
        try:
            sql, params = SQLCompiler(self.query, connections[self.db], None).as_sql()
        except EmptyResultSet:
            raise StopIteration
        cursor = CursorWrapper(connections[self.db], self.query)
        cursor.execute(sql, params)

        # TODO this is different for Django 1.10
        only_load = self.query.get_loaded_field_names()
        load_fields = []
        # If only/defer clauses have been specified,
        # build the list of fields that are to be loaded.
        if not only_load:
            model_cls = self.model
            init_list = None
        else:
            fields = self.model._meta.concrete_fields
            for field in fields:
                model = field.model._meta.concrete_model
                if model is None:
                    model = self.model
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
            if DJANGO_110_PLUS:
                model_cls = self.model
            else:
                model_cls = deferred_class_factory(self.model, skip)

        field_names = self.query.get_loaded_field_names()
        _ = field_names  # NOQA
        for res in python.Deserializer(
            (x for x in (prep_for_deserialize(model_cls, r, self.db, init_list)
                         for r in cursor.results
                         ) if x is not None
             ), using=self.db
        ):
            # Store the source database of the object
            res.object._state.db = self.db
            # This object came from the database; it's not being added.
            res.object._state.adding = False

            if DJANGO_110_PLUS and init_list is not None and len(init_list) != len(model_cls._meta.concrete_fields):
                pass  # TODO
                # raise NotImplementedError("methods defer() and only() are not implemented for Django 1.10 yet")

            yield res.object

    def query_all(self):
        """
        Allows querying for also deleted or merged records.
            Lead.objects.query_all().filter(IsDeleted=True,...)
        https://www.salesforce.com/us/developer/docs/api_rest/Content/resources_queryall.htm
        """
        obj = self._clone(klass=SalesforceQuerySet)
        obj.query.set_query_all()
        return obj
