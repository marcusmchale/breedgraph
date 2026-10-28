"""
The place search's names (docs/maps.md): GeoNames' places in one SQLite database, so that a search is one query,
answered on our server, and no third party receives it. It holds the countries packaged with BreedGraph
(countries.py) with the extents of their outlines, the towns of 1,000 people or more worldwide, from the world's file,
and every place of each country loaded, from its own file (both written by map_worker.fetching.write_gazetteer). A
country's own places stand in for the world's towns of it once loaded. The sections of countries places are in
(regions) are kept once each, however many places are in them.

A load or removal is one transaction, one at a time across processes; searches go on while it is written (WAL), each
on its own connection and within SEARCH_SECONDS.
"""
import fcntl
import gzip
import json
import math
import re
import sqlite3
import time
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator, List

from breedgraph.adapters.pmtiles.regions import country_bounds
from breedgraph.service_layer.infrastructure.gazetteer import Place
from map_worker.fetching import GAZETTEER_COLUMNS, MALFORMED_SHARE
from .countries import Country

import logging
logger = logging.getLogger(__name__)

DATABASE = 'gazetteer.sqlite'
PLACES_DIRECTORY = 'places'  # the files the database is loaded from, as received, beside it
SCHEMA_VERSION = 1  # a database made by another version is made again, and loaded again from those files
WORLD = 'world'  # the source of the world's towns and countries, beside each country's own
SEARCH_SECONDS = 1.0
PROGRESS_STEPS = 1000  # SQLite's steps between checks of a search's time
QUERY_MAX_CHARACTERS = 200
QUERY_MAX_WORDS = 6
LIMIT_MAX = 20

TEXT_INDEX = "tokenize='unicode61 remove_diacritics 2', prefix='2 3'"
SCHEMA = f"""
CREATE TABLE countries (
    code TEXT PRIMARY KEY,  -- ISO 3166 alpha-3, as countries are coded in BreedGraph
    alpha2 TEXT NOT NULL UNIQUE,  -- as in GeoNames' files
    name TEXT NOT NULL,
    geonameid INTEGER NOT NULL,
    south REAL, west REAL, north REAL, east REAL,  -- around its main parts, east above 180 across the antimeridian
    loaded INTEGER NOT NULL DEFAULT 0  -- whether its own places are, rather than only the world's towns of it
);
CREATE TABLE regions (
    id INTEGER PRIMARY KEY,
    country TEXT NOT NULL,
    admin1 TEXT NOT NULL,
    admin2 TEXT NOT NULL,
    keys TEXT NOT NULL,  -- the sections' names and other names, and the country's, as searched for, one a line
    UNIQUE (country, admin1, admin2, keys)
);
CREATE VIRTUAL TABLE regions_text USING fts5(keys, content='regions', content_rowid='id', {TEXT_INDEX});
CREATE TABLE features (
    code TEXT PRIMARY KEY,  -- GeoNames' feature class and code: 'S.FRM'
    label TEXT NOT NULL  -- and its name for it: 'farm'
);
CREATE TABLE places (
    id INTEGER PRIMARY KEY,
    geonameid INTEGER NOT NULL,
    source TEXT NOT NULL,  -- 'world', or 'country' for those from the country's own file
    country TEXT NOT NULL,  -- alpha-3
    region INTEGER NOT NULL,
    name TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    feature TEXT NOT NULL,
    population INTEGER NOT NULL,
    importance REAL NOT NULL,
    names TEXT NOT NULL,  -- its name, as searched for, one a line
    alternates TEXT NOT NULL  -- its other names
);
CREATE INDEX places_by_country ON places (country, source);
CREATE VIRTUAL TABLE places_text USING fts5(names, alternates, content='places', content_rowid='id', {TEXT_INDEX});
"""

# A place's importance, before its population: countries, then sections and the towns that are their seats
CODE_WEIGHTS = {
    'PCLI': 9, 'PCL': 8, 'PCLD': 8, 'PCLF': 8, 'PCLS': 8, 'PCLIX': 8, 'TERR': 7,
    'ADM1': 6, 'PPLC': 6, 'ADM2': 5, 'PPLA': 5, 'PPLG': 5, 'ADM3': 4, 'PPLA2': 4,
    'ADM4': 3, 'PPLA3': 3, 'PPLA4': 3, 'ADM5': 2, 'ADMD': 2, 'PPL': 2, 'PPLX': 1,
}
CLASS_WEIGHTS = {'A': 2, 'P': 2}
COUNTRY_CODES = frozenset({'PCLI', 'PCL', 'PCLD', 'PCLF', 'PCLS', 'PCLIX', 'TERR'})
# populated places told apart by their population: towns, rather than villages, as GeoNames' cities1000 counts them
SIZED_CODES = frozenset({'PPL', 'PPLA', 'PPLA2', 'PPLA3', 'PPLA4', 'PPLA5', 'PPLG'})
CITY_POPULATION = 100_000
TOWN_POPULATION = 1000
# The zoom to show a place at, by GeoNames' feature classes: spots (buildings, farms), hypsographic (hills,
# mountains), hydrographic (lakes, rivers), areas (parks, regions) and vegetation (forests)
CLASS_ZOOMS = {'S': 16, 'T': 13, 'H': 13, 'L': 12, 'V': 13}
DEFAULT_ZOOM = 13

# letters that lose nothing to decomposition, folded as unicode61's remove_diacritics would not
FOLDED = str.maketrans({'ø': 'o', 'ł': 'l', 'đ': 'd', 'ð': 'd', 'ħ': 'h', 'þ': 'th', 'æ': 'ae', 'œ': 'oe', 'ı': 'i'})
APOSTROPHES = "'’ʼ‘`"
_NOT_WORDS = re.compile(r'[\W_]+')


class GazetteerFileError(Exception):
    """A file of places that cannot be loaded"""


class SearchTooLong(Exception):
    """A search that took more than SEARCH_SECONDS"""


def normalize(text: str, apostrophes: str = ' ') -> str:
    """
    A name as searched for: without case or accents, in words of letters and numbers split by single spaces, with
    apostrophes replaced by the given string (a space, or '' to join "King's" into "kings")
    """
    if text.isascii():
        folded = text.lower()
    else:
        folded = unicodedata.normalize('NFKD', text.casefold())
        folded = ''.join(c for c in folded if not unicodedata.combining(c)).translate(FOLDED)
    for apostrophe in APOSTROPHES:
        if apostrophe in folded:
            folded = folded.replace(apostrophe, apostrophes)
    return _NOT_WORDS.sub(' ', folded).strip()


def _lines(names: Iterable[str]) -> str:
    """
    Names as searched for, each once and on its own line, with a line break before and after so that a whole name is
    found by its line; each with its apostrophes as spaces and left out, so that "king's", "king s" and "kings" find it
    """
    seen = {}
    for name in names:
        if name:
            for variant in (normalize(name), normalize(name, '')):
                if variant:
                    seen.setdefault(variant, None)
    return '\n' + '\n'.join(seen) + '\n' if seen else ''


def words(query: str) -> List[str]:
    """A search's words, apostrophes left out, as the FTS5 queries take them: letters and numbers only"""
    return normalize(query[:QUERY_MAX_CHARACTERS], '').split()[:QUERY_MAX_WORDS]


def term(word: str, prefix: bool) -> str:
    """A word quoted, so that none is read as FTS5's syntax, or the start of one"""
    return f'"{word}"*' if prefix else f'"{word}"'


def importance_for(feature_class: str, feature_code: str, population: int) -> float:
    return CODE_WEIGHTS.get(feature_code, CLASS_WEIGHTS.get(feature_class, 1)) + math.log10(1 + max(population, 0))


def label_for(feature_class: str, feature_code: str, label: str | None, population: int) -> str | None:
    """What kind of place it is, in words a person would use where GeoNames' are technical"""
    if feature_code in COUNTRY_CODES:
        return 'country'
    if feature_code == 'ADM1':
        return 'state or province'
    if feature_code == 'ADM2':
        return 'county or district'
    if feature_code.startswith('ADM'):
        return 'district'
    if feature_code == 'PPLC':
        return 'capital'
    if feature_code in SIZED_CODES:
        if population >= CITY_POPULATION:
            return 'city'
        if population >= TOWN_POPULATION:
            return 'town'
        return 'village' if population > 0 else 'town or village'
    return label or None


def zoom_for(feature_class: str, feature_code: str, population: int) -> int:
    """The zoom to show a place at, where it has no bounds"""
    if feature_code in COUNTRY_CODES:
        return 5
    if feature_code == 'ADM1':
        return 7
    if feature_code == 'ADM2':
        return 9
    if feature_code.startswith('ADM'):
        return 11
    if feature_class == 'P':
        if population >= CITY_POPULATION:
            return 11
        return 12 if population >= TOWN_POPULATION else 14
    return CLASS_ZOOMS.get(feature_class, DEFAULT_ZOOM)


def region_for(name: str, admin2: str, admin1: str) -> str | None:
    """
    The sections of its country a place is in, smallest first, leaving out its own name and a name given twice:
    "Kerry, Munster"
    """
    parts, seen = [], {normalize(name)}
    for part in (admin2, admin1):
        if part and normalize(part) not in seen:
            parts.append(part)
            seen.add(normalize(part))
    return ', '.join(parts) or None


def _wrap(longitude: float) -> float:
    return (longitude + 180) % 360 - 180


class _Viewbox:
    """
    A map's view, [west, south, east, north], as Leaflet gives it: its longitudes may lie beyond ±180 when the map is
    panned across the antimeridian, and a view across it has its west east of its east once wrapped
    """

    def __init__(self, viewbox: List[float]):
        if len(viewbox) != 4 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in viewbox):
            raise ValueError("A viewbox is [west, south, east, north]")
        west, south, east, north = (float(v) for v in viewbox)
        if not -90 <= south <= north <= 90 or east < west:
            raise ValueError("A viewbox is [west, south, east, north]")
        self.south, self.north = south, north
        self.whole_width = east - west >= 360
        self.west, self.east = (-180.0, 180.0) if self.whole_width else (_wrap(west), _wrap(east))
        self.latitude = (south + north) / 2
        self.longitude = _wrap((west + east) / 2)
        self.scale = math.cos(math.radians(self.latitude)) ** 2  # degrees of longitude are shorter away from the equator

    def inside(self) -> str:
        latitude = 'p.latitude BETWEEN :south AND :north'
        if self.whole_width:
            return f'({latitude})'
        if self.west <= self.east:
            return f'({latitude} AND p.longitude BETWEEN :west AND :east)'
        return f'({latitude} AND (p.longitude >= :west OR p.longitude <= :east))'

    @staticmethod
    def distance() -> str:
        """Squared, in degrees of latitude, from the view's centre, the short way round"""
        longitudes = 'min(abs(p.longitude - :centre_longitude), 360 - abs(p.longitude - :centre_longitude))'
        return (f'(p.latitude - :centre_latitude) * (p.latitude - :centre_latitude)'
                f' + {longitudes} * {longitudes} * :scale')

    def parameters(self) -> dict:
        return {
            'south': self.south, 'north': self.north, 'west': self.west, 'east': self.east,
            'centre_latitude': self.latitude, 'centre_longitude': self.longitude, 'scale': self.scale
        }


class _Rows:
    """A file's places, read as they are written in, counting those that could not be read"""

    def __init__(self, path: Path):
        self.path = path
        self.read = 0
        self.malformed = 0

    def __iter__(self) -> Iterator[list]:
        try:
            with gzip.open(self.path, 'rt', encoding='utf-8') as f:
                if tuple(f.readline().rstrip('\n').split('\t')) != GAZETTEER_COLUMNS:
                    raise GazetteerFileError(f"{self.path.name} is not a file of places")
                for line in f:
                    self.read += 1
                    fields = line.rstrip('\n').split('\t')
                    if len(fields) != len(GAZETTEER_COLUMNS):
                        self.malformed += 1
                        continue
                    yield fields
        except (OSError, EOFError, UnicodeDecodeError) as e:
            raise GazetteerFileError(f"{self.path.name} could not be read: {type(e).__name__}") from e

    def check(self) -> None:
        if self.malformed > self.read * MALFORMED_SHARE:
            raise GazetteerFileError(f"{self.malformed} of {self.read} places in {self.path.name} are malformed")


class _Load:
    """
    A file's places written in, in a transaction: their regions, each kept once, given ids as they are first met (any
    already in the database kept), and the names of their features
    """

    def __init__(self, db: sqlite3.Connection, source: str, countries: dict, where: str = '', parameters: tuple = ()):
        """
        countries: alpha-2: (alpha-3, name, geonameid), the countries whose places are loaded; where: their regions
        """
        self.db, self.source, self.countries = db, source, countries
        self.regions = {
            (country, admin1, admin2, keys): region for region, country, admin1, admin2, keys
            in db.execute(f'SELECT id, country, admin1, admin2, keys FROM regions {where}', parameters)
        }
        self.first_region = (db.execute('SELECT max(id) FROM regions').fetchone()[0] or 0) + 1
        self.new_regions = []
        self.read_regions = {}
        self.region_alternates = {}  # the other names of sections, by country (alpha-2) and their names, as given once
        self.features = {}
        self.shapes = []  # the world's countries' (geonameid, shape)

    def region(self, code: str, country: str, admin1: str, admin2: str, alternates: str) -> int:
        read = (code, admin1, admin2, alternates)
        if read not in self.read_regions:
            region = (code, admin1, admin2, _lines([admin2, admin1, *alternates.split(','), country]))
            if region not in self.regions:
                self.regions[region] = self.first_region + len(self.new_regions)
                self.new_regions.append((self.regions[region], *region))
            self.read_regions[read] = self.regions[region]
        return self.read_regions[read]

    def rows(self, rows: _Rows) -> Iterator[tuple]:
        """Rows of the places table from a file's"""
        for (geonameid, name, asciiname, alternates, latitude, longitude, feature_class, feature_code, label,
             alpha2, admin1, admin2, region_alternates, population, _modified, shape) in rows:
            if not geonameid and region_alternates:
                self.region_alternates[(alpha2, admin1, admin2)] = region_alternates
                continue
            try:
                if shape:
                    self.shapes.append((int(geonameid), json.loads(shape)))
                    continue
                if alpha2 not in self.countries:
                    continue
                code, country, country_geonameid = self.countries[alpha2]
                identifier, population = int(geonameid), int(population or 0)
                latitude, longitude = float(latitude), float(longitude)
                if not name or not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                    raise ValueError
            except ValueError:
                rows.malformed += 1
                continue
            feature = f'{feature_class}.{feature_code}'
            if label:
                self.features[feature] = label
            # the country itself is found by the name it has in BreedGraph too ("Fiji", which GeoNames calls "Viti")
            names = [country, name, asciiname] if identifier == country_geonameid else [name, asciiname]
            region_alternates = region_alternates or self.region_alternates.get((alpha2, admin1, admin2), '')
            yield (
                identifier, self.source, code, self.region(code, country, admin1, admin2, region_alternates), name,
                latitude, longitude, feature, population, importance_for(feature_class, feature_code, population),
                _lines(names), _lines(alternates.split(',')) if alternates else ''
            )

    def insert(self, places: Iterable[tuple]) -> int:
        before = self.db.total_changes
        self.db.executemany(
            'INSERT INTO places (geonameid, source, country, region, name, latitude, longitude, feature, population,'
            ' importance, names, alternates) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', places
        )
        return self.db.total_changes - before

    def finish(self, where: str, parameters: tuple = ()) -> None:
        """The new regions and features written, and the places loaded (where) indexed"""
        self.db.executemany('INSERT INTO regions (id, country, admin1, admin2, keys) VALUES (?, ?, ?, ?, ?)',
                            self.new_regions)
        self.db.execute('INSERT INTO regions_text (rowid, keys) SELECT id, keys FROM regions WHERE id >= ?',
                        (self.first_region,))
        self.db.executemany('INSERT INTO features (code, label) VALUES (?, ?)'
                            ' ON CONFLICT (code) DO UPDATE SET label = excluded.label', self.features.items())
        self.db.execute('INSERT INTO places_text (rowid, names, alternates)'
                        f' SELECT id, names, alternates FROM places WHERE {where}', parameters)


class GazetteerIndex:
    """The database at path (GAZETTEER_PATH/DATABASE), made by create() before it is loaded or searched"""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock_path = self.path.with_name(f'.{self.path.name}.lock')

    @contextmanager
    def _locked(self) -> Iterator[None]:
        """Held while the database is written, by one thread in one process at a time"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._lock_path, 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    @contextmanager
    def _closing(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, isolation_level=None)
        try:
            yield db
        finally:
            db.close()

    def create(self, countries: Iterable[Country]) -> bool:
        """
        Make the database, or make it again, empty, when another version of this module made it, and list the
        countries in it: True when made, so that its places are to be loaded again
        """
        with self._locked():
            made = False
            try:
                with self._closing() as db:
                    version = db.execute('PRAGMA user_version').fetchone()[0]
            except sqlite3.DatabaseError:
                version = None
            if version != SCHEMA_VERSION:
                for path in (self.path, Path(f'{self.path}-wal'), Path(f'{self.path}-shm')):
                    path.unlink(missing_ok=True)
                with self._closing() as db:
                    db.execute('PRAGMA auto_vacuum = INCREMENTAL')  # so that the room a country's places took is given back
                    db.execute('PRAGMA journal_mode = WAL')
                    db.executescript(SCHEMA)
                    db.execute(f'PRAGMA user_version = {SCHEMA_VERSION}')
                made = True
            with self._closing() as db:
                db.execute('BEGIN IMMEDIATE')
                db.executemany(
                    'INSERT INTO countries (code, alpha2, name, geonameid) VALUES (?, ?, ?, ?)'
                    ' ON CONFLICT (code) DO UPDATE'
                    ' SET alpha2 = excluded.alpha2, name = excluded.name, geonameid = excluded.geonameid',
                    [(country.iso3, country.iso2, country.name, country.geonameid) for country in countries]
                )
                db.execute('COMMIT')
            return made

    @contextmanager
    def _writing(self) -> Iterator[sqlite3.Connection]:
        """
        One transaction, committed if it ends without an exception, after which the room what it deleted took is given
        back: the text indexes keep what is deleted until their parts merge, so they are merged into one (as long as
        a load again: 15 s with the United States), and the pages freed are cut from the file
        """
        with self._locked(), self._closing() as db:
            db.execute('PRAGMA synchronous = NORMAL')
            db.execute('BEGIN IMMEDIATE')
            try:
                yield db
                db.execute("INSERT INTO places_text (places_text) VALUES ('optimize')")
                db.execute("INSERT INTO regions_text (regions_text) VALUES ('optimize')")
            except BaseException:
                if db.in_transaction:
                    db.execute('ROLLBACK')
                raise
            db.execute('COMMIT')
            db.execute('PRAGMA incremental_vacuum').fetchall()  # a page a step
            db.execute('PRAGMA wal_checkpoint(TRUNCATE)')  # so the log, as large as a country's places, doesn't stay

    @staticmethod
    def _delete(db: sqlite3.Connection, where: str, parameters: tuple = ()) -> None:
        """Places, with their entries in the text index (which takes the text each was indexed with)"""
        db.execute("INSERT INTO places_text (places_text, rowid, names, alternates)"
                   f" SELECT 'delete', id, names, alternates FROM places WHERE {where}", parameters)
        db.execute(f'DELETE FROM places WHERE {where}', parameters)

    @staticmethod
    def _delete_regions(db: sqlite3.Connection, where: str, parameters: tuple = ()) -> None:
        """Regions no place is in any longer, of those where"""
        where = f'{where} AND id NOT IN (SELECT region FROM places)'
        db.execute(f"INSERT INTO regions_text (regions_text, rowid, keys) SELECT 'delete', id, keys FROM regions"
                   f" WHERE {where}", parameters)
        db.execute(f'DELETE FROM regions WHERE {where}', parameters)

    def load_country(self, code: str, path: Path) -> int:
        """A country's places from its file, in place of any it had: how many"""
        own = "country = ? AND source = 'country'"
        with self._writing() as db:
            row = db.execute('SELECT alpha2, name, geonameid FROM countries WHERE code = ?', (code,)).fetchone()
            if row is None:
                raise GazetteerFileError(f"{code} is not one of the countries")
            alpha2, name, geonameid = row
            self._delete(db, own, (code,))
            load = _Load(db, 'country', {alpha2: (code, name, geonameid)}, 'WHERE country = ?', (code,))
            rows = _Rows(path)
            count = load.insert(load.rows(rows))
            rows.check()
            load.finish(own, (code,))
            self._delete_regions(db, 'country = ?', (code,))
            db.execute('UPDATE countries SET loaded = 1 WHERE code = ?', (code,))
        logger.info(f"Loaded {count} places of {code} for the place search")
        return count

    def load_world(self, path: Path) -> int:
        """
        The world's towns and countries' shapes from its file, in place of any it had: how many towns. The countries
        are places too, at the middle of their extents.
        """
        with self._writing() as db:
            countries = {alpha2: (code, name, geonameid) for code, alpha2, name, geonameid
                         in db.execute('SELECT code, alpha2, name, geonameid FROM countries')}
            self._delete(db, 'source = ?', (WORLD,))
            db.execute('UPDATE countries SET south = NULL, west = NULL, north = NULL, east = NULL')
            load = _Load(db, WORLD, countries)
            rows = _Rows(path)
            count = load.insert(load.rows(rows))
            rows.check()
            for geonameid, shape in load.shapes:
                bounds = country_bounds([{'geometry': shape}])
                if bounds is not None:
                    (south, west), (north, east) = bounds
                    db.execute('UPDATE countries SET south = ?, west = ?, north = ?, east = ? WHERE geonameid = ?',
                               (south, west, north, east, geonameid))
            load.insert([
                (geonameid, WORLD, code, load.region(code, name, '', '', ''), name, (south + north) / 2,
                 _wrap((west + east) / 2), 'A.PCLI', 0, importance_for('A', 'PCLI', 0), _lines([name]), '')
                for code, name, geonameid, south, west, north, east in db.execute(
                    'SELECT code, name, geonameid, south, west, north, east FROM countries WHERE south IS NOT NULL'
                ).fetchall()
            ])
            load.finish('source = ?', (WORLD,))
            self._delete_regions(db, '1')
        logger.info(f"Loaded {count} towns and {len(load.shapes)} countries' shapes of the world for the place search")
        return count

    def remove_country(self, code: str) -> None:
        """A country's own places, leaving the world's towns of it"""
        with self._writing() as db:
            self._delete(db, "country = ? AND source = 'country'", (code,))
            self._delete_regions(db, 'country = ?', (code,))
            db.execute('UPDATE countries SET loaded = 0 WHERE code = ?', (code,))

    def loaded(self) -> set[str]:
        """The countries whose own places are loaded"""
        with self._reading() as db:
            return {code for code, in db.execute('SELECT code FROM countries WHERE loaded')}

    def world_loaded(self) -> bool:
        """Whether the world's towns are"""
        with self._reading() as db:
            return bool(db.execute('SELECT EXISTS (SELECT 1 FROM places WHERE source = ?)', (WORLD,)).fetchone()[0])

    @contextmanager
    def _reading(self, seconds: float | None = None) -> Iterator[sqlite3.Connection]:
        if not self.path.exists():
            raise FileNotFoundError(f"The place search's database is not made: {self.path}")
        with self._closing() as db:
            db.execute('PRAGMA query_only = 1')
            if seconds is not None:
                deadline = time.monotonic() + seconds
                db.set_progress_handler(lambda: time.monotonic() > deadline, PROGRESS_STEPS)
            try:
                yield db
            except sqlite3.OperationalError as e:
                if 'interrupted' in str(e):
                    raise SearchTooLong() from e
                raise

    @staticmethod
    def _place(row: sqlite3.Row) -> Place:
        feature_class, _, feature_code = row['feature'].partition('.')
        population = row['population']
        country = row['geonameid'] == row['country_geonameid']  # the country itself, named as BreedGraph names it
        bounds = None
        if country and row['south'] is not None:
            bounds = [[row['south'], row['west']], [row['north'], row['east']]]
        name = row['country_name'] if country else row['name']
        return Place(
            name=name,
            latitude=row['latitude'],
            longitude=row['longitude'],
            bounds=bounds,
            description=label_for(feature_class, feature_code, row['label'], population),
            region=None if country else region_for(name, row['admin2'], row['admin1']),
            country=None if country else row['country_name'],
            country_code=row['country_code'],
            zoom=None if bounds else zoom_for(feature_class, feature_code, population)
        )

    @staticmethod
    def _query(found: List[str], by: int, view: '_Viewbox | None', bounded: bool, country: str | None) -> tuple:
        """
        The search for places one of whose names has the word found[by], each other word in their names or their
        region's, ranked by search()'s order; and its parameters
        """
        whole = ' '.join(found)
        last = len(found) - 1
        # the last word is the start of one, as it is being typed; but a single letter, as the word the places are found
        # by, starts too many names to rank in time (the United States has 2 million), so it is a whole word there
        match = term(found[by], by == last and len(found[by]) > 1)
        parameters = {'match': match, 'exact': f'\n{whole}\n', 'start': f'\n{whole}'}
        conditions = ['places_text MATCH :match', "(p.source = 'country' OR NOT c.loaded)"]
        for i, word in enumerate(found):
            if i == by:
                continue
            parameters |= {f'region_{i}': term(word, i == last), f'line_{i}': f'\n{word}', f'word_{i}': f' {word}'}
            conditions.append(
                f'(p.region IN (SELECT rowid FROM regions_text WHERE regions_text MATCH :region_{i})'
                + ''.join(f' OR instr(p.{column}, :{start}_{i}) > 0'
                          for column in ('names', 'alternates') for start in ('line', 'word'))
                + ')'
            )
        if country:
            conditions.append('p.country = :country')
            parameters['country'] = country
        order = ['instr(p.names, :exact) > 0 DESC', 'instr(p.names, :start) > 0 DESC',
                 'instr(p.alternates, :exact) > 0 DESC']
        if view is not None:
            parameters |= view.parameters()
            if bounded:
                conditions.append(view.inside())
            else:
                order.append(f'{view.inside()} DESC')
        order.append('p.importance DESC')
        if view is not None:
            order.append(view.distance())
        sql = (
            'SELECT p.geonameid, p.name, p.latitude, p.longitude, p.feature, p.population, r.admin1, r.admin2, f.label,'
            ' c.code AS country_code, c.name AS country_name, c.geonameid AS country_geonameid, c.south, c.west, c.north, c.east'
            ' FROM places_text JOIN places p ON p.id = places_text.rowid JOIN regions r ON r.id = p.region'
            ' JOIN countries c ON c.code = p.country LEFT JOIN features f ON f.code = p.feature'
            f" WHERE {' AND '.join(conditions)} ORDER BY {', '.join(order)} LIMIT :limit"
        )
        return sql, parameters

    def search(
            self,
            query: str,
            viewbox: List[float] | None = None,
            bounded: bool = False,
            country: str | None = None,
            limit: int = 5
    ) -> List[Place]:
        """
        Places one of whose names has the query's first word, or the start of it as the last, its other words in their
        names or their region's: their name first being the query, then starting it, then another of their names being
        it, then those in viewbox ([west, south, east, north]), or only those there when bounded, the most important,
        and the nearest to it; only those in the country with this alpha-3 code when given. When none has the first
        word in its names, the next is tried ("kerry ballyduff"). SearchTooLong after SEARCH_SECONDS.
        """
        found = words(query or '')
        view = _Viewbox(viewbox) if viewbox else None
        rows = []
        with self._reading(SEARCH_SECONDS) as db:
            db.row_factory = sqlite3.Row
            for by in range(len(found)):
                sql, parameters = self._query(found, by, view, bounded, country)
                rows = db.execute(sql, {**parameters, 'limit': max(1, min(limit, LIMIT_MAX))}).fetchall()
                if rows:
                    break
        return [self._place(row) for row in rows]

    def country_place(self, code: str) -> Place | None:
        """A country, with its extent, once the world's file is loaded"""
        with self._reading() as db:
            row = db.execute('SELECT name, south, west, north, east FROM countries WHERE code = ? AND south IS NOT NULL',
                             (code,)).fetchone()
        if row is None:
            return None
        name, south, west, north, east = row
        return Place(
            name=name,
            latitude=(south + north) / 2,
            longitude=_wrap((west + east) / 2),
            bounds=[[south, west], [north, east]],
            description='country',
            country_code=code
        )
