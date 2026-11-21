"""Detailed maps outside the United States: one JSON file per region in this folder (docs/REGIONS.md).

A US state map's box comes from ZIP centres in profiles.sqlite. A region here has no ZIP centres, so its box is the
extent of an official open boundary, recorded in its file, plus the same margin the US state maps use.

  from packaging import regions          # or: sys.path.insert(0, 'packaging'); import regions
  regions.codes()                        # ['CA-BC', 'CA-ON', 'GY'] (whichever files are present)
  regions.get('CA-ON')['name']           # 'Ontario'
  regions.box('GY')                      # (w, s, e, n) with the margin added
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARGIN = .15                                       # the same margin as build_packs.state_box
CODE = re.compile(r'[A-Z]{2}(-[A-Z0-9]{1,3})?')    # ISO 3166-1 alpha-2, or ISO 3166-2 style for a subdivision
REQUIRED = ('id', 'name', 'country', 'kind', 'bbox', 'bbox_source', 'includes', 'sources')


def codes():
    return sorted(p.stem for p in HERE.glob('*.json') if CODE.fullmatch(p.stem))


def is_region(code):
    return bool(code) and CODE.fullmatch(code) is not None and (HERE / f'{code}.json').is_file()


def get(code):
    if not is_region(code):
        raise KeyError(code)
    r = json.loads((HERE / f'{code}.json').read_text(encoding='utf-8'))
    check(r, code)
    return r


def check(r, code=None):
    missing = [k for k in REQUIRED if k not in r]
    if missing:
        raise ValueError(f'{code or r.get("id")}: missing {", ".join(missing)}')
    if code is not None and r['id'] != code:
        raise ValueError(f'{code}: id is {r["id"]}')
    w, s, e, n = r['bbox']
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise ValueError(f'{r["id"]}: bad bbox {r["bbox"]}')
    return r


def box(code, margin=MARGIN):
    w, s, e, n = get(code)['bbox']
    return w - margin, s - margin, e + margin, n + margin
