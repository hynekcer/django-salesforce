# Generated by Django 3.2.5 on 2021-07-14 22:10

from django.db import migrations


class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        ('example', '0003_auto_20210714_2108'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='test',
            options={'verbose_name': 'Test', 'verbose_name_plural': 'Tests_'},
        ),
        migrations.AlterModelTable(
            name='test',
            table='django_TestX__c',
        ),
    ]