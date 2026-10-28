"""
The wheel carries every file its packages read and installs every package they import. Each file in a package that
isn't Python is matched by that package's package-data in pyproject.toml, as setuptools globs it, or is one left out on
purpose; and each package each of breedgraph, the archive worker and the analysis worker imports is installed by the
extra it is deployed with, directly or as a requirement of one. An installed worker reads its files beside its code
(the analysis worker's models.R), and the API is installed from a wheelhouse of its extra alone, so what is left out
fails only once deployed. The requirements are followed through the packages installed here. Runs with --noconftest.
"""
import ast
import sys
import tomllib
from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / 'src'

# files in a package that nothing reads, so not in the wheel
LEFT_OUT = {
    'breedgraph': {'entrypoints/fastapi/templates/index.html'},
}

# each package and the extra it is installed with (docs/deployment.md; instance/*.service)
DEPLOYED_WITH = {
    'breedgraph': 'server', 'archive_worker': 'worker', 'analysis_worker': 'analysis_worker', 'map_worker': 'worker'
}
OWN = {'breedgraph', 'archive_worker', 'analysis_worker', 'map_worker', 'breedcafs_migration'}
WORKERS = ('archive_worker', 'analysis_worker', 'map_worker')


def pyproject() -> dict:
    with open(ROOT / 'pyproject.toml', 'rb') as f:
        return tomllib.load(f)


def package_data() -> dict[str, list[str]]:
    return pyproject()['tool']['setuptools']['package-data']


def data_files(package: str) -> set[str]:
    folder = SRC / package
    return {
        path.relative_to(folder).as_posix() for path in folder.rglob('*')
        if path.is_file() and path.suffix not in {'.py', '.pyc'} and '__pycache__' not in path.parts
    }


def matched(package: str, patterns: list[str]) -> set[str]:
    folder = SRC / package
    return {path.relative_to(folder).as_posix() for pattern in patterns for path in folder.glob(pattern)}


def installed_by(extra: str) -> set[str]:
    """The distributions an extra installs, its requirements' requirements followed as far as they are installed."""
    extras = pyproject()['project']['optional-dependencies']
    found, todo = set(), [Requirement(line) for line in extras[extra]]
    while todo:
        requirement = todo.pop()
        if requirement.marker and not requirement.marker.evaluate({'extra': ''}):
            continue
        name = canonicalize_name(requirement.name)
        if name == 'breedgraph':
            todo += [Requirement(line) for other in requirement.extras for line in extras[other]]
        elif name not in found:
            found.add(name)
            try:
                todo += [Requirement(line) for line in metadata.requires(name) or []]
            except metadata.PackageNotFoundError:
                pass
    return found


def imported(package: str) -> dict[str, set[str]]:
    """The modules a package imports from outside itself and the standard library, and the files importing each."""
    modules = {}
    for path in (SRC / package).rglob('*.py'):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                top = name.split('.')[0]
                if top not in sys.stdlib_module_names and top not in OWN:
                    modules.setdefault(top, set()).add(path.relative_to(SRC).as_posix())
    return modules


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


def test_every_package_a_package_imports_is_installed_with_it():
    distributions = metadata.packages_distributions()
    for package, extra in DEPLOYED_WITH.items():
        installed = installed_by(extra)
        missing = {
            module: sorted(files) for module, files in imported(package).items()
            if not {canonicalize_name(name) for name in distributions.get(module, [module])} & installed
        }
        assert not missing, f'{package} imports what breedgraph[{extra}] does not install: {missing}'


def own_imports(package: str, path: Path | None = None) -> dict[str, set[str]]:
    """The packages of our own a package (or one of its files) imports, and the files importing each"""
    modules = {}
    for file in [path] if path else (SRC / package).rglob('*.py'):
        for node in ast.walk(ast.parse(file.read_text())):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                top = name.split('.')[0]
                if top in OWN and top != package:
                    modules.setdefault(top, set()).add(file.relative_to(SRC).as_posix())
    return modules


def test_the_workers_import_nothing_of_breedgraph():
    """breedgraph's modules need the API's packages and environment, which a worker's server doesn't have"""
    for worker in WORKERS:
        assert 'breedgraph' not in own_imports(worker), f'{worker} imports breedgraph: {own_imports(worker)}'


def test_what_the_api_shares_with_the_map_worker_needs_only_httpx():
    """The API imports map_worker.fetching, so it reads no environment and needs nothing the API lacks"""
    path = SRC / 'map_worker' / 'fetching.py'
    tree = ast.parse(path.read_text())
    tops = {
        name.split('.')[0]
        for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
        for name in ([alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ''])
    }
    assert tops - set(sys.stdlib_module_names) == {'httpx'}
    used = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)} \
        | {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not used & {'environ', 'getenv'}
