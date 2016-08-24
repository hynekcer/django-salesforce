Help for some Error Messages
----------------------------

**Q:** `"...Error: Table 'my_sfdc_application.SomeTable' doesn't exist"` is reported on a line in program file like "...sqlite...", "...postgres..." or "...mysql...".

* Missed to set `DATABASE_ROUTERS = ["salesforce.router.ModelRouter"]` in your `settings.py` and therefore the "default" database is used instead of "salesforce"
* Missed to use the base class `salesforce.models.Model` instead of `django.db.models.Model` in that your model class.  
  
  
**Q:** `SalesforceError: {'errorCode': 'INVALID_TYPE', 'message': "... FROM SomeSObject ...`  
  `sObject type 'SomeSObject' is not supported. ..."`

* Typo in the `db_table` name that doesn't equal to object's `API Name` in Salesforce (e.g. missing "__c").  
* The current user's permissions are insufficient for this sObject type. Some fields created by installed packages or by API calls can be set without permissions even for the System Administrator profile if he doesn't add permission himself.

**Q:** `SalesforceError: {'errorCode': 'INVALID_OPERATION_WITH_EXPIRED_PASSWORD', 'message': "The users password has expired, you must call SetPassword before attempting any other API operations"}`

* The message is clear. If you use the Django service with a fixed user and password authentication, consider to set a separate user profile for that user with a password policy that never expires.
Setup / Administer / Manage users / Profiles,
Select the current user profile, click "Clone" (new name), to be cloned, click "Password Policies", edit "User passwords expire in" - "never expires". Assign the profile.