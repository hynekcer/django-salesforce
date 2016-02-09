"""
Python DB API 2.0 - A layer that is independent on Django.

Basic SQL and a small part of PEP 0249 will implemented.
On the contrary, transactions will be never implemented.

Purpose:
Many Salesforce APIs and low level features need not be updated and
tested for every Django version, but can depend on some SFDC version.
"""
