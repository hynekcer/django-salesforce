# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

from decimal import Decimal
import datetime
import pytz
import random
import string

from django.conf import settings
from django.test import TestCase
from django.utils.unittest import skip, skipUnless

from salesforce.testrunner.example.models import Account, Contact, Lead, ChargentOrder
import django
import salesforce

import logging
log = logging.getLogger(__name__)

random_slug = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for x in range(32))
current_user = settings.DATABASES['salesforce']['USER']
test_email = 'test-djsf-unittests-%s@example.com' % random_slug
sf_tables = [x['name'] for x in
		connections['salesforce'].introspection.table_list_cache['sobjects']
		]


def refresh(obj):
	"""
	Get the same object refreshed from db.
	"""
	return obj.__class__.objects.get(pk=obj.pk)
	
def round_datetime_utc(timestamp):
	"""Round to seconds and set zone to UTC."""
	## sfdates are UTC to seconds precision but use a fixed-offset
	## of +0000 (as opposed to a named tz)
	timestamp = timestamp.replace(microsecond=0)
	timestamp = timestamp.replace(tzinfo=pytz.utc)
	return timestamp


class BasicSOQLTest(TestCase):
	def setUp(self):
		"""
		Create our test lead record.
		"""
		self.test_lead = Lead(
			FirstName	= "User",
			LastName	= "Unittest General",
			Email		= test_email,
			Status		= 'Open',
			Company = "Some company, Ltd.",
		)
		self.test_lead.save()
	
	def tearDown(self):
		"""
		Clean up our test lead record.
		"""
		self.test_lead.delete()


	def test_raw(self):
		"""
		Get the first two contact records.
		(At least 3 manually created Contacts must exist before these read-only tests.)
		"""
		contacts = Contact.objects.raw(
				"SELECT Id, LastName, FirstName FROM Contact "
				"LIMIT 2")
		self.assertEqual(len(contacts), 2)
		# It had a side effect that the same assert failed second times.
		self.assertEqual(len(contacts), 2)
		'%s' % contacts[0].__dict__  # Check that all fields are accessible

	def test_raw_foreignkey_id(self):
		"""
		Get the first two contacts by raw query with a ForeignKey id field.
		"""
		contacts = Contact.objects.raw(
				"SELECT Id, LastName, FirstName, OwnerId FROM Contact "
				"LIMIT 2")
		self.assertEqual(len(contacts), 2)
		'%s' % contacts[0].__dict__  # Check that all fields are accessible
		self.assertIn('@', contacts[0].Owner.Email)

	def test_select_all(self):
		"""
		Get the first two contact records.
		"""
		contacts = Contact.objects.all()[0:2]
		self.assertEqual(len(contacts), 2)

	def test_exclude_query_construction(self):
		"""
		Test that exclude query construction returns valid SOQL.
		"""
		contacts = Contact.objects.filter(FirstName__isnull=False).exclude(Email="steve@apple.com", LastName="Wozniak").exclude(LastName="smith")
		number_of_contacts = contacts.count()
		self.assertIsInstance(number_of_contacts, int)
		# the default self.test_lead shouldn't be excluded by only one nondition
		leads = Lead.objects.exclude(Email="steve@apple.com", LastName="Unittest General").filter(FirstName="User", LastName="Unittest General")
		self.assertEqual(leads.count(), 1)

	def test_foreign_key(self):
		account = Account.objects.all()[0]
		user = account.Owner
		self.assertEqual(user.Email, settings.DATABASES['salesforce']['USER'].rsplit('.', 1)[0])  # 'admins@freelancersunion.org.prod001'
	
	def test_update_date_auto(self):
		"""
		Test updating a date.
		"""
		
		account = Account.objects.all()[0]
		account.save()
		now = datetime.datetime.utcnow()
		last_timestamp = salesforce.backend.query.sf_last_timestamp
		if django.VERSION[:2] >= (1,4):
			now = now.replace(tzinfo=pytz.utc)
		else:
			last_timestamp = last_timestamp.replace(tzinfo=None)
		saved = Account.objects.get(pk=account.pk)
		self.assertGreaterEqual(saved.LastModifiedDate, now)
		self.assertLess(saved.LastModifiedDate, now + datetime.timedelta(seconds=5))
		self.assertEqual(saved.LastModifiedDate, last_timestamp)
	
	def test_insert_date(self):
		"""
		Test inserting a date.
		"""
		self.skipTest("TODO Fix this test for yourself please if you have such customize Account.")
		
		now = datetime.datetime.now()
		account = Account(
			FirstName = 'Joe',
			LastName = 'Freelancer',
			IsPersonAccount = False,
			LastLogin = now,
		)
		account.save()
		
		saved = Account.objects.get(pk=account.pk)
		self.assertEqual(saved.LastLogin, now)
		self.assertEqual(saved.IsPersonAccount, False)
		
		saved.delete()
	
	def test_get(self):
		"""
		Get the test lead record.
		"""
		lead = Lead.objects.get(Email=test_email)
		self.assertEqual(lead.FirstName, 'User')
		self.assertEqual(lead.LastName, 'Unittest General')
		# test a read only field (formula of full name)
		self.assertEqual(lead.Name, 'User Unittest General')
	
	def test_not_null(self):
		"""
		Get the test lead record by isnull condition.
		"""
		lead = Lead.objects.get(Email__isnull=False, FirstName='User')
		self.assertEqual(lead.FirstName, 'User')
		self.assertEqual(lead.LastName, 'Unittest General')
	
	def test_not_null_related(self):
		"""
		Verify conditions `isnull` for foreign keys: filter(Account=None)
		filter(Account__isnull=True) and nested in Q(...) | Q(...).
		"""
		test_contact = Contact(FirstName='sf_test', LastName='my')
		test_contact.save()
		try:
			contacts = Contact.objects.filter(Q(Account__isnull=True) |
					Q(Account=None), Account=None, Account__isnull=True,
					FirstName='sf_test')
			self.assertEqual(len(contacts), 1)
		finally:
			test_contact.delete()
	
	def test_unicode(self):
		"""
		Make sure weird unicode breaks properly.
		"""
		test_lead = Lead(FirstName=u'\u2603', LastName="Unittest Unicode", Email='test-djsf-unicode-email@example.com', Company="Some company")
		test_lead.save()
		try:
			self.assertEqual(refresh(test_lead).FirstName, u'\u2603')
		finally:
			test_lead.delete()
	
	def test_date_comparison(self):
		"""
		Test that date comparisons work properly.
		"""
		today = round_datetime_utc(datetime.datetime(2013, 8, 27))
		yesterday = today - datetime.timedelta(days=1)
		tomorrow = today + datetime.timedelta(days=1)
		contact = Contact(FirstName='sf_test', LastName='date',
				EmailBouncedDate=today)
		contact.save()
		try:
			contacts1 = Contact.objects.filter(EmailBouncedDate__gt=yesterday)
			self.assertEqual(len(contacts1), 1)
			contacts2 = Contact.objects.filter(EmailBouncedDate__gt=tomorrow)
			self.assertEqual(len(contacts2), 0)
		finally:
			contact.delete()
	
	def test_insert(self):
		"""
		Create a lead record, and make sure it ends up with a valid Salesforce ID.
		"""
		test_lead = Lead(FirstName="User", LastName="Unittest Inserts", Email='test-djsf-inserts-email@example.com', Company="Some company")
		test_lead.save()
		try:
			self.assertEqual(len(test_lead.pk), 18)
		finally:
			test_lead.delete()
	
	def test_delete(self):
		"""
		Create a lead record, then delete it, and make sure it's gone.
		"""
		test_lead = Lead(FirstName="User", LastName="Unittest Deletes", Email='test-djsf-delete-email@example.com', Company="Some company")
		test_lead.save()
		test_lead.delete()
		
		self.assertRaises(Lead.DoesNotExist, Lead.objects.get, Email='test-djsf-delete-email@example.com')
	
	def test_update(self):
		"""
		Update the test lead record.
		"""
		test_lead = Lead.objects.get(Email=test_email)
		self.assertEqual(test_lead.FirstName, 'User')
		test_lead.FirstName = 'Tested'
		test_lead.save()
		self.assertEqual(refresh(test_lead).FirstName, 'Tested')

	def test_decimal_precision(self):
		"""
		Ensure that the precision on a DecimalField of a record saved to
		or retrieved from SalesForce is equal.
		"""
		product = Product(Name="Test Product")
		product.save()

		# The price for a product must be set in the standard price book.
		# http://www.salesforce.com/us/developer/docs/api/Content/sforce_api_objects_pricebookentry.htm
		pricebook = Pricebook.objects.get(Name="Standard Price Book")
		saved_pricebook_entry = PricebookEntry(Product2Id=product, Pricebook2Id=pricebook, UnitPrice=Decimal('1234.56'), UseStandardPrice=False)
		saved_pricebook_entry.save()
		retrieved_pricebook_entry = PricebookEntry.objects.get(pk=saved_pricebook_entry.pk)

		try:
			self.assertEqual(saved_pricebook_entry.UnitPrice, retrieved_pricebook_entry.UnitPrice)
		finally:
			retrieved_pricebook_entry.delete()
			product.delete()

	@skipUnless('ChargentOrders__ChargentOrder__c' in sf_tables,
			'Not found custom tables ChargentOrders__*')
	def test_custom_objects(self):
		"""
		Make sure custom objects work.
		"""
		from salesforce.testrunner.example.models import TimbaSurveysQuestion
		orders = TimbaSurveysQuestion.objects.all()[0:5]
		self.assertEqual(len(orders), 5)

	def test_update_date_custom(self):
		"""
		Test updating a timestamp in a normal field.
		"""
		# create
		contact = Contact(LastName='test_sf')
		contact.save()
		contact = Contact.objects.filter(Name='test_sf')[0]
		# update
		contact.EmailBouncedDate = now = datetime.datetime.now().replace(tzinfo=pytz.utc)
		contact.save()
		contact = Contact.objects.get(Id=contact.Id)
		# test
		self.assertEqual(contact.EmailBouncedDate.utctimetuple(), now.utctimetuple())
		# delete, including the old failed similar
		for x in Contact.objects.filter(Name='test_sf'):
			x.delete()
