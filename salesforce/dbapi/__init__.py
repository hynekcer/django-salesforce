"""
Python DB API 2.0 - A layer that is independent on Django.

Basic SQL and a small part of PEP 0249 will implemented.
On the contrary, transactions will be never implemented.

Purpose:
Many Salesforce APIs and low level features need not be updated and
tested for every Django version, but can depend on some SFDC version.
"""

import logging

log = logging.getLogger(__name__)

# The maximal number of retries for timeouts in requests to Force.com API.
# Can be set dynamically
# None: use defaults from settings.REQUESTS_MAX_RETRIES (default 1)
# 0: no retry
# 1: one retry
MAX_RETRIES = None  # uses defaults below)


def get_max_retries():
    """Get the maximal number of requests retries"""
    global MAX_RETRIES
    from django.conf import settings
    if MAX_RETRIES is None:
        MAX_RETRIES = getattr(settings, 'REQUESTS_MAX_RETRIES', 1)
    return MAX_RETRIES
