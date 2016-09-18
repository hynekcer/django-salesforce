"""Backward compatible behaviour with primary key 'Id' and upper-case field names"""
from salesforce import DJANGO_19_PLUS
from salesforce import models
from salesforce.models import SalesforceModel


def auto_assign_user():
    # (obsoleted - for test of backward compatibility)
    """
    Function that can be used instead of default value of ForeignKey User,
    where SFDC can assign an useful value, e.g. the current user for Owner field.
    """
    return User(pk='DEFAULT')


class User(SalesforceModel):
    Username = models.CharField(max_length=80)
    Email = models.CharField(max_length=100)


class Lead(SalesforceModel):
    Company = models.CharField(max_length=255)
    LastName = models.CharField(max_length=80)
    Owner = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                              default=auto_assign_user, db_column='OwnerId')
    if DJANGO_19_PLUS:
        # the second positional parameter "on_delete" is not supported before Django 1.9
        LastModifiedBy = models.ForeignKey(User, models.DO_NOTHING, related_name='+',
                                           sf_read_only=models.READ_ONLY)
