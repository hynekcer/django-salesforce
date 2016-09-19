import datetime
import pytz
from django.test.utils import override_settings
from salesforce.dbapi.mocksf import MockJsonRequest, MockTestCase
from .models import DjangoTest, DjangoTestDetail


QUERY_SANDBOX = MockJsonRequest(
    'GET', 'mock:///services/data/v37.0/query/?q=SELECT+IsSandbox+FROM+Organization',
    resp=('{"totalSize":1,"done":true,"records":[{"attributes":{"type":"Organization",'
          '"url":"/services/data/v37.0/sobjects/Organization/00DM0000001eBkwMAE"},"IsSandbox":true}]}')
)


# @override_settings(SF_MOCK_MODE='record')
# @override_settings(SF_MOCK_MODE='playback')
# @override_settings(SF_MOCK_MODE='mixed')
class CustomTest(MockTestCase):

    # @override_settings(SF_MOCK_MODE='record')
    def test_insert(self):
        # playback log
        self.mock_add_expected([
            QUERY_SANDBOX,
            MockJsonRequest(  # create row_1
                'POST', 'mock:///services/data/v37.0/sobjects/django_Test__c/',
                req=('{"Name": "sf_test_1", "TestBool__c": "true", "TestText__c": "something", '
                     '"Test_Picklist__c": "Line 2", "TestMultiselectPicklist__c": "Item 1;Item 3", '
                     '"TestReferenceSelf__c": null, "TestDateTime__c": "2016-12-31T23:30:15.000+0000"}'),
                resp='{"id":"a0pM0000002Dy6yIAC","success":true,"errors":[]}',
                status_code=201),
            MockJsonRequest(  # create row_2
                'POST', 'mock:///services/data/v37.0/sobjects/django_Test__c/',
                req=('{"Name": "sf_test_2", "TestBool__c": "false", "TestText__c": null, '
                     '"Test_Picklist__c": null, "TestMultiselectPicklist__c": null, '
                     '"TestReferenceSelf__c": "a0pM0000002Dy6yIAC", "TestDateTime__c": null}'),
                resp='{"id":"a0pM0000002Dy9OIAS","success":true,"errors":[]}',
                status_code=201),
            MockJsonRequest(  # update row_1
                'PATCH', 'mock:///services/data/v37.0/sobjects/django_Test__c/a0pM0000002Dy9OIAS',
                req='{"TestReferenceSelf__c": "a0pM0000002Dy6yIAC"}',
                status_code=204),
            MockJsonRequest(  # query
                'GET', ('mock:///services/data/v37.0/query/?q='
                        'SELECT+COUNT%28django_Test__c.Id%29+x_sf_count+FROM+django_Test__c'),
                resp=('{"totalSize":1,"done":true,"records":[{"attributes":{"type":"AggregateResult"},'
                      '"x_sf_count":2}]}')),
            MockJsonRequest(  # delete
                'DELETE', 'mock:///services/data/v37.0/sobjects/django_Test__c/a0pM0000002Dy9OIAS',
                status_code=204),
            MockJsonRequest(  # delete
                'DELETE', 'mock:///services/data/v37.0/sobjects/django_Test__c/a0pM0000002Dy6yIAC',
                status_code=204),
        ])
        # test
        row_1 = DjangoTest.objects.create(name='sf_test_1',
                                          test_bool=True,
                                          test_text='something',
                                          test_picklist='Line 2',
                                          test_multiselect_picklist='Item 1;Item 3',
                                          test_date_time=datetime.datetime(2016, 12, 31, 23, 30, 15, tzinfo=pytz.utc),
                                          test_reference_self=None,
                                          )
        row_2 = DjangoTest.objects.create(name='sf_test_2', test_reference_self=row_1, test_bool=False)
        row_1.test_reference_self = row_2
        # with override_settings(SF_MOCK_MODE='record'):
        row_2.save(update_fields=['test_reference_self'])
        try:
            self.assertEqual(DjangoTest.objects.count(), 2)
            DjangoTestDetail  # .objects.count
        finally:
            row_2.delete()
            row_1.delete()
