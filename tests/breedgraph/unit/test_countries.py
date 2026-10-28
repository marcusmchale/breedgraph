"""
The countries a location tree can start from (adapters/geonames/countries.py): GeoNames' country list, packaged with
BreedGraph as data/countryInfo.txt, in place of a file each deployment had to supply.
"""
import re

from breedgraph.adapters.geonames.countries import read_countries, parse_country_info, Country

HEADER = "# GeoNames' notes\n#ISO\tISO3\tISO-Numeric\tfips\tCountry\tCapital\tArea\tPopulation\tContinent\ttld\t" \
         "CurrencyCode\tCurrencyName\tPhone\tPostal Code Format\tPostal Code Regex\tLanguages\tgeonameid\tneighbours\t" \
         "EquivalentFipsCode\n"


def row(iso2, iso3, name, geonameid='1'):
    return '\t'.join([iso2, iso3, '000', 'XX', name, 'Capital', '1', '1', 'EU', '.x', 'EUR', 'Euro', '1', '', '', 'en',
                      geonameid, '', '']) + '\n'


def test_the_packaged_countries():
    countries = read_countries()
    assert len(countries) >= 245
    assert countries['IRL'] == Country('IE', 'IRL', 'Ireland', 2963597)
    assert countries['NAM'].iso2 == 'NA', "Namibia's code is a code, not a missing value"
    assert 'ANT' not in countries and 'SCG' not in countries, 'no dissolved countries'
    assert all(re.fullmatch('[A-Z]{3}', code) and country.iso3 == code for code, country in countries.items())
    assert len({country.iso2 for country in countries.values()}) == len(countries)


def test_country_info_is_read_by_its_tabs_alone():
    text = HEADER + row('NA', 'NAM', 'Namibia', '3355338') + row('BQ', 'BES', 'Bonaire, Saint Eustatius and Saba') \
        + row('AN', 'ANT', 'Netherlands Antilles') + row('xx', 'XXX', 'Lower case') + row('YY', 'YYY', 'No id', '') \
        + 'ZZ\tZZZ\ttoo few fields\n' + '\n'
    assert parse_country_info(text) == {
        'NAM': Country('NA', 'NAM', 'Namibia', 3355338),
        'BES': Country('BQ', 'BES', 'Bonaire, Saint Eustatius and Saba', 1),
    }
