"""
The test app keeps its maps and the place search's places in the temporary folders tests/breedgraph/conftest.py's
map_paths gives, not in instance/, so a test removing a country leaves the development site's maps and places alone
"""
from pathlib import Path

import pytest

from breedgraph import config

INSTANCE = Path(__file__).resolve().parents[3] / 'instance'


@pytest.mark.asyncio(loop_scope="session")
async def test_the_apps_maps_are_the_tests_own(bus):
    paths = [bus.map_regions.tiles_path, bus.map_regions.boundaries.path, bus.gazetteer.path]
    assert paths == [Path(config.MAP_TILES_PATH), Path(config.MAP_BOUNDARIES_PATH), Path(config.GAZETTEER_PATH)]
    assert not any(path.resolve().is_relative_to(INSTANCE) for path in paths)
