# Generated by Django 3.2.5 on 2021-07-14 19:08

from django.db import migrations
import salesforce.fields


class Migration(migrations.Migration):

    dependencies = [
        ('example', '0002_auto_20210714_1933'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='test',
            options={'verbose_name': 'Test', 'verbose_name_plural': 'Tests'},
        ),
        migrations.AddField(
            model_name='test',
            name='test_decimal',
            field=salesforce.fields.DecimalField(db_column='TestDecimal__c', decimal_places=2, default=0, max_digits=10, sf_managed=True),
        ),
        migrations.AddField(
            model_name='test',
            name='test_picklist',
            field=salesforce.fields.CharField(choices=[('a', 'A'), ('b', 'B')], db_column='TestPicklist__c', max_length=40, null=True, sf_managed=True),
        ),
        migrations.AlterField(
            model_name='test',
            name='name',
            field=salesforce.fields.CharField(max_length=20, verbose_name='name'),
        ),
        migrations.AlterField(
            model_name='test',
            name='test_text',
            field=salesforce.fields.CharField(db_column='TestText__c', help_text='unicode Θöá', max_length=41, sf_managed=True, verbose_name='text_'),
        ),
    ]