#!/usr/bin/env python3
"""Release gate: the manifest a build carries must validate and offer at least one library pack.

  python3 -I -B packaging/check_release_manifest.py derived/release/manifest-v1.json
  python3 -I -B packaging/check_release_manifest.py /opt/lastbook/setup/manifest-v1.json

An empty or malformed manifest is a failed release build, not a warning: a build that ships it cannot install a library.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]
from engine.setup import manifest  # noqa: E402


def main():
    if len(sys.argv) != 2:
        sys.exit(f'usage: {Path(sys.argv[0]).name} MANIFEST')
    path = Path(sys.argv[1])
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        sys.exit(f'{path}: not readable JSON ({e})')
    checked = manifest.validate(raw)
    if checked is None:
        sys.exit(f'{path}: does not pass engine/setup/manifest.validate')
    packs = [p for p in checked['packs'] if p['available'] and p['files'] and sum(f['size'] for f in p['files']) > 0]
    if not packs:
        sys.exit(f'{path}: has no downloadable library pack (an empty manifest cannot install a library)')
    models = [m for m in checked['models'] if m['available']]
    print(f'{path}: {len(packs)} downloadable packs ({", ".join(p["id"] for p in packs)}), '
          f'{len(checked["maps"])} maps, {len(checked["address_indexes"])} address indexes, '
          f'{len(models)} model(s)')


if __name__ == '__main__':
    main()
