# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

import re

from salesforce import DJANGO_18_PLUS

if DJANGO_18_PLUS:
	from django.db.backends.base.operations import BaseDatabaseOperations
else:
	from django.db.backends import BaseDatabaseOperations

"""
Default database operations, with unquoted names.
"""

class DatabaseOperations(BaseDatabaseOperations):
	compiler_module = "salesforce.backend.compiler"
	
	def connection_init(self):
		pass
	
	def sql_flush(self, style, tables, sequences):
		return []
	
	def quote_name(self, name):
		return name
	
	def value_to_db_datetime(self, value):
		"""
		We let the JSON serializer handle dates for us.
		"""
		return value

	def value_to_db_date(self, value):
		"""
		We let the JSON serializer handle dates for us.
		"""
		return value
	
	def value_to_db_decimal(self, value, *args):
		if str(value) == 'DEFAULTED_ON_CREATE':
			return value
		return super(DatabaseOperations, self).value_to_db_decimal(value, *args)

	def last_insert_id(self, cursor, db_table, db_column):
		return cursor.lastrowid

	# This SQL is not important because we control the db from the compiler
	# but anything must exist
	def bulk_insert_sql(self, fields, num_values):
		items_sql = "(%s)" % ", ".join(["%s"] * len(fields))
		return "VALUES " + ", ".join([items_sql] * num_values)

