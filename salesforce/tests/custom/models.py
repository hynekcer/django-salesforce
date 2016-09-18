# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey has `on_delete` set to the desired behavior.
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from __future__ import unicode_literals

from salesforce import models


class DjangoTest(models.Model):
    name = models.CharField(max_length=80, verbose_name='Test Record',
                            default=models.DEFAULTED_ON_CREATE, blank=True, null=True)
    test_bool = models.BooleanField(custom=True, default=models.DEFAULTED_ON_CREATE)
    test_text = models.CharField(custom=True, max_length=42, blank=True, null=True)
    django_test = models.CharField(custom=True, db_column='django_Test__c', max_length=20,
                                   verbose_name='django_Test', blank=True, null=True)
    test_date_time = models.DateTimeField(custom=True, verbose_name='Test DateTime', blank=True, null=True)
    test_picklist = models.CharField(
        custom=True, db_column='Test_Picklist__c', max_length=255, verbose_name='Test Picklist',
        choices=[('Line 1', 'Line 1'), ('Line 2', 'Line 2'), ('Line 3', 'Line 3')],
        blank=True, null=True
    )
    test_multiselect_picklist = models.CharField(
        custom=True, max_length=4099,
        choices=[('Item 1', 'Item 1'), ('Item 2', 'Item 2'), ('Item 3', 'Item 3')],
        blank=True, null=True
    )
    test_reference_self = models.ForeignKey('self', on_delete=models.DO_NOTHING, custom=True, blank=True, null=True)
    children_count = models.DecimalField(custom=True, db_column='children_count__c',
                                         max_digits=18, decimal_places=0, verbose_name='children count',
                                         sf_read_only=models.READ_ONLY, blank=True, null=True)
    last_modified_date = models.DateTimeField(sf_read_only=models.READ_ONLY)
    # contact = models.ForeignKey('Contact', on_delete=models.DO_NOTHING, custom=True, blank=True, null=True)

    class Meta(models.Model.Meta):
        db_table = 'django_Test__c'
        verbose_name = 'django Test'
        verbose_name_plural = 'django Tests'
        # keyPrefix = 'a0p'


class DjangoTestDetail(models.Model):
    name = models.CharField(max_length=80, verbose_name='django Test detail Name',
                            default=models.DEFAULTED_ON_CREATE, blank=True, null=True)
    parent = models.ForeignKey(DjangoTest, on_delete=models.DO_NOTHING, custom=True,
                               sf_read_only=models.NOT_UPDATEABLE)  # Master Detail Relationship 0

    class Meta(models.Model.Meta):
        db_table = 'django_Test_detail__c'
        verbose_name = 'django Test detail'
        verbose_name_plural = 'django Test details'
        # keyPrefix = 'a0Z'
