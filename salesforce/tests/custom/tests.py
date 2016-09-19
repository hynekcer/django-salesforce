import datetime
import pytz
from django.test import mock
from django.test.utils import override_settings
from salesforce.dbapi.mocksf import MockJsonRequest, MockTestCase
from .models import DjangoTest, DjangoTestDetail


QUERY_SANDBOX = MockJsonRequest(
    'GET', 'mock:///services/data/v37.0/query/?q=SELECT+IsSandbox+FROM+Organization',
    resp=('{"totalSize":1,"done":true,"records":[{"attributes":{"type":"Organization",'
          '"url":"/services/data/v37.0/sobjects/Organization/00DM0000001eBkwMAE"},"IsSandbox":true}]}')
)


@override_settings(SF_MOCK_MODE='playback')
@mock.patch('salesforce.API_VERSION', '37.0')  # use the version recorded in playback
class CustomTest(MockTestCase):

    ROW_DICT_1 = dict(name='sf_test_1',
                      test_bool=True,
                      test_text='something',
                      test_picklist='Line 2',
                      test_multiselect_picklist='Item 1;Item 3',
                      test_date_time=datetime.datetime(2016, 12, 31, 23, 30, 15, tzinfo=pytz.utc),
                      test_reference_self=None,
                      )
    CREATE_ROW_1 = MockJsonRequest(
        'POST', 'mock:///services/data/v37.0/sobjects/django_Test__c/',
        req=('{"Name": "sf_test_1", "TestBool__c": "true", "TestText__c": "something", '
             '"Test_Picklist__c": "Line 2", "TestMultiselectPicklist__c": "Item 1;Item 3", '
             '"TestReferenceSelf__c": null, "TestDateTime__c": "2016-12-31T23:30:15.000+0000"}'),
        resp='{"id":"a0pM0000002Dy6yIAC","success":true,"errors":[]}',
        status_code=201)
    DELETE_ROW_1 = MockJsonRequest(
        'DELETE', 'mock:///services/data/v37.0/sobjects/django_Test__c/a0pM0000002Dy6yIAC',
        status_code=204)

    ROW_DICT_2 = dict(name='sf_test_2', test_bool=False)
    CREATE_ROW_2 = MockJsonRequest(
        'POST', 'mock:///services/data/v37.0/sobjects/django_Test__c/',
        req=('{"Name": "sf_test_2", "TestBool__c": "false", "TestText__c": null, '
             '"Test_Picklist__c": null, "TestMultiselectPicklist__c": null, '
             '"TestReferenceSelf__c": null, "TestDateTime__c": null}'),
        resp='{"id":"a0pM0000002Dy9OIAS","success":true,"errors":[]}',
        status_code=201)
    DELETE_ROW_2 = MockJsonRequest(
        'DELETE', 'mock:///services/data/v37.0/sobjects/django_Test__c/a0pM0000002Dy9OIAS',
        status_code=204)

    def test_insert_one_simple(self):
        # playback log
        self.mock_add_expected([
            QUERY_SANDBOX,
            self.CREATE_ROW_1,
            self.DELETE_ROW_1,
        ])
        # test
        row_1 = DjangoTest.objects.create(**self.ROW_DICT_1)
        row_1.delete()

    def test_insert_two_and_update(self):
        # playback log
        self.mock_add_expected([
            QUERY_SANDBOX,
            self.CREATE_ROW_1,
            self.CREATE_ROW_2,
            MockJsonRequest(  # update row_1
                'PATCH', 'mock:///services/data/v37.0/sobjects/django_Test__c/a0pM0000002Dy6yIAC',
                req='{"TestReferenceSelf__c": "a0pM0000002Dy9OIAS"}',
                status_code=204),
            MockJsonRequest(  # update row_2
                'PATCH', 'mock:///services/data/v37.0/sobjects/django_Test__c/a0pM0000002Dy9OIAS',
                req='{"TestReferenceSelf__c": "a0pM0000002Dy6yIAC"}',
                status_code=204),
            MockJsonRequest(  # create DjangoTestDetail
                'POST', 'mock:///services/data/v37.0/sobjects/django_Test_detail__c/',
                req='{"Name": "test detail", "Parent__c": "a0pM0000002Dy6yIAC"}',
                resp='{"id":"a0ZM000000ChaLsMAJ","success":true,"errors":[]}',
                response_type='application/json;charset=UTF-8',
                status_code=201),
            MockJsonRequest(  # query count
                'GET', ('mock:///services/data/v37.0/query/?q='
                        'SELECT+COUNT%28django_Test__c.Id%29+x_sf_count+FROM+django_Test__c'),
                resp=('{"totalSize":1,"done":true,"records":[{"attributes":{"type":"AggregateResult"},'
                      '"x_sf_count":2}]}')),
            self.DELETE_ROW_2,
            self.DELETE_ROW_1,
            MockJsonRequest(
                'DELETE', 'mock:///services/data/v37.0/sobjects/django_Test_detail__c/a0ZM000000ChaLsMAJ',
                status_code=204),
        ])
        # test
        row_1 = DjangoTest.objects.create(**self.ROW_DICT_1)
        row_2 = DjangoTest.objects.create(**self.ROW_DICT_2)
        try:
            row_1.test_reference_self = row_2
            row_2.test_reference_self = row_1
            row_1.save(update_fields=['test_reference_self'])
            row_2.save(update_fields=['test_reference_self'])
            row_detail_1 = DjangoTestDetail.objects.create(name='test detail', parent=row_1)
            self.assertEqual(DjangoTest.objects.count(), 2)
        finally:
            row_2.delete()
            row_1.delete()
            row_detail_1.delete()
