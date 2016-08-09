# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Database backend for the Salesforce API.

No code in this directory is used with standard databases, even if a standard
database is used for running some application tests on objects defined by
SalesforceModel. All code for SF models that can be used with non SF databases
should be located directly in the 'salesforce' directory in files 'models.py',
'fields.py', 'manager.py', 'router.py', 'admin.py'.

All code here in salesforce.backend is private without public API. (It can be
changed anytime between versions.)

structure:
    salesforce/*.py - what the user can/should use instead of standard
        django.db classes in his app and settings
    salesforce/backend/*.py - what is private,
        equivalent to django.db.backend.some_backend
    salesforce/dbapi/*.py - database driver is independent on Django

Incorrectly located files: (It is better not to change it now.)
    backend/manager.py   => manager.py
    auth.py              => backend/auth.py
"""
