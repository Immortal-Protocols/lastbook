"""Proves scan_pack.py and build_packs.py on a scratch copy of a sample pack. Never packaged, and nothing is written outside the work folder.

  python -I -B test_pack_tools.py <sample pack> <work folder> [--pages N]

Each control runs the real scan as its own process and reads its exit code and report:
  plants     one sample of each forbidden thing, and benign look-alikes that must not fail
  no pass    a scan that crashed, or read nothing, or was given nothing to look for, must exit 1
  real pages untouched saved pages fail and their stripped copies pass
  words      words, local images and links on pages parsed the same way with and without stripping
  builder    the stripper on small cases, and what the build would put in Small and Medium from the snapshot, without building
Exit 1 if any control does not come out as expected.
"""
import argparse
import hashlib
import html
import importlib.util
import json
import os
import shutil
import sqlite3
import struct
import subprocess
import sys
import zlib
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
LIB = PROJECT / 'library-data'
WORD = 'ZZprivatewordZZ'
EVIL = 'https://evil.example/x'
SHIP_EDITS = json.loads((HERE / 'ship_edits.json').read_text(encoding='utf-8'))
HOME = next(w for w in SHIP_EDITS['forbidden'] if w.isalpha())     # a household word, read from the list so that it is never written here


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scan_pack = load('scan_pack')
build_packs = load('build_packs')
saved_pages = build_packs.load_saved_pages()
SPEC = build_packs.SPEC
OK = FAILED = 0


def result(name, good, detail=''):
    global OK, FAILED
    OK, FAILED = OK + good, FAILED + (not good)
    print(f"{'ok  ' if good else 'MISS'} {name}{'  ' + detail if detail else ''}", flush=True)


class Work:
    def __init__(self, sample, folder):
        self.sample, self.folder = Path(sample), Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.terms = self.folder / 'terms.txt'
        self.terms.write_text((PROJECT / 'derived/packs/private-terms.txt').read_text(encoding='utf-8') + WORD + '\n', encoding='utf-8')
        self.accepted = self.folder / 'accepted.tsv'
        self.n = 0

    def copy(self):
        """A fresh clone of the base pack."""
        self.n += 1
        dest = self.folder / f'c{self.n}'
        if dest.exists():
            shutil.rmtree(dest)
        subprocess.run(['cp', '-cR', str(self.base), str(dest)], check=True)
        return dest

    def scan(self, pack, terms=None, accepted=None):
        report = self.folder / f'report{self.n}.json'
        if report.exists():
            report.unlink()
        args = [sys.executable, '-I', '-B', str(HERE / 'scan_pack.py'), str(pack), '--terms', str(terms or self.terms), '--accepted', str(accepted or self.accepted), '--report', str(report)]
        p = subprocess.run(args, capture_output=True, text=True)
        rep = json.loads(report.read_text(encoding='utf-8')) if report.exists() else None
        return p.returncode, rep, p.stdout + p.stderr


def page(body, head=''):
    return f'<!doctype html><html><head><title>t</title>{head}</head><body>{body}</body></html>'.encode()


HTML_PLANTS = [
    ('script element', page('<script>alert(1)</script>'), 'html.element.script'),
    ('SCRIPT in mixed case', page('<ScRiPt>alert(1)</sCrIpT>'), 'html.element.script'),
    ('script with a slash for a space', page('<script/src=x.js></script>'), 'html.element.script'),
    ('script hidden after an empty comment', page('<!--><script>alert(1)</script>-->'), 'html.element.script'),
    ('script after a comment ending --!>', page('<!-- x --!><script>alert(1)</script>'), 'html.element.script'),
    ('script inside noscript', page('<noscript><script>x</script></noscript>'), 'html.element.script'),
    ('script inside svg title', page('<svg><title><script>x</script></title></svg>'), 'html.element.script.in_raw_text'),
    ('event attribute', page('<img src=a.png onerror=x>'), 'html.event_attribute'),
    ('event attribute in capitals', page('<IMG SRC=a.png ONERROR=x>'), 'html.event_attribute'),
    ('event attribute after a slash', page('<svg/onload=x>'), 'html.event_attribute'),
    ('event attribute with no space after a quote', page('<img src="a.png"onerror=x>'), 'html.event_attribute'),
    ('javascript link', page('<a href="javascript:x()">a</a>'), 'html.script_link'),
    ('javascript link in entities', page('<a href="jav&#x61;script&colon;x()">a</a>'), 'html.script_link'),
    ('javascript link with a tab inside', page('<a href="java\tscript:x()">a</a>'), 'html.script_link'),
    ('javascript link with leading spaces', page('<a href="  \x01javascript:x()">a</a>'), 'html.script_link'),
    ('JAVASCRIPT link in capitals', page('<a href="JaVaScRiPt:x()">a</a>'), 'html.script_link'),
    ('vbscript link', page('<a href="vbscript:x">a</a>'), 'html.script_link'),
    ('data link', page('<a href="data:text/html,x">a</a>'), 'html.script_link'),
    ('remote image', page(f'<img src="{EVIL}">'), 'html.remote_url'),
    ('remote image in capitals', page('<img src="HTTPS://EVIL.EXAMPLE/x">'), 'html.remote_url'),
    ('remote image in entities', page('<img src="&#104;ttps://evil.example/x">'), 'html.remote_url'),
    ('remote image with no quotes', page('<img src=https://evil.example/x>'), 'html.remote_url'),
    ('protocol-relative image', page('<img src="//evil.example/x">'), 'html.remote_url'),
    ('protocol-relative with backslashes', page(r'<img src="\\evil.example\x">'), 'html.remote_url'),
    ('slash then backslash', page(r'<img src="/\evil.example/x">'), 'html.remote_url'),
    ('data page as an image', page('<img src="data:text/html,x">'), 'html.remote_url'),
    ('poster', page(f'<video poster="{EVIL}"></video>'), 'html.remote_url'),
    ('background attribute', page(f'<table background="{EVIL}"></table>'), 'html.remote_url'),
    ('video source', page(f'<video><source src="{EVIL}"></video>'), 'html.remote_url'),
    ('remote track', page(f'<video><track src="{EVIL}"></video>'), 'html.remote_url'),
    ('srcset', page(f'<img src=a.png srcset="a.png 1x, {EVIL} 2x">'), 'html.remote_srcset'),
    ('srcset with no spaces', page('<img srcset="a.png 1x,//evil.example/x 2x">'), 'html.remote_srcset'),
    ('srcset in entities', page('<img srcset="&#104;ttp://evil.example/x 2x">'), 'html.remote_srcset'),
    ('imagesrcset on a link', page('', f'<link rel=stylesheet href=a.css imagesrcset="{EVIL} 2x">'), 'html.remote_srcset'),
    ('remote iframe', page(f'<iframe src="{EVIL}"></iframe>'), 'html.element.iframe'),
    ('iframe with no address', page('<iframe srcdoc="x"></iframe>'), 'html.element.iframe'),
    ('remote frame', page(f'<frameset><frame src="{EVIL}"></frameset>'), 'html.element.frame'),
    ('object', page('<object data="a.swf"></object>'), 'html.element.object'),
    ('embed', page('<embed src="a.swf">'), 'html.element.embed'),
    ('applet', page('<applet code=x></applet>'), 'html.element.applet'),
    ('base href', page('', '<base href="https://evil.example/">'), 'html.base_href'),
    ('remote stylesheet', page('', f'<link rel=stylesheet href="{EVIL}">'), 'html.element.link'),
    ('preload link', page('', '<link rel=preload href=a.js>'), 'html.element.link'),
    ('dns-prefetch link', page('', '<link rel=dns-prefetch href="//evil.example">'), 'html.element.link'),
    ('meta refresh', page('', f'<meta http-equiv=refresh content="0;url={EVIL}">'), 'html.element.meta'),
    ('meta refresh in capitals', page('', f'<META HTTP-EQUIV="REFRESH" CONTENT="0;url={EVIL}">'), 'html.element.meta'),
    ('meta set-cookie', page('', '<meta http-equiv=set-cookie content="a=b">'), 'html.element.meta'),
    ('form action', page(f'<form action="{EVIL}"></form>'), 'html.attr.action'),
    ('button formaction', page(f'<button formaction="{EVIL}"></button>'), 'html.attr.formaction'),
    ('a ping', page(f'<a href="#x" ping="{EVIL}">a</a>'), 'html.attr.ping'),
    ('html manifest', b'<!doctype html><html manifest="a.appcache"><body>x</body></html>', 'html.attr.manifest'),
    ('codebase', page(f'<div codebase="{EVIL}"></div>'), 'html.attr.codebase'),
    ('data attribute with an address', page(f'<div data-src="{EVIL}"></div>'), 'html.data_attribute'),
    ('data attribute protocol-relative', page('<div data-src="//evil.example/x"></div>'), 'html.data_attribute'),
    ('svg image href', page(f'<svg><image href="{EVIL}"/></svg>'), 'html.remote_href'),
    ('svg use xlink:href', page(f'<svg><use xlink:href="{EVIL}"/></svg>'), 'html.remote_href'),
    ('svg animate to an address', page(f'<svg><image><animate attributeName=href to="{EVIL}"/></image></svg>'), 'html.animated_url'),
    ('style @import', page('<style>@import "a.css";</style>'), 'css.import'),
    ('style @IMPORT in capitals', page('<style>@IMPORT "a.css";</style>'), 'css.import'),
    ('style @import in css escapes', page(r'<style>@\69 mport "a.css";</style>'), 'css.import'),
    ('style url', page(f'<style>a{{background:url({EVIL})}}</style>'), 'css.remote_url'),
    ('style URL in capitals with quotes', page('<style>a{background:URL( "//evil.example/x" )}</style>'), 'css.remote_url'),
    ('style url in css escapes', page(r'<style>a{background:u\72 l(https://evil.example/x)}</style>'), 'css.remote_url'),
    ('style url with a comment in it', page('<style>a{background:/**/url(/**/https://evil.example/x)}</style>'), 'css.remote_url'),
    ('style image-set string', page(f'<style>a{{background:image-set("{EVIL}" 1x)}}</style>'), 'css.remote_url'),
    ('style attribute url', page(f'<div style="background:url({EVIL})"></div>'), 'css.remote_url'),
    ('style attribute in entities', page('<div style="background:url(&#104;ttps://evil.example/x)"></div>'), 'css.remote_url'),
    ('script after a style that closes oddly', page('<style>a{}</style x><script>y</script>'), 'html.element.script'),
    ('comment', page('<!-- a note -->'), 'html.comment'),
    ('processing instruction', page('<?php x ?>'), 'html.processing_instruction'),
    ('private word', page(f'hello {WORD}'), 'term.html'),
    ('private word in another case', page(f'hello {WORD.lower()}'), 'term.html'),
    ('private word in entities', page('hello &#90;Zprivatewordzz'), 'term.html'),
    ('private word in an attribute', page(f'<img alt="{WORD}" src=a.png>'), 'term.html'),
    ('UTF-16 page', '<html><body>x</body></html>'.encode('utf-16'), 'html.utf16'),
    ('gallery the served repair would turn into a remote image', page(f'<div class="image-gallery" data-base-url=""><a href="{EVIL}">x</a></div>'), 'served.html.remote_url'),
    ('web link', page(f'<a href="{EVIL}">source</a>'), 'html.web_anchor'),
    ('web link on area', page(f'<map name=m><area href="{EVIL}"></map>'), 'html.web_anchor'),
    ('protocol-relative link', page('<a href="//evil.example/x">a</a>'), 'html.web_anchor'),
    ('file link', page('<a href="file:///C:/Users/someone/x.html">a</a>'), 'html.non_web_link'),
    ('ftp link', page('<a href="ftp://evil.example/x">a</a>'), 'html.non_web_link'),
    ('mailto link', page('<a href="mailto:x@evil.example">a</a>'), 'html.non_web_link'),
    ('a mangled address', page('<a href="nk: https://evil.example/">a</a>'), 'html.non_web_link'),
    ('link to a page not in the pack', page('<a href="absent.html">a</a>'), 'page.dead_reference'),
    ('image with no source', page('<p>words<img alt="a picture">more words</p>'), 'html.image_with_no_source'),
    ('image with an empty source', page('<img src="" alt="x">'), 'html.image_with_no_source'),
    ('image with a source of spaces', page('<img src="  " srcset="">'), 'html.image_with_no_source'),
    ('household word in a page', page(f'<p>near {HOME.title()} beach</p>'), 'term.household'),
    ('household word in entities', page(f'<p>&#{ord(HOME[0].upper())};{HOME[1:]}</p>'), 'term.household'),
    ('link to the removed library home', page('<a href="../../index.html">a</a>'), 'page.dead_reference'),
    ('picture source not in the pack', page('<picture><source srcset="/articles/x.jpg?w=1"><img src="data:image/png;base64,AAAA"></picture>'), 'page.dead_reference'),
    ('image not in the pack', page('<img src="absent.png">'), 'page.dead_reference'),
]

MUST_PASS = [
    ('link to a file in the pack, wrong case and with a fragment', page('<a href="A.PNG#x">a</a>')),
    ('link within the page', page('<a href="#x">a</a>')),
    ('local image', page('<img src="a.png" srcset="a.png 1x, b.png 2x">')),
    ('inline picture', page('<img src="data:image/png;base64,AAAA">')),
    ('a word by chance inside an inline picture', page(f'<img src="data:image/png;base64,AAA{WORD}AAA">')),
    ('alt and title that look like addresses', page('<img src=a.png alt="https://x.example/" title="Note: see //this">')),
    ('meta content with an address', page('', '<meta property="og:image" content="https://x.example/a.png">')),
    ('words about scripts', page('<pre>&lt;script src="https://x.example"&gt;</pre> a &lt; b, 1 < 2')),
    ('local stylesheet', page('', '<link rel=stylesheet href="../a.css">')),
    ('local frame and base target', page('<frameset><frame src="a.htm"></frameset>', '<base target="main">')),
    ('local iframe', page('<iframe src="a.html"></iframe>')),
    ('local track', page('<video><track src="a.vtt"></video>')),
    ('svg namespace address', page('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"><use xlink:href="#a"/></svg>')),
    ('drawer the repair rewrites', page('<button data-toggle="offcanvas" data-target="#x">m</button>')),
    ('microdata addresses, inert', page('<div itemscope itemtype="https://schema.org/Article"></div>')),
    ('a bare anchor, a target for a link within the page', page('<a name="x" id="y">words</a>')),
    ('image with a source only in srcset', page('<img srcset="a.png 1x">')),
]

CSS_PLANTS = [
    ('css file @import', '@import url(a.css);', 'css.import'),
    ('css file remote url', f'a{{background:url({EVIL})}}', 'css.remote_url'),
    ('css file protocol-relative', 'a{background:url(//evil.example/x)}', 'css.remote_url'),
    ('css file escaped', r'a{background:\75rl(https://evil.example/x)}', 'css.remote_url'),
    ('css file private word', f'/* {WORD} */', 'term.css'),
]

SVG_PLANTS = [
    ('svg file script', '<svg><script>x</script></svg>', 'svg.script'),
    ('svg file SCRIPT in capitals', '<svg><SCRIPT>x</SCRIPT></svg>', 'svg.script'),
    ('svg file event', '<svg onload="x"></svg>', 'svg.event_attribute'),
    ('svg file foreignObject', '<svg><foreignObject>x</foreignObject></svg>', 'svg.foreign_object'),
    ('svg file external href', f'<svg><image href="{EVIL}"/></svg>', 'svg.external_href'),
    ('svg file protocol-relative xlink', '<svg><use xlink:href="//evil.example/x"/></svg>', 'svg.external_href'),
    ('svg file href in entities', '<svg><image href="&#104;ttps://evil.example/x"/></svg>', 'svg.external_href'),
    ('svg file style url', f'<svg><style>a{{fill:url({EVIL})}}</style></svg>', 'svg.css.remote_url'),
    ('svg file entity', '<!DOCTYPE svg [<!ENTITY x SYSTEM "https://evil.example/">]><svg>&x;</svg>', 'svg.entity'),
    ('svg file private word', f'<svg><title>{WORD}</title></svg>', 'term.svg'),
]


def pdf_with(obj_text, compressed=False):
    if compressed:
        body = zlib.compress(obj_text)
        return b'%%PDF-1.5\n1 0 obj\n<</Type/ObjStm/Filter/FlateDecode/N 1/First 4/Length %d>>\nstream\n' % len(body) + body + b'\nendstream\nendobj\ntrailer<<>>\n%%EOF\n'
    return b'%PDF-1.4\n1 0 obj\n' + obj_text + b'\nendobj\ntrailer<<>>\n%%EOF\n'


PDF_PLANTS = [
    ('pdf /JavaScript', pdf_with(b'<</S/JavaScript/JS(x)>>'), 'pdf.javascript'),
    ('pdf /JavaScript in an object stream', pdf_with(b'<</S/JavaScript/JS(x)>>', True), 'pdf.javascript'),
    ('pdf /J#61vaScript written with an escape', pdf_with(b'<</S/J#61vaScript>>'), 'pdf.javascript'),
    ('pdf action whose type is held elsewhere', pdf_with(b'<</S 5 0 R/JS 3 0 R>>\n5 0 obj\n/JavaScript\nendobj'), 'pdf.javascript'),
    ('pdf /JS alone, as in a text setting', pdf_with(b'<</BTFN(Kozuka)>>/JS 0/KF<</BTFN()>>'), None),
    ('pdf /Launch', pdf_with(b'<</S/Launch/F(a.exe)>>'), 'pdf.launch'),
    ('pdf /Launch in an object stream', pdf_with(b'<</S/Launch/F(a.exe)>>', True), 'pdf.launch'),
    ('pdf /SubmitForm', pdf_with(b'<</S/SubmitForm/F(https://evil.example/)>>'), 'pdf.submitform'),
    ('pdf /ImportData', pdf_with(b'<</S/ImportData>>'), 'pdf.importdata'),
    ('pdf /GoToE', pdf_with(b'<</S/GoToE>>'), 'pdf.gotoe'),
    ('pdf /RichMedia', pdf_with(b'<</Subtype/RichMedia>>'), 'pdf.richmedia'),
    ('pdf /XFA', pdf_with(b'<</XFA 3 0 R>>'), 'pdf.xfa'),
    ('pdf /EmbeddedFile', pdf_with(b'<</Type/EmbeddedFile/Length 1>>'), 'pdf.embeddedfile'),
    ('pdf private word in Info', pdf_with(b'<</Author(' + WORD.encode() + b')>>'), 'term.pdf'),
    ('pdf private word in an object stream', pdf_with(b'<</Author(' + WORD.encode() + b')>>', True), 'term.pdf'),
    ('pdf web link', pdf_with(b'<</S/URI/URI(https://evil.example/a\\)b)>>'), 'pdf.web_link'),
    ('pdf web link in hex', pdf_with(b'<</S/URI/URI <68747470733a2f2f>>>'), 'pdf.web_link'),
    ('pdf web link in an object stream', pdf_with(b'<</S/URI/URI(https://evil.example/)>>', True), 'pdf.web_link'),
    ('pdf web link held elsewhere', pdf_with(b'<</S/URI/URI 5 0 R>>\n5 0 obj\n(https://evil.example/)\nendobj'), 'pdf.web_link'),
    ('pdf base address', pdf_with(b'<</URI<</Base(https://evil.example/)>>>>'), 'pdf.web_link'),
    ('pdf link with its address emptied', pdf_with(b'<</S/URI/URI()   /S/GoTo/D[1 0 R/Fit]>>'), None),
]
PDF_LINKS = [d for name, d, rule in PDF_PLANTS if rule == 'pdf.web_link']


def mp4_with(tag):
    moov = b'udta' + tag
    return struct.pack('>I4s', 16, b'ftyp') + b'isom\0\0\0\0' + struct.pack('>I4s', 8 + len(moov), b'moov') + moov + struct.pack('>I4s', 12, b'mdat') + b'data'


def plant_files(work):
    """Forbidden files, all in one pack: each is its own file, so each must be flagged by its own path."""
    pack = work.copy()
    lib = pack / 'library-data'
    expected = []

    def put(name, rel, data, rule):
        p = pack / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        expected.append((name, rel, rule))
    (lib / 'pages/control').mkdir(parents=True, exist_ok=True)
    (lib / 'pages/control/a.png').write_bytes(b'\x89PNG')
    (lib / 'pages/control/b.png').write_bytes(b'\x89PNG')
    for n, (name, data, rule) in enumerate(HTML_PLANTS):
        put(name, f'library-data/pages/control/p{n}.html', data, rule)
    for n, (name, data) in enumerate(MUST_PASS):
        put(name, f'library-data/pages/control/ok{n}.html', data, None)
    for n, (name, data, rule) in enumerate(CSS_PLANTS):
        put(name, f'library-data/courses/control/c{n}.css', data.encode(), rule)
    for n, (name, data, rule) in enumerate(SVG_PLANTS):
        put(name, f'library-data/pages/control/s{n}.svg', data.encode(), rule)
    for n, (name, data, rule) in enumerate(PDF_PLANTS):
        put(name, f'library-data/courses/control/d{n}.pdf', data, rule)
    put('video tag with a private word', 'library-data/videos/control/v.mp4', mp4_with(WORD.encode()), 'term.video_tags')
    put('video nothing names', 'library-data/videos/control/stray.mp4', mp4_with(b'x'), 'member.file_no_record_names')
    put('video with no atoms', 'library-data/videos/control/bad.mp4', b'\0\0\0\0', 'video.bad_atoms')
    put('image head with a private word', 'library-data/pages/control/i.png', b'\x89PNG' + WORD.encode(), 'term.image_head')
    put('transcript with a private word', 'library-data/transcripts/control.txt', WORD.encode(), 'term.text')
    put('vtt with a private word', 'library-data/courses/control/a.vtt', WORD.encode(), 'term.text')
    put('text with a private word', 'library-data/text/control.txt', WORD.encode(), 'term.text')
    put('text with a household word', 'library-data/text/control-home.txt', f'about {HOME.upper()}'.encode(), 'term.household')
    put('household word in a file name', f'library-data/pages/control/{HOME}-notes.html', page('x'), 'term.household')
    put('household word in a page the owner accepted by name', 'library-data/pages/control/accepted-home.html', page(f'a {HOME} street'), None)
    put('a form-posting PDF accepted only for its attachment', 'library-data/courses/control/accepted-attach.pdf',
        pdf_with(b'<</Type/EmbeddedFile>> <</S/SubmitForm/F(https://evil.example/)>>'), 'pdf.submitform')
    put('pptx with a macro', 'library-data/documents/control/m.pptx', zip_with({'ppt/vbaProject.bin': b'x'}), 'pptx.macro')
    put('pptx with a web link', 'library-data/documents/control/l.pptx', zip_with(PPTX_LINK), 'pptx.external_link')
    import io as _io, zipfile as _zf
    new, links, left = build_packs.strip_office(zip_with(PPTX_LINK))
    z = _zf.ZipFile(_io.BytesIO(new))
    result('the build takes a pptx web link out and keeps its words', (links, left) == (1, 0) and b'External' not in z.read('ppt/slides/_rels/slide1.xml.rels')
           and z.read('ppt/slides/slide1.xml') == b'<p:sld><a:r><a:rPr></a:rPr><a:t>WHO page</a:t></a:r></p:sld>', f'{links} {left}')
    stripped = [build_packs.strip_pdf(d) for d in PDF_LINKS]
    result('the build empties every PDF web link, keeping the length', all(left == 0 and n >= 1 and len(new) == len(d) and not scan_pack.PDF_ADDRESS.search(scan_pack.pdf_views(new)[0])
           and b'evil' not in scan_pack.pdf_views(new)[0] and b'6874' not in new for d, (new, n, left) in zip(PDF_LINKS, stripped)), str([(n, left) for new, n, left in stripped]))
    room = b'<</S/URI/URI(https://evil.example/' + b'x' * 400 + b')>>' + bytes(range(256)) * 4
    for squeeze in (False, True):
        body = zlib.compress(room, 9) if squeeze else zlib.compress(room, 1)
        doc = b'%%PDF-1.5\n1 0 obj\n<</Type/ObjStm/Filter/FlateDecode/N 1/First 4/Length %d>>\nstream\n' % len(body) + body + b'\nendstream\nendobj\n%EOF\n'
        new, n, left = build_packs.strip_pdf(doc)
        inner = zlib.decompress(new[doc.index(b'stream\n') + 7:doc.index(b'\nendstream')])
        result(f'an object stream keeps its length when its links are emptied ({"tight" if squeeze else "loose"})', (n, left) == (1, 0) and len(new) == len(doc)
               and inner.startswith(b'<</S/URI/URI()') and inner.rstrip(b' \n\r\t\f\0')[-1024:] == bytes(range(256)) * 4, f'{n} {left}')
    put('sign-in file', 'library-data/video-auth.json', b'{}', 'file.excluded_name')
    put('sign-in file in a folder', 'library-data/pages/control/video-auth.json', b'{}', 'file.excluded_name')
    put('cookie file', 'library-data/pages/control/cookies.txt', b'x', 'file.excluded_name')
    put('.info.json', 'library-data/videos/control/a.info.json', b'{}', 'file.excluded_name')
    put('.part', 'library-data/videos/control/a.mp4.part', b'x', 'file.excluded_name')
    put('.DS_Store', 'library-data/pages/control/.DS_Store', b'x', 'file.excluded_name')
    put('SQLite -wal', 'derived/geo/national.sqlite-wal', b'x', 'file.excluded_name')
    put('.zip', 'library-data/courses/control/a.zip', b'x', 'file.excluded_name')
    put('.description', 'library-data/videos/control/a.description', b'x', 'file.excluded_name')
    put('script file', 'library-data/courses/control/a.js', b'x', 'file.not_allowed_here')
    put('program', 'library-data/courses/control/a.exe', b'x', 'file.not_allowed_here')
    put('folder the app has no use for', 'library-data/logs/a.txt', b'x', 'file.not_allowed_here')
    put('the embedding model', 'library-data/derived/models/m.onnx', b'x', 'file.not_allowed_here')
    put('address database', 'derived/geo/addresses.sqlite', b'x', 'file.not_allowed_here')
    put('aerial photos', 'derived/geo/aerial.sqlite', b'x', 'file.not_allowed_here')
    put('lidar file', 'derived/geo/terrain-detail.sqlite', b'x', 'file.not_allowed_here')
    put('signed permission at the top', 'signed-permissions.pdf', pdf_with(b'x'), 'file.not_allowed_here')
    put('file at the top of the pack', 'extra.txt', b'x', 'file.not_allowed_here')
    put('Windows device name', 'library-data/pages/control/CON.html', page('x'), 'file.windows_refuses')
    put('name with a colon', 'library-data/pages/control/a:b.html', page('x'), 'file.windows_refuses')
    put('name ending in a dot', 'library-data/pages/control/trail..html.', page('x'), 'file.windows_refuses')
    put('very long path', 'library-data/pages/control/' + 'x' * 190 + '.html', page('x'), 'file.path_too_long')
    put('private word in a path', f'library-data/pages/control/{WORD}.html', page('x'), 'term.in_path')
    os.symlink('/etc/hosts', lib / 'pages/control/link.html')
    expected.append(('symlink', 'library-data/pages/control/link.html', 'file.symlink'))
    os.symlink(lib / 'pages', lib / 'pages/control/linkdir')
    expected.append(('linked folder', 'library-data/pages/control/linkdir', 'file.symlink'))
    (lib / 'pages/control/hard.html').write_bytes(page('x'))
    os.link(lib / 'pages/control/hard.html', lib / 'pages/control/hard2.html')
    expected.append(('hard link', 'library-data/pages/control/hard2.html', 'file.hard_link'))
    accepted = work.folder / 'accepted-with-one-page.tsv'
    accepted.write_text(work.accepted.read_text(encoding='utf-8') + 'library-data/pages/control/accepted-home.html\tcontrol only\ttest_pack_tools\tterm.household\n'
                        'library-data/courses/control/accepted-attach.pdf\tcontrol only\ttest_pack_tools\tpdf.embeddedfile\n', encoding='utf-8')
    code, rep, out = work.scan(pack, accepted=accepted)
    if rep is None:
        result('plant scan produced a report', False, out[-400:])
        return
    result('pack with plants exits 1', code == 1)
    rules = rep['rules']
    every = {}
    for rule, v in rules.items():
        for p in v['paths']:
            every.setdefault(p.split(' (word on')[0], set()).add(rule)
    for name, rel, rule in expected:
        got = every.get(rel, set())
        if rule is None:
            bad = got - {'manifest.file_not_listed'}
            result(f'must pass: {name}', not bad, ','.join(sorted(bad)))
        else:
            result(f'{name} -> {rule}', rule in got, '' if rule in got else f'got {sorted(got)}')
    return rep


PPTX_LINK = {'ppt/slides/slide1.xml': b'<p:sld><a:r><a:rPr><a:hlinkClick r:id="rId2"/></a:rPr><a:t>WHO page</a:t></a:r></p:sld>',
             'ppt/slides/_rels/slide1.xml.rels': b'<Relationships><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
                                                 b'Target="https://www.who.int/" TargetMode="External"/></Relationships>'}


def zip_with(files):
    import io
    import zipfile
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w') as z:
        for k, v in files.items():
            z.writestr(k, v)
    return b.getvalue()


def plant_each(work):
    """Forbidden things in files a pack has only one of: each gets its own scan."""
    snap = PROJECT / 'derived/packs/snapshot' / json.loads((work.base / 'pack.json').read_text(encoding='utf-8'))['snapshot']
    catalog = json.loads((snap / 'catalog.json').read_text(encoding='utf-8'))
    by = {r['id']: r for r in catalog}
    verdicts = json.loads((PROJECT / 'derived/video-review/verdicts.json').read_text(encoding='utf-8'))
    videos = [r for r in catalog if r['kind'] == 'video']

    def first(test):
        return next(r for r in videos if test(r))
    flagged = by['video--40fugwyzVU']
    dropped = first(lambda r: (verdicts.get(r['id']) or {}).get('verdict') == 'slop')
    no_verdict = first(lambda r: r['id'] not in verdicts)
    corporals = first(lambda r: r.get('publisher') == 'Corporals Corner' and (verdicts.get(r['id']) or {}).get('verdict') == 'keep')
    firearm = first(lambda r: r.get('category') == 'firearm-safety-maintenance' and r.get('publisher') != 'Corporals Corner')
    gap = next(r for r in catalog if r['path'] == 'documents/science-education/anatomy-and-physiology-2e.pdf')
    excluded = json.loads((snap / 'video-exclusions.json').read_text(encoding='utf-8'))['videos']
    removed = next((r for r in videos if r['id'] in excluded), None)

    def add_record(rec):
        def go(pack):
            f = pack / 'library-data/catalog.json'
            data = json.loads(f.read_text(encoding='utf-8'))
            data.append(rec)
            f.write_text(json.dumps(data), encoding='utf-8')
        return go

    def edit_first(change):
        def go(pack):
            f = pack / 'library-data/catalog.json'
            data = json.loads(f.read_text(encoding='utf-8'))
            change(next(r for r in data if r['kind'] in ('pdf', 'video')))
            f.write_text(json.dumps(data), encoding='utf-8')
        return go

    def edit_json(rel, change):
        def go(pack):
            f = pack / rel
            data = json.loads(f.read_text(encoding='utf-8'))
            change(data)
            f.write_text(json.dumps(data), encoding='utf-8')
        return go

    def search_sql(*sql):
        def go(pack):
            db = sqlite3.connect(pack / 'library-data/search.sqlite')
            for s in sql:
                db.execute(s)
            db.commit()
            db.close()
        return go

    def small_map(setup):
        def go(pack):
            f = pack / 'derived/geo/map.sqlite'
            f.parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(f)
            db.execute('PRAGMA journal_mode=DELETE')
            db.execute('CREATE TABLE meta(key TEXT, value TEXT)')
            for s in setup:
                db.execute(s)
            db.commit()
            db.close()
        return go

    def change_video(pack):
        data = json.loads((pack / 'library-data/catalog.json').read_text(encoding='utf-8'))
        v = next(r for r in data if r['kind'] == 'video')
        with open(pack / 'library-data' / v['path'], 'ab') as f:
            f.write(b'x')

    def change_zim(pack):
        data = json.loads((pack / 'library-data/catalog.json').read_text(encoding='utf-8'))
        z = next(r for r in data if r['kind'] == 'zim')
        p = pack / 'library-data' / z['path']
        p.unlink()
        p.write_bytes(b'not the same')

    def manifest_edit(change):
        def go(pack):
            f = pack / 'pack-manifest.tsv'
            f.write_text(change(f.read_text(encoding='utf-8')), encoding='utf-8')
        return go

    def drop_owner(pack):
        f = pack / 'library-data/documents/lastbook/sources-and-permissions.html'
        data = json.loads((pack / 'library-data/catalog.json').read_text(encoding='utf-8'))
        pub = next(r['publisher'] for r in data if r['kind'] == 'pdf')
        f.write_text(f.read_text(encoding='utf-8').replace(html.escape(pub), 'someone else'), encoding='utf-8')

    meta_row = next(r for r in json.loads((work.base / 'library-data/catalog.json').read_text(encoding='utf-8')) if r['kind'] == 'metadata')

    def edit_text(rel, change):
        def go(pack):
            f = pack / rel
            f.write_text(change(f.read_text(encoding='utf-8')), encoding='utf-8')
        return go

    def add_course(pack):
        rec = build_packs.course_records(catalog)[0]
        add_record(rec)(pack)
        home = pack / 'library-data' / rec['path']
        home.parent.mkdir(parents=True, exist_ok=True)
        home.write_bytes(page('course home'))

    def rename_back(pack):     # what a build that skipped the ID renames would leave
        f = pack / 'library-data/catalog.json'
        data = json.loads(f.read_text(encoding='utf-8'))
        old, new = next(iter(SHIP_EDITS['id_prefixes'].items()))
        r = next(r for r in data if r['kind'] == 'pdf')
        r['id'] = old + r['id']
        f.write_text(json.dumps(data), encoding='utf-8')
    cases = [
        ('flagged video in the catalog', add_record(flagged), 'member.flagged_video'),
        ('dropped video in the catalog', add_record(dropped), 'member.dropped_video'),
        ('no-verdict video in the catalog', add_record(no_verdict), 'member.no_verdict'),
        ('Corporals Corner in Small', add_record(corporals), 'member.corporals'),
        ('firearms in Small', add_record(firearm), 'member.firearms'),
        ('known-gap PDF in the catalog', add_record(gap), 'catalog.known_gap_present'),
        ('record naming an absent file', add_record({**by[next(iter(by))], 'path': 'documents/none.pdf'}), 'catalog.named_file_absent'),
        ('record not in the snapshot', add_record({'id': 'not-a-real-id', 'kind': 'pdf', 'title': 'x', 'publisher': 'x', 'path': 'reader.css'}), 'catalog.not_in_snapshot'),
        ('field outside the allow-list', edit_first(lambda r: r.update(claude_source_id='x')), 'catalog.field_not_allowed'),
        ('publisher blanked', edit_first(lambda r: r.update(publisher='')), 'credit.publisher_missing'),
        ('publisher changed', edit_first(lambda r: r.update(publisher='Someone Else')), 'credit.publisher_changed'),
        ('source address changed', edit_first(lambda r: r.update(source_url='https://other.example/')), 'credit.source_changed'),
        ('placeholder for an owner', edit_first(lambda r: r.update(publisher='See source')), 'credit.placeholder_owner'),
        ('a working name in a collection', edit_first(lambda r: r.update(collection=next(iter(SPEC['collection_renames'])))), 'term.household'),
        ('a household word in a record ID', edit_first(lambda r: r.update(id=f"{HOME}-growing-{r['id']}")), 'term.household'),
        ('a household word in a note', edit_first(lambda r: r.update(notes=f'warmer than coastal {HOME.title()}.')), 'term.household'),
        ('a record ID that keeps its old prefix', rename_back, 'term.household'),
        ('a household word in a search row', search_sql(f"INSERT INTO pages VALUES('lastbook-sources','t','{HOME} c','k','p',1,'b')"), 'term.household'),
        ('a household word in the text of a search row', search_sql(f"UPDATE pages SET body=body||' {HOME}' WHERE rowid=(SELECT min(rowid) FROM pages)"), 'term.household'),
        ('a web link left on the Sources page', edit_text('library-data/documents/lastbook/sources-and-permissions.html', lambda t: t.replace('</body>', f'<a href="{EVIL}">x</a></body>')), 'html.web_anchor'),
        ('a course record as the build makes it is not a stranger', add_course, ('not', 'catalog.not_in_snapshot')),
        ('a course record for a folder the snapshot has no records in', add_record({'id': 'course-no-such-course', 'kind': 'html', 'title': 'x', 'publisher': 'MIT OpenCourseWare', 'path': 'reader.css'}), 'catalog.not_in_snapshot'),
        ('a transcript with no video', edit_first(lambda r: (r.update(kind='transcript'), r.pop('video_path', None))), 'catalog.transcript_with_no_video'),
        ('owner missing from the Sources page', drop_owner, 'credit.owner_not_on_sources_page'),
        ('catalog with a user path', edit_first(lambda r: r.update(notes='/Users/someone/x')), 'own.user_path'),
        ('catalog with a Windows user path', edit_first(lambda r: r.update(notes='C:\\Users\\someone')), 'own.user_path'),
        ('catalog with a LAN address', edit_first(lambda r: r.update(notes='at 192.168.1.20 here')), 'own.lan_address'),
        ('catalog with a private word', edit_first(lambda r: r.update(notes=WORD)), 'term.own_json'),
        ('summary with a seventh-plus field', edit_json('library-data/summary.json', lambda d: d.update(missing_files=[])), 'summary.fields'),
        ('summary with a private word', edit_json('library-data/summary.json', lambda d: d.update(resources=WORD)), 'term.own_json'),
        ('pack.json with an unknown field', edit_json('pack.json', lambda d: d.update(built_by='x')), 'pack.field_not_allowed'),
        ('pack.json says incomplete', edit_json('pack.json', lambda d: d.update(incomplete=3)), 'pack.incomplete'),
        ('video changed after hashing', change_video, 'video.hash_differs'),
        ('ZIM changed after hashing', change_zim, 'zim.hash_differs'),
        ('search row with a private word', search_sql(f"INSERT INTO pages VALUES('lastbook-sources','t','c','k','p',1,'{WORD}')"), 'term.search'),
        ('search row of a metadata record', search_sql(f"INSERT INTO pages VALUES('{meta_row['id']}','t','c','k','p',1,'b')"), 'search.metadata_row'),
        ('search row not in the catalog', search_sql("INSERT INTO pages VALUES('no-such-doc','t','c','k','p',1,'b')"), 'search.row_not_in_catalog'),
        ('search with free pages left', search_sql('CREATE TABLE junk(x)', "INSERT INTO junk SELECT randomblob(100000) FROM pages LIMIT 200", 'DROP TABLE junk'), 'search.free_pages'),
        ('search left in WAL mode', search_sql('PRAGMA journal_mode=WAL'), 'search.not_journal_delete'),
        ('search index made with the tokenizer from before the spec kept combining marks', search_sql('CREATE TABLE keep AS SELECT doc_id,title,collection,category,path,page,body FROM pages', 'DROP TABLE pages', 'CREATE VIRTUAL TABLE pages USING fts5(doc_id UNINDEXED,title,collection,category,path UNINDEXED,page UNINDEXED,body,tokenize="unicode61")', 'INSERT INTO pages SELECT * FROM keep', 'DROP TABLE keep'), 'search.schema_differs'),
        ('map left in WAL mode', small_map(['PRAGMA journal_mode=WAL']), 'map.not_journal_delete'),
        ('map meta with a private word', small_map([f"INSERT INTO meta VALUES('source','{WORD}')"]), 'term.map'),
        ('map row replaced, its old path left in free space', small_map(['PRAGMA secure_delete=OFF', f"INSERT INTO meta VALUES('old','/Users/someone/{WORD}/survival')", "DELETE FROM meta WHERE key='old'"]), 'map.private_path_in_raw_bytes'),
        ('map done table with a private word', small_map(['CREATE TABLE done(file TEXT)', f"INSERT INTO done VALUES('/x/{WORD}')"]), 'term.map'),
        ('map source column with a private word', small_map(['CREATE TABLE resource(name TEXT, source TEXT)', f"INSERT INTO resource VALUES('a','{WORD}')"]), 'term.map'),
        ('map schema with a private word', small_map([f'CREATE TABLE {WORD}(a)']), 'term.map'),
        ('national-status with a database path', edit_json_new('derived/geo/national-status.json', {'state': 'complete', 'database': '/Users/someone/national.sqlite'}), 'own.user_path'),
        ('national-status with an extra field', edit_json_new('derived/geo/national-status.json', {'state': 'complete', 'source': 'x'}), 'status.fields'),
        ('manifest missing a file', manifest_edit(lambda s: '\n'.join(s.split('\n')[:-2]) + '\n'), 'manifest.file_not_listed'),
        ('manifest listing a file not there', manifest_edit(lambda s: s + 'library-data/none.pdf\t1\tabc\tclone\t\n'), 'manifest.listed_file_absent'),
        ('manifest with a wrong hash', manifest_edit(lambda s: s.replace('\t' + s.split('\n')[3].split('\t')[2], '\t' + '0' * 64, 1)), 'manifest.hash_differs'),
    ]
    if removed:
        cases.append(('video the owner removed', add_record(removed), 'member.owner_removed'))
    for name, go, rule in cases:
        pack = work.copy()
        go(pack)
        code, rep, out = work.scan(pack)
        got = set((rep or {}).get('rules', {}))
        if isinstance(rule, tuple):     # must not be flagged for this
            result(f'{name}: not {rule[1]}', rep is not None and rule[1] not in got, f'got {sorted(got)}')
        else:
            result(f'{name} -> {rule}', code == 1 and rule in got, '' if rule in got else f'exit {code}, got {sorted(got)} {out[-300:] if not rep else ""}')
        shutil.rmtree(pack)


def edit_json_new(rel, value):
    def go(pack):
        f = pack / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(value), encoding='utf-8')
    return go


def no_false_pass(work):
    """A scan must not pass because it crashed, read nothing or had nothing to look for."""
    folder = work.folder
    empty = folder / 'empty'
    empty.mkdir(exist_ok=True)
    only_pack = folder / 'only-pack-json'
    only_pack.mkdir(exist_ok=True)
    (only_pack / 'pack.json').write_text('{"size":"small","incomplete":0}', encoding='utf-8')
    no_words = folder / 'no-words.txt'
    no_words.write_text('# nothing\n\n', encoding='utf-8')

    def expect_fail(name, pack, terms=None):
        code, rep, out = work.scan(pack, terms=terms)
        result(name, code == 1, f'exit {code}: {out.strip().splitlines()[-1][:110] if out.strip() else ""}')
    expect_fail('no pack there', folder / 'absent')
    expect_fail('empty folder', empty)
    expect_fail('only pack.json', only_pack)
    expect_fail('terms file missing', work.base, terms=folder / 'absent.txt')
    expect_fail('terms file with no words', work.base, terms=no_words)
    for name, change in (
        ('catalog is an empty list', lambda p: (p / 'library-data/catalog.json').write_text('[]', encoding='utf-8')),
        ('catalog is not JSON', lambda p: (p / 'library-data/catalog.json').write_text('{oops', encoding='utf-8')),
        ('catalog deleted', lambda p: (p / 'library-data/catalog.json').unlink()),
        ('manifest deleted', lambda p: (p / 'pack-manifest.tsv').unlink()),
        ('manifest emptied', lambda p: (p / 'pack-manifest.tsv').write_text('path\tbytes\tsha256\thow\tchanges\n', encoding='utf-8')),
        ('manifest line too short, which crashes the scan', lambda p: (p / 'pack-manifest.tsv').write_text('path\tbytes\nlibrary-data/catalog.json\t1\n', encoding='utf-8')),
        ('search file is not a database', lambda p: (p / 'library-data/search.sqlite').write_bytes(b'garbage')),
        ('search file deleted', lambda p: (p / 'library-data/search.sqlite').unlink()),
    ):
        pack = work.copy()
        change(pack)
        expect_fail(name, pack)
        shutil.rmtree(pack)
    pack = work.copy()
    victim = next((pack / 'library-data/documents').rglob('*.pdf'))
    os.chmod(victim, 0)
    code, rep, _ = work.scan(pack)
    result('a file that cannot be read', code == 1 and 'scan.unreadable' in (rep or {}).get('rules', {}), f'exit {code}')
    os.chmod(victim, 0o644)
    shutil.rmtree(pack)
    # The scan itself made to do nothing, or to break, by patching it from outside.
    for name, patch, want in (
        ('page reader that reads nothing', 'm.Scan.inspect_html = lambda self, rel, p: None', 'scan.not_every_file_read'),
        ('every reader skipped', 'm.Scan.inspect = lambda self, rel, p: None', 'scan.not_every_file_read'),
        ('page reader that crashes', 'm.html_hits = lambda t: 1/0', 'scan.unreadable'),
        ('whole scan crashes', 'm.Scan.check_catalog = lambda self, rels: 1/0', None),
    ):
        report = folder / 'patched.json'
        if report.exists():
            report.unlink()
        code = f"""
import importlib.util as u, sys
s = u.spec_from_file_location('scan_pack', {str(HERE / 'scan_pack.py')!r}); m = u.module_from_spec(s); s.loader.exec_module(m)
{patch}
sys.exit(m.guarded_main([{str(work.base)!r}, '--terms', {str(work.terms)!r}, '--accepted', {str(work.accepted)!r}, '--report', {str(report)!r}]))
"""
        p = subprocess.run([sys.executable, '-I', '-B', '-c', code], capture_output=True, text=True)
        rules = json.loads(report.read_text(encoding='utf-8'))['rules'] if report.exists() else {}
        good = p.returncode == 1 and (want is None or want in rules)
        result(name, good, f'exit {p.returncode}' + ('' if good else ' ' + (p.stdout + p.stderr)[-300:]))


def sample_pages(n):
    """Half saved pages, half course pages, by hash so that it does not depend on folder order, plus the pages the plan named for checking."""
    def pick(top):
        found = []
        for root, _, files in os.walk(LIB / top):
            for f in files:
                if f.lower().endswith(('.html', '.htm')) and not build_packs.refused_name(f):
                    found.append(os.path.relpath(os.path.join(root, f), LIB).replace(os.sep, '/'))
        return sorted(found, key=lambda x: hashlib.sha1(x.encode()).hexdigest())
    named = ['courses/nist-sematech-statistical-handbook/handbook/apr/section2/apr215.htm', 'courses/nist-sematech-statistical-handbook/handbook/index.htm']
    pages, courses = pick('pages'), pick('courses')
    return [p for p in named if (LIB / p).exists()] + pages[:n // 2] + courses[:n // 2], len(pages), len(courses)


GONE_WITHOUT_A_TRACE = {'script', 'object', 'embed', 'applet', 'param', 'iframe', 'frame', 'link', 'meta', 'source', 'base', 'a', 'area', 'img'}   # a and img are inline: no browser shows a break where one was


def page_text(text):
    """Words, local images and links, by the scan's tokenizer, the same way for any page. A tag parts two words, except one the stripper may take out: no browser
    shows a word break where a script or a comment sat, so counting one would call the same text a loss."""
    parts, images, links = [], [], []
    depth = 0
    for t in scan_pack.tokens(text, raw=True):
        if t[0] == 'text':
            if not depth:
                parts.append(html.unescape(t[1]))
        elif t[0] in ('start', 'end'):
            if t[1] == 'head':
                depth += 1 if t[0] == 'start' else -1 if depth else 0
            if t[1] not in GONE_WITHOUT_A_TRACE:
                parts.append(' ')
            if t[0] == 'start':
                a = dict(t[2])
                if t[1] in ('img', 'image'):
                    images += [a[k] for k in ('src', 'href', 'xlink:href') if a.get(k) and not scan_pack.goes_out(a[k])]
                if t[1] in ('a', 'area') and a.get('href') and not build_packs.REMOTE.match(a['href']):     # links out go on purpose (owner decision A)
                    links.append(a['href'])
                for entry in (a.get('srcset') or '').split(','):
                    if entry.strip() and not scan_pack.goes_out(entry.split()[0]):
                        images.append(entry.split()[0])
    return ''.join(parts).split(), images, links


def compare_words(work, n):
    """Same parser both sides, on the page as saved and as served, so anything lost is the stripper's doing."""
    pages, n_saved, n_course = sample_pages(n)
    totals = Counter()
    lost_pages, gained_pages = [], []
    worst = []
    for rel in pages:
        data = (LIB / rel).read_bytes()
        if data[:2] in (b'\xff\xfe', b'\xfe\xff') or data[:512].count(b'\0') > 64:
            totals['skipped_utf16'] += 1
            continue
        new, changes, _ = build_packs.strip_page(data, saved_pages)
        if changes.get('blank_row'):
            data = saved_pages._BLANK_ROW.sub(b'', data)
            totals['pages_with_blank_rows_taken_out_first'] += 1
        for view, a, b in (('', data, new), ('served_', saved_pages.rewrite(data), saved_pages.rewrite(new))):
            wa, ia, la = page_text(a.decode('utf-8', 'replace'))
            wb, ib, lb = page_text(b.decode('utf-8', 'replace'))
            ca, cb = Counter(wa), Counter(wb)
            lost, gained = ca - cb, cb - ca
            totals[view + 'words_before'] += len(wa)
            totals[view + 'words_after'] += len(wb)
            totals[view + 'words_lost'] += sum(lost.values())
            totals[view + 'words_gained'] += sum(gained.values())
            totals[view + 'images_before'] += len(ia)
            totals[view + 'images_after'] += len(ib)
            totals[view + 'images_lost'] += sum((Counter(ia) - Counter(ib)).values())
            totals[view + 'links_before'] += len(la)
            totals[view + 'links_lost'] += sum((Counter(la) - Counter(lb)).values())
            if not view and sum(lost.values()):
                lost_pages.append((rel, sum(lost.values()), list(lost)[:12]))
            if not view and sum(gained.values()):
                gained_pages.append((rel, sum(gained.values()), list(gained)[:12]))
            if not view and sum((Counter(ia) - Counter(ib)).values()):
                worst.append((rel, sorted((Counter(ia) - Counter(ib)).elements())[:5]))
        totals['pages'] += 1
    print(json.dumps({'sample_from': {'saved_pages': n_saved, 'course_pages': n_course}, **totals}, indent=1), flush=True)
    print('pages losing words:', json.dumps(lost_pages[:30], indent=0)[:3000])
    print('pages gaining words:', json.dumps(gained_pages[:30], indent=0)[:1500])
    print('pages losing local images:', json.dumps(worst[:20], indent=0)[:1500])
    result(f"at least 200 pages compared ({totals['pages']})", totals['pages'] >= 200)
    result('no word lost', not totals['words_lost'], f"{totals['words_lost']} lost of {totals['words_before']}")
    result('no local image lost', not totals['images_lost'], f"{totals['images_lost']} lost of {totals['images_before']}")
    result('no link lost', not totals['links_lost'], f"{totals['links_lost']} lost of {totals['links_before']}")
    return pages


LEFT_TO_THE_BUILD = {'page.dead_reference'}     # only the whole build knows what a pack holds


def strip_controls():
    """What the stripper does with a reference the pack does not hold, and with a link that is not a web link."""
    dead = lambda ref: 'gone' in ref
    for name, before, after in (
        ('file link becomes text', b'<p>a <a href="file:///C:/x">t</a> b</p>', b'<p>a t b</p>'),
        ('ftp link becomes text', b'<a href="ftp://x/y">t</a>', b't'),
        ('mailto link becomes text', b'<a href="mailto:x@y">t</a>', b't'),
        ('web link becomes text', b'<p>Buy <a href="https://x/y" rel="nofollow" class="c">from <b>here</b></a>.</p>', b'<p>Buy from <b>here</b>.</p>'),
        ('web link in capitals becomes text', b'<A HREF="HTTP://x/y">t</A>', b't'),
        ('protocol-relative link becomes text', b'<a href="//x/y">t</a>', b't'),
        ('web link written with entities becomes text', b'<a href="&#104;ttps://x/y">t</a>', b't'),
        ('javascript link becomes text', b'<a href="javascript:x()">t</a>', b't'),
        ('inline-picture link becomes text', b'<a href="data:image/png;base64,AAAA">t</a>', b't'),
        ('web link that is also a target keeps its name', b'<a name="n" href="https://x/">t</a>', b'<a name="n">t</a>'),
        ('web link around a local picture leaves the picture', b'<a href="https://x/"><img src="here.png"></a>', b'<img src="here.png">'),
        ('only the end tag of the unwrapped link goes', b'<a href="https://x/">t</a> <a href="here.html">u</a>', b't <a href="here.html">u</a>'),
        ('an unclosed web link, then a live one', b'<a href="https://x/">t<a href="here.html">u</a>', b't<a href="here.html">u</a>'),
        ('web area goes', b'<map name=m><area href="https://x/" alt="a"></map>', b'<map name=m></map>'),
        ('dead link becomes text', b'<a href="gone.html#x">t</a>', b't'),
        ('live link stays', b'<a href="here.html">t</a>', b'<a href="here.html">t</a>'),
        ('link within the page stays', b'<a href="#x">t</a>', b'<a href="#x">t</a>'),
        ('bare anchor stays', b'<a name="x">t</a>', b'<a name="x">t</a>'),
        ('dead picture source goes, the image stays', b'<picture><source srcset="/gone.jpg"><img src="here.jpg"></picture>', b'<picture><img src="here.jpg"></picture>'),
        ('live picture source stays', b'<source srcset="here.jpg 1x">', b'<source srcset="here.jpg 1x">'),
        ('dead srcset entry goes, the live one stays', b'<source srcset="gone.jpg 1x, here.jpg 2x">', b'<source srcset="here.jpg 2x">'),
        ('dead image goes', b'<p><img src="gone.png"></p>', b'<p></p>'),
        ('remote image goes, its caption and words stay', b'<figure><img src="https://x/a.png" alt="a"><figcaption>Fig. 1</figcaption></figure> text', b'<figure><figcaption>Fig. 1</figcaption></figure> text'),
        ('image with no source goes', b'a<img alt="x" width=10>b', b'ab'),
        ('image with an empty source goes', b'<img src="">', b''),
        ('image left with only a live srcset stays', b'<img src="gone.png" srcset="here.png 2x">', b'<img srcset="here.png 2x">'),
        ('image with a remote src and a live srcset stays', b'<img src="https://x/a.png" srcset="here.png 1x">', b'<img srcset="here.png 1x">'),
        ('inline picture stays', b'<img src="data:image/png;base64,gone">', b'<img src="data:image/png;base64,gone">'),
    ):
        got = build_packs.strip_page(before, saved_pages, lambda r: not build_packs.REMOTE.match(r) and dead(r))[0]
        result(f'stripper: {name}', got == after, got.decode())
    web = {'https://held/a': 'pages/x y/a.html', 'https://held/gone': 'pages/gone/b.html', 'https://held/c': 'documents/claude-materials/c.pdf'}   # as the catalog maps them
    for name, before, after in (
        ('web link the library holds opens its copy', b'<a href="https://held/a#s" class="k">t</a>', b'<a href="/pages/x%20y/a.html#s" class="k">t</a>'),
        ('web link to a copy the pack does not hold becomes text', b'<a href="https://held/gone">t</a>', b't'),
        ('web link to a renamed folder opens it under its pack name', b'<a href="https://held/c">t</a>', b'<a href="/documents/materials/c.pdf">t</a>'),
        ('web link the library does not hold becomes text', b'<a href="https://held/other">t</a>', b't'),
    ):
        got = build_packs.strip_page(before, saved_pages, lambda r: not build_packs.REMOTE.match(r) and dead(r), web)[0]
        result(f'stripper: {name}', got == after, got.decode())


def builder_controls(work):
    """What the build would put in Small and Medium, from the newest snapshot and the shipped guides, without building them."""
    import re
    snap = sorted(p for p in (PROJECT / 'derived/packs/snapshot').glob('*') if (p / 'snapshot.json').exists())[-1]
    catalog = json.loads((snap / 'catalog.json').read_text(encoding='utf-8'))
    courses = build_packs.course_records(catalog)
    full = catalog + courses
    household = re.compile('|'.join(SHIP_EDITS['forbidden']), re.I)
    fields = SPEC['catalog_fields_allowed']
    guides = build_packs.guide_ids()
    gone = build_packs.gone_paths(full)
    result('the two NIST form PDFs are left out', {'courses/nist-sematech-statistical-handbook/handbook/toolaids/pff/E-Handbook.pdf', 'courses/nist-sematech-statistical-handbook/handbook/toolaids/pff/pmc.pdf'} <= gone)
    land = [r['path'] for r in catalog if r['id'].startswith('land-')]
    result(f'the land-data pages are left out ({len(land)})', len(land) == 30 and set(land) <= gone)
    result('no shipped guide card names land data', not any(g.startswith('land-') for g in guides))
    result(f"one course record per course folder with a home page ({len(courses)})", len(courses) == 27 and all(
        r['id'] == f"course-{r['path'].split('/')[1]}" and (LIB / r['path']).is_file() and r['publisher'] == 'MIT OpenCourseWare' and set(r) <= set(fields) for r in courses))
    raw_hits = sum(1 for r in catalog for v in r.values() if isinstance(v, str) and household.search(v))
    result(f'the snapshot itself has household words in its records ({raw_hits}), so the check below can see them', raw_hits > 0)
    for size in ('small', 'medium'):
        chosen, _, _ = build_packs.select(size, full, snap, 0)
        recs = [build_packs.pack_record(r, fields) for r in chosen.values() if r['kind'] != 'metadata']
        bad = [(r['id'], k) for r in recs for k, v in r.items() if isinstance(v, str) and household.search(v)]
        result(f'{size}: no household or working word in any record the pack would carry', not bad, str(bad[:4]))
        ids = {r['id'] for r in recs}
        missing = sorted(g for g in guides if g not in ids and g in {build_packs.pack_id(r['id']) for r in catalog} and next(r for r in catalog if build_packs.pack_id(r['id']) == g)['path'] not in gone
                         and next(r for r in catalog if build_packs.pack_id(r['id']) == g)['kind'] != 'video')
        result(f'{size}: every document a shipped guide card names is in the pack, by the ID the card uses', not missing, str(missing[:5]))
        result(f'{size}: no land-data record', not any(r['id'].startswith('land-') for r in recs))
        result(f'{size}: each text file named by its record\'s pack ID', all(Path(r['text_path']).stem == r['id'] for r in recs if r.get('text_path', '').startswith('text/')))
        n_courses = sum(r['id'].startswith('course-') and r['path'].endswith('/index.html') for r in recs)
        result(f'{size}: course records ({n_courses})', n_courses == (27 if size == 'medium' else 0))
        if size == 'small':
            chapters = [r for r in chosen.values() if r['path'].startswith(tuple(SPEC['sizes']['small']['with_chapters']))]
            front = next(r for r in chapters if r['id'] in {g for g in guides})
            held = {r['path'] for r in chosen.values()}
            refs = build_packs.strip_page((LIB / front['path']).read_bytes(), saved_pages)[2]
            pages = [build_packs.resolve_ref(ref, front['path']) for kind, ref in refs if kind == 'a' and not build_packs.REMOTE.match(ref)]
            pages = [t for t in pages if t and t.endswith(('.html', '.htm'))]
            result(f'small: the Water Lifting chapters are in ({len(chapters)}) and every chapter link on its contents page has its page ({len(pages)} links)', len(chapters) == 16 and pages and all(t in held for t in pages), str([t for t in pages if t not in held][:3]))
            b = build_packs.Build('control', work.folder / 'search-control', work.folder / 'search-control-build', None)
            dest = work.folder / 'search-control/library-data/search.sqlite'
            build_packs.build_search(snap, dest, recs, 'sources', b)
            db = sqlite3.connect(f'file:{dest}?immutable=1', uri=True)
            rows = db.execute('SELECT doc_id,title,collection,category,path FROM pages').fetchall()
            db.close()
            bad = [r[0] for r in rows if household.search(' '.join(map(str, r)))]
            result(f'small: search rows renamed as the catalog is ({len(rows)} rows)', rows and not bad and {r[0] for r in rows} <= ids | {SPEC['sources_page']['record']['id']}, str(bad[:3]))
            shutil.rmtree(work.folder / 'search-control')


def real_pages(work, pages):
    """Untouched real pages against their stripped copies, through the real scan."""
    pack = work.copy()
    raw_dir = pack / 'library-data/pages/control-raw'
    new_dir = pack / 'library-data/pages/control-stripped'
    raw_dir.mkdir()
    new_dir.mkdir()
    names = {}
    for n, rel in enumerate(pages):
        data = (LIB / rel).read_bytes()
        if data[:2] in (b'\xff\xfe', b'\xfe\xff') or data[:512].count(b'\0') > 64:
            continue
        new, _, _ = build_packs.strip_page(data, saved_pages)
        (raw_dir / f'{n}.html').write_bytes(data)
        (new_dir / f'{n}.html').write_bytes(new)
        names[n] = rel
    code, rep, out = work.scan(pack)
    fails_raw, fails_new, detail = set(), set(), Counter()
    for rule, v in (rep or {}).get('rules', {}).items():
        if rule.startswith(('manifest.', 'member.')) or rule in LEFT_TO_THE_BUILD:
            continue
        for p in v['paths']:
            if '/control-raw/' in p:
                fails_raw.add(p)
            elif '/control-stripped/' in p:
                fails_new.add(p.split(' (')[0])
                detail[rule] += 1
    result(f'untouched real pages fail ({len(fails_raw)} of {len(names)})', len(fails_raw) > 0, 'the rest hold nothing forbidden' if len(fails_raw) < len(names) else '')
    result(f'their stripped copies all pass ({len(names) - len(fails_new)} of {len(names)})', not fails_new, str(dict(detail)) + ' ' + str(sorted(fails_new)[:3]))
    per_page = {}
    for rule, v in rep['rules'].items():
        if not rule.startswith(('manifest.', 'member.')):
            for x in v['paths']:
                per_page.setdefault(x.split(' (')[0], set()).add(rule)
    saved = [n for n, rel in names.items() if rel.startswith('pages/')]
    n = max(saved, key=lambda k: len(per_page.get(f'library-data/pages/control-raw/{k}.html', ())))
    print(f'one real saved page: {names[n]}')
    print('  untouched fails on:', sorted(per_page.get(f'library-data/pages/control-raw/{n}.html', ())))
    print('  stripped fails on :', sorted(per_page.get(f'library-data/pages/control-stripped/{n}.html', ())))
    shutil.rmtree(pack)


def make_base(work):
    """A copy of the sample pack that passes with the owner's own scan-accepted.tsv. Anything more it needs is excused here only, in this folder, and counted as not as expected."""
    work.base = work.folder / 'base'
    if work.base.exists():
        shutil.rmtree(work.base)
    subprocess.run(['cp', '-cR', str(work.sample), str(work.base)], check=True)
    owner = (PROJECT / 'derived/packs/scan-accepted.tsv').read_text(encoding='utf-8')
    work.accepted.write_text(owner, encoding='utf-8')
    code, rep, out = work.scan(work.base)
    result("sample pack passes with the owner's scan-accepted.tsv", code == 0, str({k: v['paths'][:3] for k, v in rep['rules'].items()}) if rep else out[-300:])
    if code:
        rows = [(x, rule) for rule, v in rep['rules'].items() if rule.startswith(('pdf.', 'zim.', 'term.household')) for x in v['paths'] if ': ' not in x]   # never our own fields
        work.accepted.write_text(owner + ''.join(f'{x}\tcontrol only\ttest_pack_tools\t{rule}\n' for x, rule in sorted(set(rows))), encoding='utf-8')
        print(f'excused here only: {len(set(rows))} paths')
        code, rep, out = work.scan(work.base)
    print(out.strip()[:600])
    result('base pack passes before anything is planted', code == 0, str(sorted(rep['rules'])))
    return code == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('sample')
    ap.add_argument('work')
    ap.add_argument('--pages', type=int, default=600)
    args = ap.parse_args()
    work = Work(args.sample, args.work)
    if not make_base(work):
        print('the base pack does not pass, so the plants would prove nothing')
        return 1
    strip_controls()
    builder_controls(work)
    plant_files(work)
    plant_each(work)
    no_false_pass(work)
    pages = compare_words(work, args.pages)
    real_pages(work, pages)
    print(f'{OK} ok, {FAILED} not as expected')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
