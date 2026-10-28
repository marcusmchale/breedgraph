"""
The regions mapped in full detail (map_regions.py): whole countries, or for a country too large to fetch whole, the
sections of it (states or provinces, geoBoundaries' ADM1 units, or within one of those an ADM2 unit) where locations
are placed. Countries are public, and a section shows only that some location lies within it.

Sections are found here, from local outlines, so no site coordinates leave the server.
"""
import fcntl
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from math import cos, radians, inf
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ATTRIBUTION = '© OpenStreetMap contributors, Protomaps'
COUNTRY = 'ADM0'
SECTION_LEVELS = ('ADM1', 'ADM2')
REGIONS_DIRECTORY = 'regions'  # within the tiles path, so served with the world file
COUNTRIES_DIRECTORY = 'countries'  # each country's extent, for showing it on the map
WORLD_JSON = 'world.json'
TILES_JSON = 'tiles.json'
# How far a point may lie outside every simplified outline and still take the nearest section, in degrees of latitude
NEAREST_SECTION_DEGREES = 1.0
# A country is shown by its parts at least this share of its largest, by area
MAIN_PART_SHARE = 0.01

_CODE = re.compile(r'[A-Z]{3}')
_SHAPE_ID = re.compile(r'[A-Za-z0-9_-]+')

Point = Tuple[float, float]  # latitude, longitude


@dataclass(frozen=True)
class Region:
    """A country (ISO 3166 alpha-3 code) or a section of it (geoBoundaries' level and shapeID)"""
    code: str
    level: str = COUNTRY
    shape_id: str | None = None

    def __post_init__(self):
        if not _CODE.fullmatch(self.code or ''):
            raise ValueError(f"Not an ISO 3166 alpha-3 code: {self.code!r}")
        if self.level == COUNTRY:
            if self.shape_id is not None:
                raise ValueError("A country has no shapeID")
        elif self.level not in SECTION_LEVELS or not _SHAPE_ID.fullmatch(self.shape_id or ''):
            raise ValueError(f"Not a section: {self.level} {self.shape_id!r}")

    @property
    def key(self) -> str:
        """IRL, or USA-ADM1-<shapeID>; the name of the region's files"""
        return self.code if self.level == COUNTRY else f'{self.code}-{self.level}-{self.shape_id}'

    @classmethod
    def from_key(cls, key: str) -> 'Region':
        code, *section = key.split('-', 2)
        if not section:
            return cls(code)
        if len(section) != 2:
            raise ValueError(f"Not a region key: {key!r}")
        return cls(code, *section)


def _polygons(geometry: dict) -> list:
    """The polygons of a Polygon or MultiPolygon, each a list of rings of [longitude, latitude, ...]"""
    if geometry.get('type') == 'Polygon':
        return [geometry['coordinates']]
    if geometry.get('type') == 'MultiPolygon':
        return geometry['coordinates']
    return []


def geometry_bounds(geometry: dict) -> List[List[float]] | None:
    """[[south, west], [north, east]] around the geometry, or None when it has no points"""
    points = [point for polygon in _polygons(geometry) for ring in polygon for point in ring]
    if not points:
        return None
    longitudes, latitudes = [point[0] for point in points], [point[1] for point in points]
    return [[min(latitudes), min(longitudes)], [max(latitudes), max(longitudes)]]


def features_bounds(features: Iterable[dict]) -> List[List[float]] | None:
    boxes = [box for box in (geometry_bounds(feature.get('geometry') or {}) for feature in features) if box]
    if not boxes:
        return None
    return [[min(box[0][0] for box in boxes), min(box[0][1] for box in boxes)],
            [max(box[1][0] for box in boxes), max(box[1][1] for box in boxes)]]


def _area(polygon: list) -> float:
    """Roughly the area of a polygon's outer ring, in square degrees of latitude"""
    ring = polygon[0] if polygon else []
    if len(ring) < 3:
        return 0.0
    scale = cos(radians(sum(position[1] for position in ring) / len(ring)))
    twice = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1]))
    return abs(twice) / 2 * scale


def _longitude_span(intervals: List[Tuple[float, float]]) -> Tuple[float, float]:
    """
    West and east of the narrowest span holding the intervals of longitude, crossing the antimeridian when that is
    narrower; east is then above 180, which Leaflet accepts
    """
    merged: List[List[float]] = []
    for west, east in sorted(intervals):
        if merged and west <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], east)
        else:
            merged.append([west, east])
    # the widest gap between them, round the globe, is left out
    gaps = [(merged[0][0] + 360 - merged[-1][1], len(merged) - 1)]
    gaps += [(merged[i + 1][0] - merged[i][1], i) for i in range(len(merged) - 1)]
    _, before = max(gaps)
    if before == len(merged) - 1:
        return merged[0][0], merged[-1][1]
    return merged[before + 1][0], merged[before][1] + 360


def country_bounds(features: Iterable[dict]) -> List[List[float]] | None:
    """
    [[south, west], [north, east]] to show a country by: around its main parts, those at least MAIN_PART_SHARE of the
    largest, so that small distant islands and territories don't widen it across an ocean
    """
    features = list(features)
    polygons = [polygon for feature in features for polygon in _polygons(feature.get('geometry') or {}) if polygon]
    areas = [_area(polygon) for polygon in polygons]
    if not polygons or max(areas) <= 0:
        return features_bounds(features)
    main = [polygon[0] for polygon, area in zip(polygons, areas) if area >= max(areas) * MAIN_PART_SHARE]
    latitudes = [position[1] for ring in main for position in ring]
    west, east = _longitude_span([(min(p[0] for p in ring), max(p[0] for p in ring)) for ring in main])
    return [[min(latitudes), west], [max(latitudes), east]]


def _in_ring(latitude: float, longitude: float, ring: list) -> bool:
    inside = False
    for start, end in zip(ring, ring[1:] + ring[:1]):
        (x1, y1), (x2, y2) = start[:2], end[:2]
        if (y1 > latitude) != (y2 > latitude) and longitude < x1 + (latitude - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def contains(geometry: dict, point: Point) -> bool:
    latitude, longitude = point
    return any(
        polygon and _in_ring(latitude, longitude, polygon[0])
        and not any(_in_ring(latitude, longitude, hole) for hole in polygon[1:])
        for polygon in _polygons(geometry)
    )


def _segment_distance(point: Tuple[float, float], start: Tuple[float, float], end: Tuple[float, float]) -> float:
    (px, py), (ax, ay), (bx, by) = point, start, end
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy
    t = 0.0 if length == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length))
    return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5


def distance(geometry: dict, point: Point) -> float:
    """Roughly how far the point is from the geometry's outline, in degrees of latitude"""
    latitude, longitude = point
    scale = cos(radians(latitude))  # degrees of longitude are shorter away from the equator
    nearest = inf
    for polygon in _polygons(geometry):
        for ring in polygon:
            scaled = [(position[0] * scale, position[1]) for position in ring]
            for start, end in zip(scaled, scaled[1:]):
                nearest = min(nearest, _segment_distance((longitude * scale, latitude), start, end))
    return nearest


def _box_contains(feature: dict, point: Point) -> bool:
    if 'bbox' not in feature:
        bounds = geometry_bounds(feature.get('geometry') or {})
        feature['bbox'] = [bounds[0][1], bounds[0][0], bounds[1][1], bounds[1][0]] if bounds else None
    box = feature['bbox']
    return box is not None and box[1] <= point[0] <= box[3] and box[0] <= point[1] <= box[2]


def section_for(features: Iterable[dict], point: Point) -> dict | None:
    """
    The feature whose outline holds the point, or when none does, e.g. for a site on a coast that the simplified
    outlines leave out, the nearest within NEAREST_SECTION_DEGREES; None when the point is further from every one
    """
    features = [feature for feature in features if feature.get('geometry')]
    for feature in features:
        if _box_contains(feature, point) and contains(feature['geometry'], point):
            return feature
    nearest = min(features, key=lambda feature: distance(feature['geometry'], point), default=None)
    if nearest is not None and distance(nearest['geometry'], point) <= NEAREST_SECTION_DEGREES:
        return nearest
    return None


def write_json(path: Path, content) -> None:
    """Written under a temporary name and then replaced, so readers never see part of it"""
    temporary = path.with_name(f'.{path.name}.partial')
    temporary.write_text(json.dumps(content, indent=2))
    os.replace(temporary, path)


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return None


def region_file(tiles_path: Path, region: Region, suffix: str = '.pmtiles') -> Path:
    return tiles_path / REGIONS_DIRECTORY / f'{region.key}{suffix}'


def regions_size(directory: Path, excluding: Path | None = None) -> int:
    """The bytes the complete region files in the directory take, but for one"""
    return sum(
        path.stat().st_size for path in directory.glob('*.pmtiles')
        if not path.name.startswith('.') and path != excluding
    )


def read_sidecars(tiles_path: Path) -> List[dict]:
    """The regions fetched: the sidecar of each complete region file"""
    directory = tiles_path / REGIONS_DIRECTORY
    if not directory.is_dir():
        return []
    sidecars = []
    for path in sorted(directory.glob('*.json')):
        if path.name.startswith('.') or not path.with_suffix('.pmtiles').exists():
            continue
        sidecar = read_json(path)
        if sidecar is not None:
            sidecars.append(sidecar)
    return sidecars


def country_file(tiles_path: Path, code: str) -> Path:
    return tiles_path / COUNTRIES_DIRECTORY / f'{code}.json'


def read_countries(tiles_path: Path) -> Dict[str, dict]:
    """The extents of the countries whose maps were asked for, by code"""
    directory = tiles_path / COUNTRIES_DIRECTORY
    if not directory.is_dir():
        return {}
    countries = {}
    for path in sorted(directory.glob('*.json')):
        country = read_json(path)
        if country is not None:
            countries[path.stem] = country
    return countries


def tiles_json(world: dict, sidecars: Iterable[dict], countries: Dict[str, dict] | None = None) -> dict:
    """
    tiles.json, for the location map (breedview composables/locations/baseMap.js): the world, then the regions, and
    the extent to show each country by
    """
    return {
        'attribution': ATTRIBUTION,
        'updated': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'layers': [
            {key: world[key] for key in ('url', 'maxZoom', 'build') if key in world},
            *({key: sidecar[key] for key in ('url', 'name', 'minZoom', 'maxZoom', 'bounds')} for sidecar in sidecars)
        ],
        'countries': {
            code: {key: country[key] for key in ('name', 'bounds')} for code, country in (countries or {}).items()
        }
    }


def write_tiles_json(tiles_path: Path) -> bool:
    """
    Rebuild tiles.json from world.json, the regions' sidecars and the countries' extents, holding a lock so that
    processes adding or removing regions at the same time keep one another's. Returns False, writing nothing, while
    there is no world file.
    """
    tiles_path.mkdir(parents=True, exist_ok=True)
    with open(tiles_path / '.tiles.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        world = read_json(tiles_path / WORLD_JSON)
        if world is None:
            return False
        write_json(tiles_path / TILES_JSON, tiles_json(world, read_sidecars(tiles_path), read_countries(tiles_path)))
        return True
