"""
The wheel carries every file its packages read: each file in a package that isn't Python is matched by that package's
package-data in pyproject.toml, as setuptools globs it, or is one left out on purpose. An installed worker reads its
files beside its code, so one left out fails only once deployed (the analysis worker's models.R). Runs with
--noconftest.
"""
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / 'src'

# files in a package that nothing reads, so not in the wheel
LEFT_OUT = {
    'breedgraph': {'entrypoints/fastapi/templates/index.html'},
}


def package_data() -> dict[str, list[str]]:
    with open(ROOT / 'pyproject.toml', 'rb') as f:
        return tomllib.load(f)['tool']['setuptools']['package-data']


def data_files(package: str) -> set[str]:
    folder = SRC / package
    return {
        path.relative_to(folder).as_posix() for path in folder.rglob('*')
        if path.is_file() and path.suffix not in {'.py', '.pyc'} and '__pycache__' not in path.parts
    }


def matched(package: str, patterns: list[str]) -> set[str]:
    folder = SRC / package
    return {path.relative_to(folder).as_posix() for pattern in patterns for path in folder.glob(pattern)}


def test_every_package_with_files_has_package_data():
    packages = {path.name for path in SRC.iterdir() if (path / '__init__.py').exists()} - {'breedcafs_migration'}
    assert packages <= set(package_data()), 'each package built into the wheel names its files, even none'


def test_every_file_a_package_reads_is_in_the_wheel():
    for package, patterns in package_data().items():
        missing = data_files(package) - matched(package, patterns) - LEFT_OUT.get(package, set())
        assert not missing, f'{package} package-data leaves out {sorted(missing)}'


def test_the_files_left_out_are_still_there():
    for package, files in LEFT_OUT.items():
        assert files <= data_files(package), 'remove what no longer exists from LEFT_OUT'
