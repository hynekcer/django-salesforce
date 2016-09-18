from django.test.utils import override_settings
from salesforce.dbapi.mocksf import MockJsonRequest, MockTestCase
from .models import DjangoTest, DjangoTestDetail


QUERY_SANDBOX = MockJsonRequest(
    'GET', 'mock:///services/data/v37.0/query/?q=SELECT+IsSandbox+FROM+Organization',
    resp=('{"totalSize":1,"done":true,"records":[{"attributes":{"type":"Organization",'
          '"url":"/services/data/v37.0/sobjects/Organization/00DM0000001eBkwMAE"},"IsSandbox":true}]}')
)


@override_settings(SF_MOCK_MODE='playback')
# @override_settings(SF_MOCK_MODE='mixed')
class CustomTest(MockTestCase):

    # @override_settings(SF_MOCK_MODE='record')
    def test_insert(self):
        self.mock_add_expected([
            QUERY_SANDBOX,
            MockJsonRequest(
                'POST', 'mock:///services/data/v37.0/sobjects/django_Test__c/',
                req=('{"Name": "sf_test", "TestBool__c": "true", "TestText__c": "something", '
                     '"Test_Picklist__c": "Line 2", "TestMultiselectPicklist__c": "Item 1;Item 3", '
                     '"TestReferenceSelf__c": null, "django_Test__c": null, "TestDateTime__c": null}'),
                resp='{"id":"a0pM0000002Dy6yIAC","success":true,"errors":[]}',
                status_code=201),
            MockJsonRequest(
                'GET', ('mock:///services/data/v37.0/query/?q='
                        'SELECT+COUNT%28django_Test__c.Id%29+x_sf_count+FROM+django_Test__c'),
                resp=('{"totalSize":1,"done":true,"records":[{"attributes":{"type":"AggregateResult"},'
                      '"x_sf_count":1}]}')),
            MockJsonRequest(
                'DELETE', 'mock:///services/data/v37.0/sobjects/django_Test__c/a0pM0000002Dy6yIAC',
                status_code=204),
        ])

        row = DjangoTest.objects.create(name='sf_test',
                                        test_bool=True,
                                        test_text='something',
                                        test_picklist='Line 2',
                                        test_multiselect_picklist='Item 1;Item 3',
                                        )
        try:
            self.assertEqual(DjangoTest.objects.count(), 1)
            DjangoTestDetail  # .objects.count
        finally:
            row.delete()
