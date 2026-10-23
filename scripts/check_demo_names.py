#!/usr/bin/env python3
"""
Check the demonstration database's invented variety names (tests/breedgraph/scenarios/demo/story.py) against variety
catalogues, so that no fictional variety shares a real one's name. Read only: it reports, and changes nothing.

The catalogues are exported by hand and kept out of git, e.g. in src/data/variety_catalogues/: the EU Plant Variety
Database (common catalogue, Triticum aestivum), the UK National List and the Irish national catalogue, as CSV or text.
Every cell of every file is read as a candidate name. A name matches when it is the same once case and punctuation
are ignored, and is close when difflib's ratio is at least --close (default 0.85).

Usage:  python scripts/check_demo_names.py src/data/variety_catalogues/*.csv
Exits non-zero when any name matches or is close.
"""
import argparse
import csv
import difflib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT))

from tests.breedgraph.scenarios.demo.story import GERMPLASM, NEW_CROSS


def normalised(name: str) -> str:
    return re.sub(r'[^a-z0-9]', '', name.casefold())


def catalogue_names(path: Path) -> set[str]:
    with path.open(newline='', encoding='utf-8', errors='replace') as file:
        return {cell.strip() for row in csv.reader(file) for cell in row if cell.strip()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('catalogues', type=Path, nargs='+', help="catalogue exports (CSV or one name a line)")
    parser.add_argument('--close', type=float, default=0.85, help="the difflib ratio at which a name is close")
    args = parser.parse_args()

    real = {}
    for path in args.catalogues:
        for name in catalogue_names(path):
            real.setdefault(normalised(name), name)
    # the invented ones: the varieties, not the crop or the breeding lines' codes (EPB ...), and the guide's new cross
    invented = [variety.name for key, variety in GERMPLASM.items() if key != 'wheat' and not variety.name.startswith('EPB')]
    invented += [name for name in (NEW_CROSS[0],) if not name.startswith('EPB')]

    reported = 0
    for name in invented:
        key = normalised(name)
        if key in real:
            print(f"{name}: the same as the catalogued {real[key]!r}")
            reported += 1
            continue
        close = difflib.get_close_matches(key, real.keys(), n=3, cutoff=args.close)
        if close:
            print(f"{name}: close to {', '.join(repr(real[c]) for c in close)}")
            reported += 1
    print(f"{len(invented)} names against {len(real)} catalogued: {reported} to look at")
    return 1 if reported else 0


if __name__ == '__main__':
    sys.exit(main())
