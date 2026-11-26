"""Link catalogued HTML readings through the trusted browser UI, without saved-page code."""
import html
from html.parser import HTMLParser
import re
from urllib.parse import quote, urlencode, urljoin, urlsplit, unquote

MAX_PAGE = 16 * 1024 * 1024
TOKEN = re.compile(r'[0-9a-f]{32}\Z')
KINDS = {'html', 'pdf', 'video', 'transcript', 'pptx'}
RAW = {'script', 'style', 'title', 'textarea', 'xmp', 'noembed', 'noframes', 'iframe'}


def route(record, fragment=''):
    rid = quote(str(record['id']), safe='')
    if record['kind'] == 'video':
        return '#/watch/' + rid
    if record['kind'] == 'pdf':
        m = re.search(r'(?:^|&)page=([0-9]{1,7})(?:&|$)', fragment)
        page = max(1, int(m[1])) if m else 1
        return f'#/read/{rid}?p={page}&view=pdf'
    return '#/read/' + rid


def destination(href, source, catalog, file_ok):
    """Only a different supported catalog record at a local, allowed library file."""
    if not href or any(ord(c) < 32 for c in href) or '\\' in href:
        return None
    href = href.strip()
    given = urlsplit(href)
    if given.scheme or given.netloc or href.startswith('//'):
        return None
    target = urlsplit(urljoin('/' + source['path'], href))
    if re.search(r'%(?:2f|5c)', target.path, re.I):
        return None
    path = unquote(target.path).lstrip('/')
    if any(p in ('.', '..', '') for p in path.split('/')) or '\\' in path or '\0' in path:
        return None
    record = catalog['by_path'].get(path)
    if not record or record['id'] == source['id'] or record.get('kind') not in KINDS or not file_ok(path):
        return None
    return record, target.fragment


def rewrite(data, source, catalog, token, file_ok):
    """Rewrite real anchor tags only. The saved response's CSP stays unchanged.

    UTF-8 input is preserved byte for byte outside changed anchor start tags.
    Non-UTF-8, malformed or oversized input retains its ordinary saved-page path.
    """
    if not TOKEN.fullmatch(token or '') or source.get('kind') != 'html' or len(data) > MAX_PAGE:
        return data
    try:
        text = data.decode('utf-8')
    except UnicodeError:
        return data
    changes, checked = [], {}
    def checked_file(path):
        if path not in checked:
            checked[path] = file_ok(path)
        return checked[path]

    class Links(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.raw = None
            self.source_line, self.source_offset = 1, 0
            self.output_bytes = len(data)

        def handle_starttag(self, tag, attrs):
            if self.raw:
                return
            if tag in RAW:
                self.raw = tag
                return
            if tag != 'a' or len(self.get_starttag_text()) > 65536:
                return
            hrefs = [v for k, v in attrs if k == 'href']
            if len(hrefs) != 1:
                return
            found = destination(hrefs[0], source, catalog, checked_file)
            if not found:
                return
            record, fragment = found
            params = dict(source=str(source['id']), target=str(record['id']), token=token)
            if record['kind'] == 'pdf':
                params['page'] = route(record, fragment).split('?p=')[1].split('&')[0]
            link = '/ui/reading-link?' + urlencode(params)
            attrs = [(k, link if k == 'href' else v) for k, v in attrs]
            tag_text = '<a' + ''.join(' ' + k + (('="' + html.escape(v, quote=True) + '"') if v is not None else '') for k, v in attrs) + '>'
            self.output_bytes += len(tag_text.encode('utf-8')) - len(self.get_starttag_text().encode('utf-8'))
            if self.output_bytes > MAX_PAGE:
                raise ValueError('Expanded reading links exceed the page limit')
            line, col = self.getpos()
            while self.source_line < line:
                self.source_offset = text.index('\n', self.source_offset) + 1
                self.source_line += 1
            start = self.source_offset + col
            changes.append((start, start + len(self.get_starttag_text()), tag_text))

        def handle_endtag(self, tag):
            if tag == self.raw:
                self.raw = None

    try:
        parser = Links(); parser.feed(text); parser.close()
    except (ValueError, AssertionError):
        return data
    chunks, cursor = [], 0
    for start, end, replacement in changes:
        chunks.extend((text[cursor:start], replacement)); cursor = end
    chunks.append(text[cursor:])
    return ''.join(chunks).encode('utf-8')


def relay(catalog, params, file_ok, user_navigation=False):
    """A small trusted UI document. It never contains the destination's saved text."""
    if set(params) - {'source', 'target', 'token', 'page'} or not TOKEN.fullmatch(params.get('token', '')):
        return None
    source = catalog['by_id'].get(params.get('source'))
    target = catalog['by_id'].get(params.get('target'))
    if not source or source.get('kind') != 'html' or not target or target['id'] == source['id'] or target.get('kind') not in KINDS:
        return None
    if not file_ok(source['path']) or not file_ok(target['path']):
        return None
    page = params.get('page', '1')
    if not re.fullmatch('[0-9]{1,7}', page) or ('page' in params and target['kind'] != 'pdf'):
        return None
    target_route = route(target, 'page=' + page)
    values = dict(token=params['token'], source=str(source['id']), route=target_route, automatic='yes' if user_navigation else 'no')
    attrs = ''.join(' data-' + k + '="' + html.escape(v, quote=True) + '"' for k, v in values.items())
    title = html.escape(str(target['title']))
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<title>Open reading · Lastbook</title><body' + attrs + '><main><h1>' + title + '</h1>'
            '<p>Open this reading with its source details in Lastbook.</p><button id="openReading">Open reading</button>'
            '</main><script src="/ui/reading-links.js"></script></body></html>').encode('utf-8')
