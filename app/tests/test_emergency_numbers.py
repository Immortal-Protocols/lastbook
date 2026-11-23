#!/usr/bin/env python3
"""content/emergency/<CC>.json: every number names its source and the day it was checked (format: content/emergency/SCHEMA.md).

  python3 -B -m unittest app.tests.test_emergency_numbers

Two parts: the real files are checked, and the checker itself is shown to fail on a row with no source, no date or a
number that is not a number, so a passing run means something.
"""
import copy, json, os, re, sys, unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.dont_write_bytecode = True
DIR = Path(__file__).resolve().parents[2] / 'content' / 'emergency'

KINDS = {'general', 'ambulance', 'fire', 'police', 'poison', 'crisis', 'other'}
HOW = {'call', 'sms', 'chat', 'app'}
WORKS_FROM = {'mobile', 'landline', 'voip'}
VERIFIED = {'official', 'found_online'}
NUMBER = re.compile(r'^[+*]?[0-9][0-9 ]*$')
CALLING_CODE = re.compile(r'^\+[0-9]{1,4}$')
SOURCE = re.compile(r'^https?://[^\s/]+\.[^\s/]+\S*$')


# The last day a number in content/emergency/ may be dated. The real files are checked against this day, not against the
# computer's clock, so the result is the same on every machine and every day, even where the clock or the time zone is
# off. Whoever adds or re-checks a number sets it to that day, in the same change. A row dated after it fails.
REFERENCE_DATE = date(2026, 11, 22)


def latest_checked_date(now=None):
    """The latest day a number can honestly say it was checked on: today's date in the earliest time zone on Earth
    (UTC+14), from the clock in UTC. A person in Chile or Europe may check a number after their midnight while a machine
    behind them is still on the day before, so the machine's own date would call that "the future" and fail. A day more
    than that is the future everywhere."""
    now = now or datetime.now(timezone.utc)
    return (now.astimezone(timezone.utc) + timedelta(hours=14)).date()


def source(x):
    return isinstance(x, str) and bool(SOURCE.match(x))


def words(x):
    return isinstance(x, list) and bool(x) and all(isinstance(w, str) and w.strip() and w == w.lower() for w in x)


def problems(data, name, latest=None):
    """What is wrong with one country's table, as a list of plain lines. Empty when it is sound. `latest` is the last
    day a check may be dated (default: latest_checked_date()); the tests below give it a fixed day."""
    latest = latest or latest_checked_date()
    out = []
    code = name[:-5] if name.endswith('.json') else name
    if not re.fullmatch(r'[A-Z]{2}', code):
        out.append(f'{name}: the file name must be the two-letter country code in capitals, such as CL.json')
    if data.get('code') != code:
        out.append(f'{name}: "code" is {data.get("code")!r}, but the file name says {code!r}')
    if not isinstance(data.get('country'), str) or not data['country'].strip():
        out.append(f'{name}: "country" is missing')
    if not CALLING_CODE.match(str(data.get('calling_code', ''))):
        out.append(f'{name}: "calling_code" must be + and digits, such as +56')
    services = data.get('services')
    if not isinstance(services, list) or not services:
        return out + [f'{name}: "services" must list at least one number']
    numbers = set()
    for i, s in enumerate(services):
        who = f'{name} services[{i}] ({s.get("name", "?") if isinstance(s, dict) else "?"})'
        if not isinstance(s, dict):
            out.append(f'{who}: not an object')
            continue
        if s.get('kind') not in KINDS:
            out.append(f'{who}: "kind" {s.get("kind")!r} is not one of {sorted(KINDS)}')
        if not isinstance(s.get('name'), str) or not s['name'].strip():
            out.append(f'{who}: "name" is missing')
        n = s.get('number')
        if not isinstance(n, str) or not NUMBER.match(n):
            out.append(f'{who}: "number" must be digits and spaces only (a leading + or * is allowed): {n!r}')
        else:
            numbers.add(n)
        v = s.get('how')
        if not isinstance(v, list) or not v or not set(v) <= HOW:
            out.append(f'{who}: "how" must be a non-empty list from {sorted(HOW)}')
        v = s.get('works_from')   # empty: the source does not say
        if not isinstance(v, list) or not set(v) <= WORKS_FROM:
            out.append(f'{who}: "works_from" must be a list from {sorted(WORKS_FROM)}, empty if the source does not say')
        k = s.get('keywords')
        if not isinstance(k, dict) or not words(k.get('local')) or not words(k.get('en')):
            out.append(f'{who}: "keywords" needs lower-case "local" and "en" word lists')
        # Each claim about how the number can be reached has its own source, so an editor can check it alone.
        if s.get('works_from') and not source(s.get('works_from_source')):
            out.append(f'{who}: "works_from" is listed, so "works_from_source" must be the address of the page that says so')
        if 'free' not in s or s['free'] not in (True, False, None):
            out.append(f'{who}: "free" must be true, false or null (null: the sources do not say)')
        elif s['free'] is not None and not source(s.get('free_source')):
            out.append(f'{who}: "free" is {str(s["free"]).lower()}, so "free_source" must be the address of the page that says so')
        if not isinstance(s.get('when'), str):
            out.append(f'{who}: "when" must be a string (empty if there is nothing to add)')
        if not source(s.get('source')):
            out.append(f'{who}: "source" must be the web address of the page the number was read from')
        if 'url' in s and not source(s['url']):
            out.append(f'{who}: "url" is optional, but when present it must be the web address of the service\'s own page')
        c = s.get('checked_on')
        try:
            d = date.fromisoformat(c)
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', c):
                raise ValueError
            if d > latest:
                out.append(f'{who}: "checked_on" {c} is after the last allowed day, {latest}')
        except (TypeError, ValueError):
            out.append(f'{who}: "checked_on" must be a date as YYYY-MM-DD')
        if s.get('verified') not in VERIFIED:
            out.append(f'{who}: "verified" must be one of {sorted(VERIFIED)}')
    g = data.get('general')
    if g is not None and g not in numbers:
        out.append(f'{name}: "general" is {g!r}, which is not the number of any service')
    return out


class Files(unittest.TestCase):
    def check_all(self, latest):
        files = sorted(DIR.glob('*.json'))
        self.assertTrue(files, 'no country files in content/emergency/')
        for f in files:
            with self.subTest(f.name):
                data = json.loads(f.read_text(encoding='utf-8'))
                self.assertEqual(problems(data, f.name, latest=latest), [])

    def test_every_file_is_sound(self):
        """Against the fixed REFERENCE_DATE: needs no right clock."""
        self.check_all(REFERENCE_DATE)

    @unittest.skipUnless(os.environ.get('LASTBOOK_CHECK_CLOCK') == '1',
                         "off by default: it trusts the clock of this computer; set LASTBOOK_CHECK_CLOCK=1 to run it")
    def test_no_file_is_dated_in_the_future_by_the_clock(self):
        """Against the computer's own clock (UTC+14 rule): catches a date later than the day it really is, which the
        fixed REFERENCE_DATE cannot. Only as right as the clock of the computer that runs it."""
        self.check_all(latest_checked_date())

    def test_the_reference_date_is_not_older_than_the_data(self):
        """Raising a row's date past REFERENCE_DATE fails the test above; this says why, in plain words."""
        newest = max(date.fromisoformat(s['checked_on']) for f in DIR.glob('*.json')
                     for s in json.loads(f.read_text(encoding='utf-8'))['services'])
        self.assertLessEqual(newest, REFERENCE_DATE, 'a number is dated after REFERENCE_DATE: set REFERENCE_DATE to that day')


class Checker(unittest.TestCase):
    GOOD = {
        'country': 'Springfield', 'code': 'ZZ', 'calling_code': '+99', 'general': '911',
        'services': [{
            'kind': 'general', 'name': 'Emergency', 'number': '911', 'how': ['call'],
            'works_from': ['mobile', 'landline'], 'keywords': {'local': ['emergencia'], 'en': ['emergency']},
            'works_from_source': 'https://example.org/dialling', 'free': True, 'free_source': 'https://example.org/costs',
            'when': '', 'source': 'https://example.org/numbers', 'checked_on': '2026-11-01', 'verified': 'official'}],
    }

    def bad(self, **change):
        d = copy.deepcopy(self.GOOD)
        for k, v in change.items():
            if k.startswith('s_'):
                d['services'][0][k[2:]] = v
            else:
                d[k] = v
        return problems(d, 'ZZ.json', latest=date(2026, 11, 22))

    def test_a_sound_table_passes(self):
        self.assertEqual(problems(self.GOOD, 'ZZ.json', latest=date(2026, 11, 22)), [])

    def test_no_source_fails(self):
        self.assertTrue(self.bad(s_source=''))
        self.assertTrue(self.bad(s_source='not an address'))
        d = copy.deepcopy(self.GOOD)
        del d['services'][0]['source']
        self.assertTrue(problems(d, 'ZZ.json'))

    def test_no_date_fails(self):
        d = copy.deepcopy(self.GOOD)
        del d['services'][0]['checked_on']
        self.assertTrue(problems(d, 'ZZ.json'))
        self.assertTrue(self.bad(s_checked_on='yesterday'))
        self.assertTrue(self.bad(s_checked_on='2026-13-01'))
        self.assertTrue(self.bad(s_checked_on='20261101'))

    def test_a_date_in_the_future_fails(self):
        self.assertFalse(self.bad(s_checked_on='2026-11-22'))   # the last day allowed
        self.assertTrue(self.bad(s_checked_on='2026-11-23'))    # one day past it
        self.assertTrue(self.bad(s_checked_on='2026-12-01'))

    def test_the_last_day_allowed_is_the_same_whatever_the_machine_clock_says(self):
        """Fixed moments, not the real clock. 10:00 UTC is midnight in UTC+14: from then on, that next day has begun
        somewhere, so a number checked there may carry it; one minute earlier it has not."""
        utc = timezone.utc
        for now, day in ((datetime(2026, 11, 21, 9, 59, tzinfo=utc), date(2026, 11, 21)),
                         (datetime(2026, 11, 21, 10, 0, tzinfo=utc), date(2026, 11, 22)),
                         (datetime(2026, 11, 21, 23, 59, tzinfo=utc), date(2026, 11, 22)),
                         (datetime(2026, 11, 22, 0, 0, tzinfo=utc), date(2026, 11, 22)),
                         (datetime(2026, 11, 22, 9, 59, tzinfo=timezone(timedelta(hours=-11))), date(2026, 11, 23))):
            with self.subTest(now=now.isoformat()):
                self.assertEqual(latest_checked_date(now), day)

    def test_a_number_that_is_not_a_number_fails(self):
        for n in ('', 'call 911', '9-1-1', '911.', None, 911):
            with self.subTest(n):
                self.assertTrue(self.bad(s_number=n))
        self.assertFalse(self.bad(s_number='+56 2 2635 3800', general=None))
        self.assertFalse(self.bad(s_number='*4141', general=None))

    def test_a_claim_without_its_own_source_fails(self):
        self.assertTrue(self.bad(s_works_from_source=''))
        self.assertTrue(self.bad(s_free_source=None))
        self.assertTrue(self.bad(s_free='yes'))
        d = copy.deepcopy(self.GOOD)
        del d['services'][0]['free']
        self.assertTrue(problems(d, 'ZZ.json'))

    def test_url_is_optional_but_must_be_an_address(self):
        self.assertFalse(self.bad())
        self.assertFalse(self.bad(s_url='https://example.org/service'))
        for v in ('', None, 'not an address', 5):
            self.assertTrue(self.bad(s_url=v), v)

    def test_a_claim_left_unknown_needs_no_source(self):
        self.assertFalse(self.bad(s_works_from=[], s_works_from_source=None, s_free=None, s_free_source=None))
        self.assertFalse(self.bad(s_free=False))

    def test_unknown_words_fail(self):
        self.assertTrue(self.bad(s_kind='hospital'))
        self.assertTrue(self.bad(s_verified='probably'))
        self.assertTrue(self.bad(s_how=['pigeon']))
        self.assertTrue(self.bad(s_works_from=['telepathy']))
        self.assertTrue(self.bad(s_how=[]))
        self.assertFalse(self.bad(s_works_from=[]))

    def test_the_file_name_must_match_the_code(self):
        self.assertTrue(problems(self.GOOD, 'zz.json', latest=date(2026, 11, 22)))
        self.assertTrue(problems(self.GOOD, 'YY.json', latest=date(2026, 11, 22)))

    def test_general_must_be_a_listed_number(self):
        self.assertTrue(self.bad(general='112'))

    def test_keywords_need_both_languages_in_lower_case(self):
        self.assertTrue(self.bad(s_keywords={'local': ['Emergencia'], 'en': ['emergency']}))
        self.assertTrue(self.bad(s_keywords={'local': ['emergencia']}))


if __name__ == '__main__':
    unittest.main()
