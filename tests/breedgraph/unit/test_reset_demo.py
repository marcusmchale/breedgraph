"""
scripts/reset_demo.sh with DRY_RUN=1, which prints what it would run: it reads the dump's parts from DEMO_DUMP_DIR
(neo4j.dump, files/, map_tiles/, map_boundaries/), and refuses, before stopping anything, an env file whose settings
from earlier releases name them elsewhere.
"""
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]


@pytest.fixture
def site(tmp_path) -> Path:
    """A demonstration site's folders, with its dump and its maps"""
    dump = tmp_path / 'dump'
    for folder in ('files', 'map_tiles', 'map_boundaries'):
        (dump / folder).mkdir(parents=True)
    (dump / 'neo4j.dump').write_bytes(b'')
    (tmp_path / 'demo_accounts.json').write_text('{}')
    return tmp_path


def env_file(site: Path, **settings) -> Path:
    values = {
        'BREEDGRAPH_DEMO': '1', 'DB_PORT': '7688', 'REDIS_PORT': '6380',
        'DEMO_ROOT': site, 'DEMO_DUMP_DIR': site / 'dump', 'DEMO_ACCOUNTS': site / 'demo_accounts.json',
        'DEMO_CHECKOUT': ROOT, 'DEMO_ARCHIVE_DIR': site / 'archive', 'NEO4J_PACKAGE': '/usr/share/neo4j',
        'FILE_STORAGE_PATH': site / 'files', 'PERSON_ERASURE_LOG_PATH': site / 'erasure.jsonl',
        'TERMS_OF_USE_PATH': site / 'legal/terms.md', 'PRIVACY_NOTICE_PATH': site / 'legal/privacy.md',
        'MAP_TILES_PATH': site / 'map_tiles', 'MAP_BOUNDARIES_PATH': site / 'map_boundaries',
        'GAZETTEER_PATH': site / 'gazetteer',
    } | settings
    path = site / 'breedgraph-demo.env'
    path.write_text(''.join(f'{name}="{value}"\n' for name, value in values.items()))
    return path


def reset(env: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ['bash', str(ROOT / 'scripts/reset_demo.sh'), str(env)], cwd=ROOT, capture_output=True, text=True,
        env=os.environ | {'DRY_RUN': '1'}, timeout=60
    )


def copies(result: subprocess.CompletedProcess) -> list[tuple[str, str]]:
    """The folders it would copy, from and to"""
    return [tuple(line.split()[-2:]) for line in result.stdout.splitlines() if 'rsync -a --delete' in line]


def test_the_dumps_parts_are_read_from_its_folder(site):
    result = reset(env_file(site))
    assert result.returncode == 0, result.stderr
    dump = site / 'dump'
    assert copies(result) == [
        (f'{dump}/files/', f'{site}/files/'),
        (f'{dump}/map_tiles/', f'{site}/map_tiles/'),
        (f'{dump}/map_boundaries/', f'{site}/map_boundaries/'),
    ]
    assert f'--from-path={dump} ' in result.stdout
    # the place search's database, whose places the API fetches again as it starts
    assert f"find {site}/gazetteer -maxdepth 1 -name gazetteer.sqlite* -delete" in result.stdout


@pytest.mark.parametrize('name', ['DEMO_FILES_DIR', 'DEMO_MAP_TILES_DIR', 'DEMO_MAP_BOUNDARIES_DIR'])
def test_a_setting_naming_a_part_elsewhere_is_refused_before_anything_stops(site, name):
    result = reset(env_file(site, **{name: site / 'elsewhere'}))
    assert result.returncode == 1
    assert f'sets {name} to {site}/elsewhere' in result.stderr
    assert 'systemctl stop' not in result.stdout


def test_settings_naming_the_parts_where_they_are_are_accepted(site):
    dump = site / 'dump'
    result = reset(env_file(
        site, DEMO_DUMP_DIR=f'{dump}/', DEMO_FILES_DIR=dump / 'files', DEMO_MAP_TILES_DIR=f'{dump}/map_tiles/',
        DEMO_MAP_BOUNDARIES_DIR=dump / 'map_boundaries'
    ))
    assert result.returncode == 0, result.stderr
    assert len(copies(result)) == 3


def test_a_dump_without_its_files_is_refused_before_anything_stops(site):
    (site / 'dump/files').rmdir()
    result = reset(env_file(site))
    assert result.returncode == 1
    assert f'no files at {site}/dump/files' in result.stderr
    assert 'systemctl stop' not in result.stdout


def test_a_dump_without_maps_is_reset_leaving_the_sites_maps(site):
    (site / 'dump/map_tiles').rmdir()
    result = reset(env_file(site))
    assert result.returncode == 0, result.stderr
    assert copies(result) == [(f'{site}/dump/files/', f'{site}/files/')]
    assert f'No maps in {site}/dump/map_tiles and {site}/dump/map_boundaries' in result.stdout


def test_a_site_without_a_place_search_folder_is_reset_without_it(site):
    result = reset(env_file(site, GAZETTEER_PATH=''))
    assert result.returncode == 0, result.stderr
    assert 'No places reset' in result.stdout and 'gazetteer.sqlite' not in result.stdout
