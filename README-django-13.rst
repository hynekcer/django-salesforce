Support for Django 1.3
======================

The necessary code for Django 1.3 has been backported into branch `hynekcer/django13`
starting in very recent code, with necessary fixes, in order to support some old
project. Sometimes it will be merged with recent changes.

Known Restrictions
------------------

Proxy models require to specify 'db_table' attribute explicitely in Meta.

Database introspection (inspectdb) is not tested for Django 1.3 because
SFDC can be exported on a development machine with a new Django.

Django 1.3 doesn't support bulk operations (bulk_create).
