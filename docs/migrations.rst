Migrations
==========

new in v5.1.1.

Migrations are now supported in Salesforce databases on SFDC servers.
The command ``python manage.py migrate --database=salesforce`` can
create, update, rename or delete custom models and custom fields.
For security reasons it is possible only if they were previously enabled in
a particular SFDC database. Then it is possible to fine control by the model
which custom objects and custom fields can be managed by django-salesforce
and which should remain untouched.
The migrate command works with all Python and Django versions supported by django-salesforce.
It is however recommended to use versions supported by mainstream or at least
Django >= 4.2 and Python >= 3.8. The licence policy is the same as for django-salesforce
used with the newest version of Django.


Quick start
...........

.. code:: shell

    # before running an initial migration in a new Salesforce database
    python manage.py migrate --database=salesforce --sf-create-permission-set

Then add some custom objects (models) to Salesforce and some custom fields.
As a small example you might want to add a custom field to a standard object "Contact"
and to create two custom objects by a migration:

``models.py``:

.. code:: python

    class Contact(SalesforceModel):
        # Add a custom field "my_field" to a standard object "Contact"
        last_name = models.CharField(max_length=50)
        my_field = models.CharField(max_length=50, null=True, sf_managed=True)

    class MyObject(SalesforceModel):
        # A field with API name "Name" is created automatically by SFDC.
        # You set its verbose name. Its "max_length" is ignored.
        name = models.CharField(max_length=50, verbose_name="My Object Name")
        my_field = models.CharField(max_length=50, null=True)  # this is a custom field and it is sf_managed

        class Meta:
            sf_managed = True
            # db_table = MyObject__c

    class OtherObject2(SalesforceModel):
        # Here you prefer an automatic read only name field in the style "A-{0000}"
        name = models.CharField(max_length=50, sf_read_only=models.READ_ONLY)
        ...

        class Meta:
            sf_managed = True
            # db_table = OtherObject2__c

Add this change to Salesforce:

.. code:: shell

    # before the first managed migration on the database create a permission set "Django_Salesforce".
    python manage.py migrate --database=salesforce --sf-create-permission-set

    # then for every migration
    python manage.py makemigrations
    python manage.py migrate --database=salesforce


More advanced
.............

This simple method of operation works well on a new empty development Salesforce instance,
but even with a sandbox created from an existing production database a more complicated
workflow is desiarable.
A general practice with Salesforce is that more software packages made by different vendors are installed
by the organization. Not all custom objects or custom fields should be therefore managed by Django.

An extended version of ``migrate`` command is installed by django-salesforce. Four new options are added by it.
``--sf-create-permission-set``, ``--sf-debug-info``, ``--sf-interactive``, ``--sf-no-check-permissions``.
These options are checked only for databases on salesforce.com (SFDC) and are ignored for other databases.

| Here is a detailed explanation that ``migrate`` command modifies SFDC only if:  
| A) if it is explicitly enabled in the Django model  
| B) and also it is enabled in Salesforce.com Setup  
| C) and additional conditions must be met on production databases.
|

**A\) How to enable migrations in Django model**

Custom object in Salesforce that should be created and managed by Django must use the Meta option: ``sf_managed = True``.

Custom fields can be created and managed also in objects not managed by Django if a field is marked
by a parameter ``sf_managed=True`` in a field definition. Custom fields in a sf_managed object do not
require a sf_managed parameter.

**B\) How to enable migrations also in Salesforce.com Setup.**

A basic security feature is that a permission set "Django_Salesforce" must exist in the database
before a ``migrate`` command is executed.
It can be created by the command
``python manage.py migrate --database=salesforce --sf-create-permission-set``
that also assigns that permission set to the current user.

A custom table can be deleted or renamed by Django only if it has been created by Django originally.
(More precisely: All possible object permissions are automatically enabled for a new Salesforce object
in "Django_Salesforce" Permission Set when the table is created by Django,
including "PermissionsModifyAllRecords". That is later verified before an object is deleted or renamed.)

A custom field can be modified or deleted by Django if at least one field has been created by Django
in that table or if the whole table can be modified by Django. (More precisely: The object permission
"PermissionsEdit" is assigned to a Salesforce
in "Django_Salesforce" Permission Set when a custom field is created by Django.
No field can be modified or deleted by Django in a table without this ObjectPermission. TODO discussion about it.)

At the end of development you may want to disable all migrations in the production database
e.g. by renaming the API Name of the permission set.

**C\) Security on production databases**

Another security feature is that all destructive operations (``delete_model`` and ``remove_field``)
are now interactively checked on production databases. Every delete must be confirmed like
if an option ``--sf-interactive`` was used, but no choice will be offered after any error and
the migration is always terminated (unlike '--sf-interactive' on sandboxes).

Troubleshooting
...............

Migrations are excellent in develomment especially if they are used since the beginning.
They can be problematic if management by Django has been combined with some manual
administration of the same objects or if an application should work on an existing database
and also on a new empty database.

You can create the initial migrations that reflect the initial stat of the database from
a model without any ``sf_managed=True``. The consequence is that these migrations will
be never reversed by Django

An option ``--sf-interactive`` allows to interactively skip
any individual part of a migration and eventually to continue if you are sure that
an error can be ignored (only on a sandbox),
e.g. if it failed because a duplicit object has beens created or an object should be deleted,
but it does not exist now.
It allows to normally terminate or to ignore an error or to start debugging.

.. code::

    $ python manage.py migrate --sf-interactive --database=salesforce ...

    Running migrations:
        Applying example.0001_initial...
    create_model(<model Test>)
    Run this command [Y/n]: n

The answer ``**migrate --fake** at Stackoverflow <https://stackoverflow.com/a/46774336/448474>``
can be useful how the migration state can be set if you know how many initial migrations were applied
manually on an instance before the migration system is enabled on it.

The option ``--sf-debug-info`` will print a short useful context about an error before raising an exception.
It is useful also in an interactive mode for a decision if the command should continue or to be terminated.

The option ``--sf-no-check-permissions`` disables the security mechanism B) about permission of
objects and fields. It is useful if the database contains no important data,
but the migration state is lost or out of sync and you want to go to an initial state and migrate again.
Then this combination of parameters could be useful:

.. code:: shell

   python manage.py migrate --database=salesforce my_application --sf-interactive --noinput --sf-no-check-permissions --sf-debug-info
   python manage.py migrate --database=salesforce my_application zero --sf-interactive --noinput --sf-no-check-permissions --sf-debug-info
   python manage.py migrate --database=salesforce my_application

The combination of ``--sf-interactive --noinput`` means that all question "Run this command?"
are answered "Y(es)" and all questions "Stop after this error?" are answered "c(ontinue)".
(The option '--noinput' is currently ignored but can be easily enabled by changin one


Reference
.........

| **Terminology**:  
| **Model** in Django terminology is an equivalent of **Table** in database terminology and equivalent to **Object** in Salesforce terminology. These three points of view are used in this text.  
|  
| **Builtin** object and builtin field have a name without any double underscore ``'__'``.  
| **Custom** object and custom field are in the form ``ApiName__c`` with only a suffix ``__c`` and without any other double underscore.  
| **Namespace** object and namespace field names are with two double underscores in the form ``NameSpace__ApiName__c``.  
|   
| Only custom objects or fields can be migrated, neither builtins nor namespace objects or fields.
| Because custom fields can be managed by Django automatically in SFDC and the algorithm
| of conversion a name to db_column is guaranteed stable then the db_column is not so important as before.  

| If no **db_column** is specified then it can be derived this way from "django field name":  
| Default API name from a lower case name is created by capitalizing and removing spaces:  
| If the django field name is not lower case then the default api name is equal.  
| e.g. default api name "LastModifiedDate" can be created from "last_modified_date" or from "LastModifiedDate".  
| Custom field can be recognized by "custom=True".  
| Namespace field can be recognized by "sf_prefix='NameSpacePrefix'".  
| All unspecified fields without "db_column" in custom objects are expected to be custom field,
| except a few standard well known system names like e.g. "LastModifiedDate" or its equivalent "last_modified_date".  
|  
| (If you find a new not recognized system name then specify an explicit "custom=False"
| or an explicit "db_column=..." and report that bug, but it is extremely unprobable because
| I verify all system names in a new API before I enable that API version in a new version of django-salesforce.)


All fields that can be managed by Django in SFDC are entirely explicitly identified in ``migrations/*.py``
by a parameter ``sf_managed=True``. The right value ``field.sf_managed`` can be usually derived correctly from a simple
model ``models.py`` with minimum of `sf_managed`` options:

- Custom fields in sf_managed custom object are sf_managed by default.
- Custom fields in non sf_managed objects are not sf_managed by default.
- Builtin fields and namespace fields and builtin objects and namespace objects should be never sf_managed.
  (It is a FieldError)
- The "Name" field (a field with db_column='Name') is a special part of a database Object and
  its sf_managed values is not important. Its ``sf_managed=`` should be omitted or it should be the same
  as the value of the object.

The table with a label "migrations" has a name "django_migrations__c" on SFDC. It is created by the first "migrate" command.

| 2) Custom object in Salesforce that should be created and managed by Django must use the Meta option: ``sf_managed = True``.
| Custom fields can be created also in objects not managed by Django if a field is marked by a parameter ``sf_managed=True``.

Custom fields in objects managed by Django are also managed by Django by default,
but it is possible to set a parameter ``sf_managed=False`` to disable it.

Objects and fields created by Django are enabled in Django_Salesforce permission set and can be
also modified and deleted by Django. If an existing sf_managed object is not enabled
in the pemission set then it is skipped with a warning and its settings can not be modified.

If you want to start to manage an object that has been created manually then enable all
Object Permissions for that object in "Django_Salesforce" permission set even if the field
is accessible still by user profiles.


Unimplemented features - caveats
................................

The implementation is kept simple until usefulness of migrations will be appreciated enough.

All migration operations are currently implemented without transactions and without
any optimization. Every field is processed by an individual command.

It is not possible to detect a separate change of ``Meta`` model options ``verbose_name`` or ``verbose_name_plural``.
You should change in the same migration also something unimportant in the ``Name`` field
of that model e.g. change the unused ``max_length`` parameter or add a space
at the end of ``verbose_name`` of Name field. That will trigger update of metadata of
the CustomObject in Salesforce.

Maybe a special NameField will be implemented, because it has a fixed option "null=False" ("required=True")
and special options "dataType", "displayFormat" and "startingNumber" not yet implemented. CharField
is good enough without them. Data type "Automatic Number" is derived from "sf_read_only=models.READ_ONLY",
otherwise the data type is "Text"

There is a risk that a field can not be created because e.g. a duplicit related name exist in trash bin
and also that a field can not be deleted because it is locked by something important in Salesforce.
That are usual problems also with manual administrations, but that could cause an inconsistent migration,
because transactions are not currently used. Therefore if you want to use migrations in production,
verify it, debug it on a sandbox, then create a fresh sandbox from production and verify the migration again.

Master-Detail Relationship is not currently implemented even that it is an important type.

All deleted objects and fields remain in a trash bin (renamed to prevent a name collision)
and they are not purged on delete.

Migrations work currently in a slow mode that modifies every field and every table individually.
That mode is useful for troubleshooting if some object is locked by something in a
Salesforce instance and that mode can be easily switched to an interactive mode.

A transactional mode should be however written where every migration will change correctly
all or nothing. That will be mostly necessary for use in production.

It is tested manually and no automatic test exist for migrations on SFDC.
