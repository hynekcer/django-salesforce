from salesforce.testrunner.settings import *  # NOQA
from salesforce.testrunner.settings import LOGGING, INSTALLED_APPS

del LOGGING['handlers']['mail_admins']
del LOGGING['loggers']['django.request']

INSTALLED_APPS += (
    'salesforce.tests.custom',
)
