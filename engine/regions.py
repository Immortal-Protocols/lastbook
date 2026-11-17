"""Region identifiers shared by setup, offline search and map builders.

US state ids stay unchanged. Canadian provinces use ISO-style ids so Canada can
never be confused with California.
"""
import re

REGION_ID = re.compile(r'(?:[A-Z]{2}|[A-Z]{2}-[A-Z0-9]{1,3})')
ONTARIO = {
    'id': 'CA-ON', 'title': 'Ontario', 'country': 'CA', 'country_name': 'Canada',
    'bounds': [-95.31, 41.52, -74.17, 57.01],
}
REGIONS = {'CA-ON': ONTARIO}


def valid_region_id(value):
    return isinstance(value, str) and REGION_ID.fullmatch(value) is not None


def canonical_region(value, country=''):
    value = str(value or '').strip().upper()
    if value in ('CA-ON', 'ON', 'ONTARIO') and country in ('', 'CA'):
        return 'CA-ON'
    return value
