"""
The countries a location tree can start from, from GeoNames' country list (https://www.geonames.org, CC BY 4.0),
packaged with BreedGraph as data/countryInfo.txt, as GeoNames publishes it: each country's name, ISO 3166 alpha-2 and
alpha-3 codes and GeoNames id, by which the place search joins its places and shapes to it (docs/maps.md).
"""
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Dict

COUNTRY_INFO_PATH = Path(__file__).parents[2] / 'data' / 'countryInfo.txt'
# kept by GeoNames for older data, though no longer countries
DISSOLVED = frozenset({'AN', 'CS'})  # the Netherlands Antilles, Serbia and Montenegro
_ISO2 = re.compile(r'[A-Z]{2}')
_ISO3 = re.compile(r'[A-Z]{3}')


@dataclass(frozen=True)
class Country:
    iso2: str
    iso3: str
    name: str
    geonameid: int


def parse_country_info(text: str) -> Dict[str, Country]:
    """
    The countries in countryInfo.txt's format, by alpha-3 code. Lines are split on tabs alone, so that Namibia's code,
    NA, stays a code.
    """
    countries = {}
    for line in text.splitlines():
        if line.startswith('#') or not line.strip():
            continue
        fields = line.split('\t')
        if len(fields) < 17 or fields[0] in DISSOLVED:
            continue
        iso2, iso3, name, geonameid = fields[0], fields[1], fields[4].strip(), fields[16]
        if _ISO2.fullmatch(iso2) and _ISO3.fullmatch(iso3) and name and geonameid.isdigit():
            countries[iso3] = Country(iso2, iso3, name, int(geonameid))
    return countries


@cache
def read_countries() -> Dict[str, Country]:
    """The packaged countries, by alpha-3 code"""
    return parse_country_info(COUNTRY_INFO_PATH.read_text(encoding='utf-8'))
