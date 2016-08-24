## Welcome to the django-salesforce wiki!

### Wiki Contents

- [Empty strings](Empty-strings) - How to exclude empty strings in queries etc.
- [Error messages](Error-messages) - How to understand some strange error messages
- [Experimental Features](Experimental-Features) - dynamic authentization, multiple SF databases with Admin
- [Foreign Key Support](Foreign-Key-Support) - queries based on fields of related tables, Many2Many relationships
- [Introspection and Special Attributes of Fields](Introspection-and-Special-Attributes-of-Fields) - How to understand the database model exported by inspectdb and how to exactly describe Salesforce by the the model.
- [SSL TLS settings and Saleforce.com](SSL-TLS-settings-and-Saleforce.com), but a better solution is to upgrade SSL/TLS system libraries and Python.

### Important issues
- [Tuning REQUESTS_MAX_RETRIES](https://github.com/django-salesforce/django-salesforce/issues/159) - A variable used in edge-cases that is difficult to describe, see this issue for more info.
- [Excluding Empty Strings](https://github.com/django-salesforce/django-salesforce/issues/143) - An issue that results from the leaky abstraction between Salesforce and an RDBMS.
- [Converting Leads](Introspection-and-Special-Attributes-of-Fields#soap-api) - Converting leads is not directly supported by the Salesforce REST interface, but an included helper function can use beatbox and the SOAP interface.

---
### Short notes

#### Field Naming Conventions
In both Django and Salesforce double underscores are significant, so to make custom fields work in Django, be sure to specify the `db_column` argument in the model field definition, i.e.
`Last_Login = models.DateTimeField(db_column='Last_Login__c',max_length=40)`

#### Faster tests
The tests can be slow with Django 1.7 and 1.8, if the `default` database has many migrations and some are applied and complex models for `salesforce` database are used, e.g. hundreds kB exported by inspectdb without pruning (`--table-filter=...`). This is fixed by Django 1.9 or many workarounds are described on the Internet for old Django.