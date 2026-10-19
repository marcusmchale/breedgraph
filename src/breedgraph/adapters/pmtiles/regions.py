"""
The regions mapped in full detail (scripts/map_tiles.py): the cells of a grid of whole degrees that come within a
padding of a location. The files are served to anyone, so they show which cells hold locations, private ones
included; coarse cells keep that to the area, not the site.
"""
from math import cos, radians, floor
from typing import Iterable, List, Set, Tuple

KM_PER_DEGREE = 111.32
MAX_LATITUDE = 85.05  # the web map projection's limit


def region_cells(
        coordinates: Iterable[Tuple[float, float]],
        padding_km: float = 25,
        cell_degrees: float = 1
) -> Set[Tuple[int, int]]:
    """The grid cells, as (row, column) of cell_degrees from latitude -90 and longitude -180, within padding_km of a
    coordinate (latitude, longitude)"""
    cells = set()
    for latitude, longitude in coordinates:
        if latitude is None or longitude is None:
            continue
        latitude = min(max(latitude, -MAX_LATITUDE), MAX_LATITUDE)
        lat_padding = padding_km / KM_PER_DEGREE
        lon_padding = min(180.0, padding_km / (KM_PER_DEGREE * max(cos(radians(latitude)), 0.01)))
        south, north = max(latitude - lat_padding, -MAX_LATITUDE), min(latitude + lat_padding, MAX_LATITUDE)
        west, east = max(longitude - lon_padding, -180.0), min(longitude + lon_padding, 180.0 - 1e-9)
        for row in range(floor((south + 90) / cell_degrees), floor((north + 90) / cell_degrees) + 1):
            for column in range(floor((west + 180) / cell_degrees), floor((east + 180) / cell_degrees) + 1):
                cells.add((row, column))
    return cells


def _cell_box(cell: Tuple[int, int], cell_degrees: float) -> Tuple[float, float, float, float]:
    """south, west, north, east"""
    row, column = cell
    south, west = row * cell_degrees - 90, column * cell_degrees - 180
    return max(south, -MAX_LATITUDE), west, min(south + cell_degrees, MAX_LATITUDE), west + cell_degrees


def region_geojson(cells: Set[Tuple[int, int]], cell_degrees: float = 1) -> dict:
    """The cells as a GeoJSON MultiPolygon, for pmtiles extract --region"""
    polygons: List[list] = []
    for cell in sorted(cells):
        south, west, north, east = _cell_box(cell, cell_degrees)
        polygons.append([[[west, south], [east, south], [east, north], [west, north], [west, south]]])
    return {'type': 'MultiPolygon', 'coordinates': polygons}


def cells_bounds(cells: Set[Tuple[int, int]], cell_degrees: float = 1) -> List[List[float]] | None:
    """[[south, west], [north, east]] around the cells, or None when there are none"""
    if not cells:
        return None
    boxes = [_cell_box(cell, cell_degrees) for cell in cells]
    return [[min(box[0] for box in boxes), min(box[1] for box in boxes)],
            [max(box[2] for box in boxes), max(box[3] for box in boxes)]]
