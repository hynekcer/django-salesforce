# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

from salesforce import models, DJANGO_14_PLUS
from salesforce.models import SalesforceModel as SalesforceModelParent

import django
from django.conf import settings

if DJANGO_14_PLUS:
	from django.utils.encoding import python_2_unicode_compatible
else:
	def python_2_unicode_compatible(klass):
		klass.__unicode__ = klass.__str__
		klass.__str__ = lambda self: self.__unicode__().encode('utf-8')
		return klass


SALUTATIONS = [
	'Mr.', 'Ms.', 'Mrs.', 'Dr.', 'Prof.'
]

INDUSTRIES = [
	'Agriculture', 'Apparel', 'Banking', 'Biotechnology', 'Chemicals',
	'Communications', 'Construction', 'Consulting', 'Education',
	'Electronics', 'Energy', 'Engineering', 'Entertainment', 'Environmental',
	'Finance', 'Food & Beverage', 'Government', 'Healthcare', 'Hospitality',
	'Insurance', 'Machinery', 'Manufacturing', 'Media', 'Not For Profit',
	'Other', 'Recreation', 'Retail', 'Shipping', 'Technology',
	'Telecommunications', 'Transportation', 'Utilities'
]

# This class customizes `managed = True` for tests and does not disturbe SF
class SalesforceModel(SalesforceModelParent):
	class Meta:
		abstract = True
		managed = True


class User(SalesforceModel):
	Username = models.CharField(max_length=80)
	Email = models.CharField(max_length=100)
	LastName = models.CharField(max_length=80)
	FirstName = models.CharField(max_length=40)
	IsActive = models.BooleanField(default=False)


class AbstractAccount(SalesforceModel):
	"""
	Default Salesforce Account model.
	"""
	TYPES = [
		'Analyst', 'Competitor', 'Customer', 'Integrator', 'Investor',
		'Partner', 'Press', 'Prospect', 'Reseller', 'Other'
	]

	Owner = models.ForeignKey(User, on_delete=models.DO_NOTHING,
			default=lambda:User(pk='DEFAULT'),
			db_column='OwnerId')
	Type = models.CharField(max_length=100, choices=[(x, x) for x in TYPES],
							null=True)
	BillingStreet = models.CharField(max_length=255)
	BillingCity = models.CharField(max_length=40)
	BillingState = models.CharField(max_length=20)
	BillingPostalCode = models.CharField(max_length=20)
	BillingCountry = models.CharField(max_length=40)
	ShippingStreet = models.CharField(max_length=255)
	ShippingCity = models.CharField(max_length=40)
	ShippingState = models.CharField(max_length=20)
	ShippingPostalCode = models.CharField(max_length=20)
	ShippingCountry = models.CharField(max_length=40)
	Phone = models.CharField(max_length=255)
	Fax = models.CharField(max_length=255)
	Website = models.CharField(max_length=255)
	Industry = models.CharField(max_length=100,
								choices=[(x, x) for x in INDUSTRIES])
	Description = models.TextField()
	# Added read only option, otherwise the object can not be never saved
	# If the model is used also with non SF databases then there should be set
	# allow_now=True or null=True
	LastModifiedDate = models.DateTimeField(db_column='LastModifiedDate',
											sf_read_only=models.READ_ONLY,
											auto_now=True)

	class Meta(SalesforceModel.Meta):
		abstract = True

	def __unicode__(self):
		return self.Name


class CoreAccount(AbstractAccount):
	Name = models.CharField(max_length=255)
	class Meta(AbstractAccount.Meta):
		abstract = True


class PersonAccount(AbstractAccount):
	# Non standard fields that require activating "Person Account"
	# (irreversible changes in Salesforce)
	LastName = models.CharField(max_length=80)
	FirstName = models.CharField(max_length=40)
	Name = models.CharField(max_length=255, sf_read_only=models.READ_ONLY)
	Salutation = models.CharField(max_length=100,
								  choices=[(x, x) for x in SALUTATIONS])
	IsPersonAccount = models.BooleanField(default=False, sf_read_only=models.READ_ONLY)
	PersonEmail = models.CharField(max_length=100)

	class Meta(AbstractAccount.Meta):
		abstract = True


if getattr(settings, 'PERSON_ACCOUNT_ACTIVATED', False):
	class Account(PersonAccount):
		pass
else:
	class Account(CoreAccount):
		pass


class Contact(SalesforceModel):
	# Example that db_column is not necessary for most of fields even with
	# lower case names and for ForeignKey
	account = models.ForeignKey(Account, on_delete=models.DO_NOTHING,
			blank=True, null=True)  # db_column: 'OwnerId'
	last_name = models.CharField(max_length=80)
	first_name = models.CharField(max_length=40, blank=True)
	name = models.CharField(max_length=121, sf_read_only=models.READ_ONLY,
			verbose_name='Full Name')
	email = models.EmailField(blank=True, null=True)
	email_bounced_date = models.DateTimeField(blank=True, null=True)
	# The `default=` with lambda function is easy readable, but can be
	# problematic with migrations in the future because it is not serializable.
	# It can be replaced by normal function.
	owner = models.ForeignKey(User, on_delete=models.DO_NOTHING,
			default=lambda:User(pk='DEFAULT'),
			related_name='contact_owner_set')

	def __unicode__(self):
		return self.name


class Lead(SalesforceModel):
	"""
	Default Salesforce Lead model.
	"""
	SOURCES = [
		'Advertisement', 'Employee Referral', 'External Referral',
		'Partner', 'Public Relations',
		'Seminar - Internal', 'Seminar - Partner', 'Trade Show', 'Web',
		'Word of mouth', 'Other',
	]

	STATUSES = [
		'Contacted', 'Open', 'Qualified', 'Unqualified',
	]

	RATINGS = [
		'Hot', 'Warm', 'Cold',
	]

	LastName = models.CharField(max_length=80)
	FirstName = models.CharField(max_length=40)
	Salutation = models.CharField(max_length=100, choices=[(x, x) for x in SALUTATIONS])
	Salutation = models.CharField(max_length=100,
								  choices=[(x, x) for x in SALUTATIONS])
	Name = models.CharField(max_length=121, sf_read_only=models.READ_ONLY)
	Title = models.CharField(max_length=128)
	Company = models.CharField(max_length=255)
	Street = models.CharField(max_length=255)
	City = models.CharField(max_length=40)
	State = models.CharField(max_length=20)
	PostalCode = models.CharField(max_length=20)
	Country = models.CharField(max_length=40)
	Phone = models.CharField(max_length=255)
	Email = models.CharField(max_length=100)
	Website = models.CharField(max_length=100)
	Description = models.TextField()
	LeadSource = models.CharField(max_length=100,
								  choices=[(x, x) for x in SOURCES])
	Status = models.CharField(max_length=100, choices=[(x, x) for x in STATUSES])
	Industry = models.CharField(max_length=100,
								  choices=[(x, x) for x in INDUSTRIES])
	Rating = models.CharField(max_length=100, choices=[(x, x) for x in RATINGS])
	# Added an example of special DateTime field in Salesforce that can
	# not be inserted, but can be updated
	# TODO write test for it
	EmailBouncedDate = models.DateTimeField(blank=True, null=True,
											sf_read_only=models.NOT_CREATEABLE)
	# Deleted object can be found only in querysets with "query_all" SF method.
	IsDeleted = models.BooleanField(default=False, sf_read_only=models.READ_ONLY)

	def __unicode__(self):
		return self.Name


class Product(SalesforceModel):
	Name = models.CharField(max_length=255)

	class Meta(SalesforceModel.Meta):
		db_table = 'Product2'

	def __unicode__(self):
		return self.Name


class Pricebook(SalesforceModel):
	Name = models.CharField(max_length=255)

	class Meta(SalesforceModel.Meta):
		db_table = 'Pricebook2'

	def __unicode__(self):
		return self.Name


class PricebookEntry(SalesforceModel):
	Name = models.CharField(max_length=255, db_column='Name', sf_read_only=models.READ_ONLY)
	Pricebook2 = models.ForeignKey('Pricebook', on_delete=models.DO_NOTHING)
	Product2 = models.ForeignKey('Product', on_delete=models.DO_NOTHING)
	UseStandardPrice = models.BooleanField(default=False)
	UnitPrice = models.DecimalField(decimal_places=2, max_digits=18)

	class Meta(SalesforceModel.Meta):
		db_table = 'PricebookEntry'
		verbose_name_plural = "PricebookEntries"

	def __unicode__(self):
		return self.Name


class ChargentOrder(SalesforceModel):
	class Meta(SalesforceModel.Meta):
		db_table = 'ChargentOrders__ChargentOrder__c'
		custom = True

	OwnerId = models.CharField(max_length=255, db_column='OwnerId')
	IsDeleted = models.CharField(max_length=255, db_column='IsDeleted')
	Name = models.CharField(max_length=255, db_column='Name')
	CreatedDate = models.CharField(max_length=255, db_column='CreatedDate')
	CreatedById = models.CharField(max_length=255, db_column='CreatedById')
	LastModifiedDate = models.CharField(max_length=255,
										db_column='LastModifiedDate', null=True)
	LastModifiedById = models.CharField(max_length=255,
										db_column='LastModifiedById')
	SystemModstamp = models.CharField(max_length=255, db_column='SystemModstamp')
	LastActivityDate = models.CharField(max_length=255,
										db_column='LastActivityDate')
	# example of automatically recognized name  db_column='ChargentOrders__Balance_Due__c'
	Balance_Due = models.CharField(max_length=255)
	Bank_Account_Name = models.CharField(max_length=255, db_column='ChargentOrders__Bank_Account_Name__c')
	Bank_Account_Number = models.CharField(max_length=255, db_column='ChargentOrders__Bank_Account_Number__c')
	Bank_Account_Type = models.CharField(max_length=255, db_column='ChargentOrders__Bank_Account_Type__c')
	Bank_Name = models.CharField(max_length=255, db_column='ChargentOrders__Bank_Name__c')
	Bank_Routing_Number = models.CharField(max_length=255, db_column='ChargentOrders__Bank_Routing_Number__c')
	Billing_Address = models.CharField(max_length=255, db_column='ChargentOrders__Billing_Address__c')
	Billing_City = models.CharField(max_length=255, db_column='ChargentOrders__Billing_City__c')
	Billing_Company = models.CharField(max_length=255, db_column='ChargentOrders__Billing_Company__c')
	Billing_Country = models.CharField(max_length=255, db_column='ChargentOrders__Billing_Country__c')
	Billing_Email = models.CharField(max_length=255, db_column='ChargentOrders__Billing_Email__c')
	Billing_Fax = models.CharField(max_length=255, db_column='ChargentOrders__Billing_Fax__c')
	Billing_First_Name = models.CharField(max_length=255, db_column='ChargentOrders__Billing_First_Name__c')
	Billing_Last_Name = models.CharField(max_length=255, db_column='ChargentOrders__Billing_Last_Name__c')
	Billing_Phone = models.CharField(max_length=255, db_column='ChargentOrders__Billing_Phone__c')
	Billing_State_Province = models.CharField(max_length=255, db_column='ChargentOrders__Billing_State_Province__c')
	Billing_State = models.CharField(max_length=255, db_column='ChargentOrders__Billing_State__c')
	Billing_Zip_Postal = models.CharField(max_length=255, db_column='ChargentOrders__Billing_Zip_Postal__c')
	Birthdate = models.CharField(max_length=255, db_column='ChargentOrders__Birthdate__c')
	Card_Expiration_Month = models.CharField(max_length=255, db_column='ChargentOrders__Card_Expiration_Month__c')
	Card_Expiration_Year = models.CharField(max_length=255, db_column='ChargentOrders__Card_Expiration_Year__c')
	Card_Number = models.CharField(max_length=255, db_column='ChargentOrders__Card_Number__c')
	Card_Security_Code = models.CharField(max_length=255, db_column='ChargentOrders__Card_Security_Code__c')
	Card_Type = models.CharField(max_length=255, db_column='ChargentOrders__Card_Type__c')
	Charge_Amount = models.CharField(max_length=255, db_column='ChargentOrders__Charge_Amount__c')
	Check_Number = models.CharField(max_length=255, db_column='ChargentOrders__Check_Number__c')
	Credit_Card_Name = models.CharField(max_length=255, db_column='ChargentOrders__Credit_Card_Name__c')
	Currency = models.CharField(max_length=255, db_column='ChargentOrders__Currency__c')
	Date = models.CharField(max_length=255, db_column='ChargentOrders__Date__c')
	Description = models.CharField(max_length=255, db_column='ChargentOrders__Description__c')
	Gateway = models.CharField(max_length=255, db_column='ChargentOrders__Gateway__c')
	Manual_Charge = models.CharField(max_length=255, db_column='ChargentOrders__Manual_Charge__c')
	Mercury_ID = models.CharField(max_length=255, db_column='ChargentOrders__Mercury_ID__c')
	No_Tax = models.CharField(max_length=255, db_column='ChargentOrders__No_Tax__c')
	OrderNumber = models.CharField(max_length=255, db_column='ChargentOrders__OrderNumber__c')
	Order_Note = models.CharField(max_length=255, db_column='ChargentOrders__Order_Note__c')
	PO_Number = models.CharField(max_length=255, db_column='ChargentOrders__PO_Number__c')
	Payment_Count = models.CharField(max_length=255, db_column='ChargentOrders__Payment_Count__c')
	Payment_End_Date = models.CharField(max_length=255, db_column='ChargentOrders__Payment_End_Date__c')
	Payment_Frequency = models.CharField(max_length=255, db_column='ChargentOrders__Payment_Frequency__c')
	Payment_Method = models.CharField(max_length=255, db_column='ChargentOrders__Payment_Method__c')
	Payment_Received = models.CharField(max_length=255, db_column='ChargentOrders__Payment_Received__c')
	Payment_Start_Date = models.CharField(max_length=255, db_column='ChargentOrders__Payment_Start_Date__c')
	Payment_Status = models.CharField(max_length=255, db_column='ChargentOrders__Payment_Status__c')
	Payment_Stop = models.CharField(max_length=255, db_column='ChargentOrders__Payment_Stop__c')
	Shipping_Address = models.CharField(max_length=255, db_column='ChargentOrders__Shipping_Address__c')
	Shipping_City = models.CharField(max_length=255, db_column='ChargentOrders__Shipping_City__c')
	Shipping_Company = models.CharField(max_length=255, db_column='ChargentOrders__Shipping_Company__c')
	Shipping_Country = models.CharField(max_length=255, db_column='ChargentOrders__Shipping_Country__c')
	Shipping_Duty = models.CharField(max_length=255, db_column='ChargentOrders__Shipping_Duty__c')
	Shipping_First_Name = models.CharField(max_length=255, db_column='ChargentOrders__Shipping_First_Name__c')
	Shipping_Instructions = models.CharField(max_length=255, db_column='ChargentOrders__Shipping_Instructions__c')
	Shipping_Name = models.CharField(max_length=255, db_column='ChargentOrders__Shipping_Name__c')
	Shipping_Phone = models.CharField(max_length=255, db_column='ChargentOrders__Shipping_Phone__c')
	Shipping_State = models.CharField(max_length=255, db_column='ChargentOrders__Shipping_State__c')
	Shipping_Zip_Postal = models.CharField(max_length=255, db_column='ChargentOrders__Shipping_Zip_Postal__c')
	Shipping = models.CharField(max_length=255, db_column='ChargentOrders__Shipping__c')
	Status = models.CharField(max_length=255, db_column='ChargentOrders__Status__c')
	Subtotal = models.CharField(max_length=255, db_column='ChargentOrders__Subtotal__c')
	Tax_Exempt = models.CharField(max_length=255, db_column='ChargentOrders__Tax_Exempt__c')
	Tax = models.CharField(max_length=255, db_column='ChargentOrders__Tax__c')
	Total = models.CharField(max_length=255, db_column='ChargentOrders__Total__c')
	Tracking_Number = models.CharField(max_length=255, db_column='ChargentOrders__Tracking_Number__c')
	Transaction_Count_Recurring = models.CharField(max_length=255, db_column='ChargentOrders__Transaction_Count_Recurring__c')
	Transaction_Count = models.CharField(max_length=255, db_column='ChargentOrders__Transaction_Count__c')
	Transaction_Total = models.CharField(max_length=255, db_column='ChargentOrders__Transaction_Total__c')
	AccountID = models.CharField(max_length=255, db_column='AccountID__c')
	Campaign = models.CharField(max_length=255, db_column='Campaign__c')
	Contribution_Date = models.CharField(max_length=255, db_column='Contribution_Date__c')
	Contribution_Type = models.CharField(max_length=255, db_column='Contribution_Type__c')
	Corporate_Flag = models.CharField(max_length=255, db_column='Corporate_Flag__c')
	Follow_up_Complete = models.CharField(max_length=255, db_column='Follow_up_Complete__c')
	Member_Flag = models.CharField(max_length=255, db_column='Member_Flag__c')
	Opportunity = models.CharField(max_length=255, db_column='Opportunity__c')
	Order_Name = models.CharField(max_length=255, db_column='Order_Name__c')
	PAC_Fund = models.CharField(max_length=255, db_column='PAC_Fund__c')
	Event_Flag = models.CharField(max_length=255, db_column='Event_Flag__c')


class CronTrigger(SalesforceModel):
	# A special DateTime field with milisecond resolution (read only)
	PreviousFireTime = models.DateTimeField(verbose_name='Previous Run Time', blank=True, null=True)
	# ...


class BusinessHours(SalesforceModel):
	Name = models.CharField(max_length=80)
	# The default record is automatically created by Salesforce.
	IsDefault = models.BooleanField(default=False, verbose_name='Default Business Hours')
	# ... much more fields, but we use only this one TimeFiled for test
	MondayStartTime = models.TimeField()

	class Meta:
		verbose_name_plural = "BusinessHours"


test_custom_db_table, test_custom_db_column = getattr(settings,
		'TEST_CUSTOM_FIELD', 'ChargentOrders__ChargentOrder__c.Name').split('.')

class SalesforceParentModel(SalesforceModel):
	"""
	Example of standard fields present in all custom models.
	"""
	# This is not a custom field because is not defined in a custom model.
	# The API name is therefore 'Name'.
	name = models.CharField(max_length=80)
	last_modified_date = models.DateTimeField(sf_read_only=models.READ_ONLY)
	# This model is not custom because it has not an explicit attribute
	# `custom = True` in Meta and also has not a `db_table` that ends with
	# '__c'.
	class Meta:
		abstract = True


class TestCustomExample(SalesforceParentModel):
	"""
	Simple custom model with one custom and more standard fields.

	Salesforce object for this model can be created from the branch
	  hynekcer/tooling-api-and-metadata  by commands
	$ python manage.py shell
		>> from salesforce.tooling import *
		>> install_metadata_service()
		>> create_demo_test_object()
	
	or create an object with `API Name`: `Test__c`
	`Data Type` of the Record Name: `Text`
	with a text field `API Name`: `TestField__c`.
	and set it accessible by you. (`Set Field-Leved Security`)
	"""
	# This is a custom field because it is defined in the custom model.
	# The API name is therefore 'TestField__c'
	test_field = models.CharField(max_length=42)
	class Meta:
		db_table = 'Test__c'
		custom = True


class GeneralCustomModel(SalesforceModel):
	"""
	This model is used for tests on a field of type CharField on a custom model
	specified in local_settings.py:
	Example:
		TEST_CUSTOM_FIELD = 'TIMBASURVEYS__SurveyQuestion__c.TIMBASURVEYS__Question__c'
	Other fields shouldn't be required for saving that object.
	"""
	# The line "managed = False" or Meta inherited from SalesforceModel.Meta
	# is especially important if the model shares a table with other model.
	class Meta:
		db_table = test_custom_db_table

	GeneralCustomField = models.CharField(max_length=255, db_column=test_custom_db_column)


class Note(models.Model):
	title = models.CharField(max_length=80)
	body = models.TextField(null=True)
	parent_id = models.CharField(max_length=18)
	parent_type = models.CharField(max_length=50, db_column='Parent.Type', sf_read_only=models.READ_ONLY)


class Opportunity(models.Model):
	name = models.CharField(max_length=255)
	contacts = django.db.models.ManyToManyField(Contact, through='example.OpportunityContactRole', related_name='opportunities')
	close_date = models.DateField()
	stage = models.CharField(max_length=255, db_column='StageName') # e.g. "Prospecting"


class OpportunityContactRole(models.Model):
	opportunity = models.ForeignKey(Opportunity, on_delete=models.DO_NOTHING, related_name='contact_roles')
	contact = models.ForeignKey(Contact, on_delete=models.DO_NOTHING, related_name='opportunity_roles')
	role = models.CharField(max_length=40, blank=True, null=True)  # e.g. "Business User"
