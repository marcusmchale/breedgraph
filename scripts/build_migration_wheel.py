#!/usr/bin/env python3
"""
Build the BreedCAFS migration as its own wheel (breedcafs-migration), to install on the server only for the migration.

Only the package's Python files are copied into a temporary project and built there, so nothing else in
src/breedcafs_migration (private_notes.md, the extraction docs and Cypher, caches) can get into the wheel; the wheel's
contents are then checked. The BreedCAFS data never goes in a wheel: it travels as the bundle (breedcafs-migration
bundle, RUNBOOK §1).

    python scripts/build_migration_wheel.py            # writes dist/breedcafs_migration-<version>-py3-none-any.whl

On the server, after installing breedgraph[server] from its wheelhouse (README):

    python -m pip install --no-deps breedcafs_migration-<version>-py3-none-any.whl
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
PACKAGE = 'breedcafs_migration'


def project_toml(version: str) -> str:
    return f'''[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project]
name = "breedcafs-migration"
version = "{version}"
description = "Migration of the legacy BreedCAFS data into BreedGraph"
requires-python = ">=3.12"
dependencies = ["breedgraph[api]=={version}"]

[project.scripts]
breedcafs-migration = "{PACKAGE}.main:cli"

[tool.setuptools]
include-package-data = false

[tool.setuptools.packages.find]
include = ["{PACKAGE}*"]
'''


def copy_sources(build_dir: Path) -> list[str]:
    """The package's Python files, and nothing else. Returns their paths in the package."""
    source = ROOT / 'src' / PACKAGE
    copied = []
    for path in sorted(source.rglob('*.py')):
        relative = path.relative_to(source)
        if '__pycache__' in relative.parts:
            continue
        target = build_dir / PACKAGE / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append(f"{PACKAGE}/{relative.as_posix()}")
    return copied


def check_wheel(wheel: Path, sources: list[str]) -> None:
    """The wheel holds exactly the copied Python files, and its metadata"""
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
    dist_info = [name for name in names if name.split('/')[0].endswith('.dist-info')]
    files = sorted(set(names) - set(dist_info))
    if files != sorted(sources):
        raise RuntimeError(
            f"The wheel's files differ from the package's Python files: "
            f"unexpected {sorted(set(files) - set(sources))}, missing {sorted(set(sources) - set(files))}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the BreedCAFS migration wheel")
    parser.add_argument('--outdir', type=Path, default=ROOT / 'dist', help="where to write the wheel (default dist/)")
    args = parser.parse_args()

    version = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']
    with tempfile.TemporaryDirectory() as build:
        build_dir = Path(build)
        (build_dir / 'pyproject.toml').write_text(project_toml(version))
        sources = copy_sources(build_dir)
        out = build_dir / 'dist'
        subprocess.run(
            [sys.executable, '-m', 'build', '--wheel', '--no-isolation', '--outdir', str(out), str(build_dir)],
            check=True
        )
        wheel, = out.glob('*.whl')
        check_wheel(wheel, sources)
        args.outdir.mkdir(parents=True, exist_ok=True)
        target = args.outdir / wheel.name
        shutil.copy2(wheel, target)
    print(f"Built {target}: {len(sources)} Python files, checked")


if __name__ == '__main__':
    main()
