"""Translate native wrapper, dialog and installer strings from the generated catalogues."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_catalogs = None
_locale = 'en'


def _candidates():
    here = Path(__file__).resolve().parent
    yield here / 'i18n_native.json'
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        root = Path(meipass)
        yield root / 'i18n_native.json'
        yield root / 'app' / 'i18n_native.json'


def _valid_messages(messages):
    if not isinstance(messages, dict):
        return False
    for key, value in messages.items():
        if not isinstance(key, str):
            return False
        if isinstance(value, str):
            continue
        if (not isinstance(value, dict) or not value
                or any(not isinstance(form, str) or not isinstance(text, str)
                       for form, text in value.items())):
            return False
    return True


def _valid_catalogues(candidate):
    if not isinstance(candidate, dict):
        return False
    english = candidate.get('en')
    locales = candidate.get('locales')
    return (
        _valid_messages(english)
        and isinstance(locales, dict)
        and all(isinstance(locale, str) and _valid_messages(messages)
                for locale, messages in locales.items())
    )


def load_catalogs():
    global _catalogs
    if _catalogs is None:
        last_missing = None
        invalid = []
        for path in _candidates():
            try:
                candidate = json.loads(path.read_text(encoding='utf-8'))
                if not _valid_catalogues(candidate):
                    raise ValueError('expected en and locales message catalogues')
                _catalogs = candidate
                break
            except FileNotFoundError:
                last_missing = path
            except (OSError, ValueError) as error:
                invalid.append(f'{path}: {error}')
                continue
        if _catalogs is None:
            _catalogs = {'en': {}, 'locales': {}}
            if invalid:
                print('i18n: invalid native catalogue; using source English fallback (' + '; '.join(invalid) + ')', file=sys.stderr)
            elif last_missing is not None:
                print(f'i18n: native catalogue not found (last tried {last_missing})', file=sys.stderr)
    return _catalogs


def set_locale(locale):
    global _locale
    catalogs = load_catalogs()
    if isinstance(locale, str) and (locale == 'en' or locale in catalogs.get('locales', {})):
        _locale = locale
    else:
        _locale = 'en'
    return _locale


def current_locale():
    return _locale


def interpolate(text, params):
    if not params or not text:
        return text
    # Substitute from the original message in one pass. Sequential replace calls
    # can accidentally expand placeholder-shaped text inside a parameter value.
    values = {str(name): str(value) for name, value in params.items()}
    return re.sub(r'\{([A-Za-z_][A-Za-z0-9_]*)\}',
                  lambda match: values.get(match.group(1), match.group(0)), text)


def lookup(key, locale=None):
    catalogs = load_catalogs()
    loc = _locale if locale is None else locale
    if loc != 'en':
        value = (catalogs.get('locales') or {}).get(loc, {}).get(key)
        if value:
            return value
    value = (catalogs.get('en') or {}).get(key)
    return value


def native_t(key, fallback, **params):
    """Look up a catalogue string, falling back to the English literal in the source."""
    value = lookup(key)
    if not value:
        value = fallback
    if isinstance(value, dict):
        value = value.get('other') or next(iter(value.values()), fallback)
    return interpolate(value, params)


def configure(settings_dir=None):
    """Load the saved interface language, or English if none is saved yet."""
    load_catalogs()
    locale = 'en'
    if settings_dir:
        path = Path(settings_dir) / 'ui-language.json'
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            saved = data.get('language') if isinstance(data, dict) else None
            if isinstance(saved, str) and saved:
                locale = saved
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            locale = 'en'
    return set_locale(locale)
