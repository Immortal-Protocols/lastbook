"""Use the optional socket-free Gemma runtime to read rural directions before an offline lookup."""
import functools
import json
import re
import threading
import time
from dataclasses import replace
from decimal import Decimal
from engine import paths, pr_rural
from engine.pr_addresses import fold

CAPACITY = threading.BoundedSemaphore(1)
BUDGET = 60
TOKENS = re.compile(r'\d+(?:[.,]\d+)?|[a-z]+')
UNSAFE = re.compile(r'\b(?:entre|between|despues|antes|before|after|about|aproximadamente|salida|exit|box|casa|solar|lote|lot|apt|apto|apartamento)\b')
HINT = re.compile(r'\b(?:frente|lado|detras|junto|cerca|esq|esquina|shopping center|parque industrial)\b')
FENCE = re.compile(r'\s*\x60\x60\x60(?:json)?\s*(.*?)\s*\x60\x60\x60\s*', re.S | re.I)


@functools.lru_cache(maxsize=1)
def language():
    return json.loads((paths.APP / 'web' / 'pr-rural-language.json').read_text(encoding='utf-8'))


def fields(value):
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != 7:
        raise ValueError('expected seven fields')
    road, km, area, postal, interior, sector, landmark = value
    if type(road) is not int or not 1 <= road <= 9999 or type(interior) is not bool:
        raise ValueError('invalid route or interior')
    if not all(isinstance(s, str) and len(s) <= 250 for s in (area, postal, sector, landmark)) or not re.fullmatch(r'(?:\d{5})?', postal):
        raise ValueError('invalid qualifier')
    if isinstance(km, bool) or not re.fullmatch(r'\d{1,3}(?:[.]\d{1,3})?', str(km)):
        raise ValueError('invalid kilometer')
    return pr_rural.RuralAddress(road, int(Decimal(str(km)) * 1000), fold(area), postal, interior, fold(sector), fold(landmark))


def extract(text):
    fenced = FENCE.fullmatch(text)
    return fields(json.loads(fenced[1] if fenced else text.strip(), parse_float=Decimal))


def spelled(n, lang):
    words = language()[lang]
    if n < len(words['small']):
        return words['small'][n]
    if n < 100:
        tens = words['tens'][n // 10 - len(words['small']) // 10]
        return tens + ((' y ' if lang == 'es' else ' ') + spelled(n % 10, lang) if n % 10 else '')
    if n < 1000:
        if lang == 'es':
            base = 'cien' if n == 100 else words['hundreds'][n // 100 - 1]
        else:
            base = spelled(n // 100, lang) + ' hundred'
        return base + (' ' + spelled(n % 100, lang) if n % 100 else '')
    base = ('mil' if n < 2000 else spelled(n // 1000, lang) + ' mil') if lang == 'es' else spelled(n // 1000, lang) + ' thousand'
    return base + (' ' + spelled(n % 1000, lang) if n % 1000 else '')


def number_forms(value):
    number, _, frac = value.partition('.')
    forms = {value}
    for lang in ('es','en'):
        whole = spelled(int(number), lang)
        if not frac:
            forms.add(whole)
            continue
        suffixes = {frac, ' '.join(spelled(int(d), lang) for d in frac)}
        if not frac.startswith('0'):
            suffixes.add(spelled(int(frac), lang))
        for glue in (('punto','con') if lang == 'es' else ('point',)):
            forms.update(' '.join((a,glue,b)) for a in (number,whole) for b in suffixes)
    return forms


def eligible(query, parsed):
    raw = pr_rural.plain(query)
    if len(query) > 400 or not pr_rural.looks_rural(query) or UNSAFE.search(raw):
        return False
    markers = pr_rural.KM.findall(raw)
    return (len(markers) <= 1 and not (markers and re.search(r'[.,]', markers[0]) and pr_rural.HM.search(raw))
            and (parsed is not None or len(pr_rural.ROAD.findall(raw)) <= 1))


def grounded(query, address, parsed):
    """Every location word and both numbers must be traceable to the input. SQLite then checks geography."""
    if address is None or not eligible(query, parsed):
        return False
    raw = pr_rural.plain(query).replace('º','o').replace('°','o')
    if pr_rural.POSTAL.findall(raw) != ([address.postal] if address.postal else []):
        return False
    if bool(re.search(r'\b(?:int|interior)\b', raw)) != address.interior:
        return False
    if bool(re.search(r'\b(?:sector|sect|sec|comunidad|com)\b', raw)) != bool(address.sector):
        return False
    if bool(HINT.search(raw)) != bool(address.landmark):
        return False
    if parsed and (parsed.route, parsed.meters) != (address.route, address.meters):
        return False
    if address.sector:
        names = fold(raw)
        label = r'(?:sector|sect|sec|comunidad|com)'
        if not re.search(r'\b(?:' + label + ' ' + re.escape(address.sector) + '|' + re.escape(address.sector) + ' ' + label + r')\b', names):
            return False
    is_named = ' '.join((address.locality, address.sector, address.landmark))
    ignore = set(language()['grammar'])
    raw = pr_rural.POSTAL.sub(' ', re.sub(language()['preamble'], '', raw.strip()))
    km = f'{address.meters / 1000:.3f}'.rstrip('0').rstrip('.')
    values = [str(address.route), km]
    if parsed and pr_rural.KM.search(raw):
        # The parser accounted for these units. Keep all other numbers, including house and sector numbers.
        raw = pr_rural.HM.sub(' ', pr_rural.KM.sub(' ', raw))
        values.pop()
    source = ' ' + ' '.join(t.replace(',', '.') for t in TOKENS.findall(raw)) + ' '
    for value in values:
        options = sorted(number_forms(value), key=lambda s: (-len(s), s))
        for form in options:
            phrase = ' ' + form + ' '
            if phrase in source:
                source = source.replace(phrase, ' ', 1)
                break
        else:
            return False
    def words(text):
        return sorted(w for w in TOKENS.findall(text) if w not in ignore)
    return words(source) == words(is_named)


def validated(query, address, parsed):
    if address and address.landmark and address.locality and not HINT.search(pr_rural.plain(query)):
        # "por Cerro Gordo" can be a geographic qualifier. Keep it mandatory; the database
        # will return a result only when the combined names match the actual place.
        if re.search(r'\b(?:por|en) ' + re.escape(address.landmark) + r'\b', fold(query)):
            address = replace(address, locality=address.locality + ' ' + address.landmark, landmark='')
    return address if grounded(query, address, parsed) else None


def inference(model, query, cancelled, only_if_idle=False):
    import llm_local
    parts = []
    messages = [{'role':'system', 'content':language()['prompt']}, {'role':'user', 'content':query}]
    model.generate(llm_local.render(messages, []), 144, cancelled, parts.append, only_if_idle=only_if_idle)
    return llm_local._strip_thinking(''.join(parts))


def interpret(model, query, parsed):
    if (model is None or not eligible(query, parsed) or not model.enabled() or not model.available()
            or model.gen_lock.locked() or not CAPACITY.acquire(blocking=False)):
        return None
    done, answer = threading.Event(), []
    deadline = time.monotonic() + BUDGET
    def cancelled():
        return time.monotonic() >= deadline
    def run():
        try:
            if not model.ensure_running(cancelled=cancelled) and not cancelled():
                value = validated(query, extract(inference(model, query, cancelled, only_if_idle=True)), parsed)
                if value:
                    answer.append(value)
        except (ValueError, OSError, RuntimeError):
            pass  # An unavailable runner, invalid response or unreadable resource leaves normal lookup available.
        finally:
            CAPACITY.release()
            done.set()
    threading.Thread(target=run, daemon=True, name='map-read-rural-address').start()
    return answer[0] if done.wait(BUDGET) and answer else None


def description(a):
    km = f'{a.meters / 1000:.3f}'.rstrip('0').rstrip('.')
    return ', '.join(s for s in (f'PR-{a.route} km {km}', a.locality, a.postal, 'interior' if a.interior else '',
                                'sector ' + a.sector if a.sector else '', a.landmark) if s)
