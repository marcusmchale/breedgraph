"""
The data bundle: the extracted and curated files the migration loads (README §1), packed to be copied to the server.

Extraction runs where the legacy BreedCAFS database is; loading runs where BreedGraph is. `bundle` packs exactly the
input files, with a manifest of their checksums, and nothing the migration writes (the *_ids.csv mappings,
factor_records.csv, the curve data files, the validation report). `unbundle` checks every file against the manifest
and unpacks them into an empty data directory, for BREEDCAFS_DATA_DIR.

The bundle holds Person data (README §1.7): it is written readable by its owner only. Copy it securely,
and delete it once the artefacts are kept (README §13).
"""
import hashlib
import io
import json
import os
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

MANIFEST = 'MANIFEST.json'
FORMAT = 1

# The files the migration and validation read, as extraction and curation leave them
INPUT_FILES = (
    'attribution_persons.csv',
    'branch_strata.csv',
    'curves.csv',
    'field_farm_region_country.csv',
    'field_lat_long.csv',
    'field_layout_types.csv',
    'field_names.csv',
    'input_details_curated.csv',
    'input_subjects.csv',
    'item_name_subject_sources_sinks.csv',
    'item_variety.csv',
    'persons.csv',
    'records.csv',
    'sample_positions.csv',
    'skipped_items.csv',
    'submissions.csv',
    'submitter_persons.csv',
    'unit_positions.csv',
    'varieties.csv',
)


class BundleError(ValueError):
    """A bundle can't be made or unpacked as asked"""


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def git_commit() -> str | None:
    """The commit of the source checkout the bundle is made from, if it is one"""
    try:
        return subprocess.run(
            ['git', 'rev-parse', 'HEAD'], cwd=Path(__file__).parent, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def bundle(data_dir: Path, out: Path) -> dict:
    """Packs the input files of data_dir into out (.tar.gz), readable by its owner only. Returns the manifest."""
    missing = [name for name in INPUT_FILES if not (data_dir / name).is_file()]
    if missing:
        raise BundleError(f"Input files missing from {data_dir}: {missing}")
    if out.exists():
        raise BundleError(f"{out} exists: remove it or choose another path")

    contents = {name: (data_dir / name).read_bytes() for name in INPUT_FILES}
    manifest = {
        'format': FORMAT,
        'created': datetime.now(timezone.utc).isoformat(),
        'source_commit': git_commit(),
        'files': [{'name': name, 'size': len(content), 'sha256': sha256(content)} for name, content in contents.items()],
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as f, tarfile.open(fileobj=f, mode='w:gz') as archive:
        for name, content in [(MANIFEST, json.dumps(manifest, indent=2).encode())] + list(contents.items()):
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mode = 0o600
            archive.addfile(info, io.BytesIO(content))
    return manifest


def unbundle(archive_path: Path, data_dir: Path) -> dict:
    """
    Checks the bundle against its manifest and unpacks it into data_dir, which must be empty or not exist.
    Nothing is written unless every file is present, expected and intact. Returns the manifest.
    """
    if data_dir.exists() and any(data_dir.iterdir()):
        raise BundleError(f"{data_dir} is not empty: unpack into a new directory")

    with tarfile.open(archive_path, mode='r:gz') as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if len(set(names)) != len(names) or any(not member.isfile() for member in members):
            raise BundleError("The bundle must hold only files, each once")
        contents = {member.name: archive.extractfile(member).read() for member in members}

    if MANIFEST not in contents:
        raise BundleError(f"The bundle has no {MANIFEST}")
    manifest = json.loads(contents.pop(MANIFEST))
    if manifest.get('format') != FORMAT:
        raise BundleError(f"Unknown bundle format {manifest.get('format')}")
    expected = {entry['name']: entry for entry in manifest['files']}
    if set(expected) != set(INPUT_FILES):
        raise BundleError(
            f"The bundle's files differ from the migration's inputs: "
            f"missing {sorted(set(INPUT_FILES) - set(expected))}, unexpected {sorted(set(expected) - set(INPUT_FILES))}"
        )
    if set(contents) != set(expected):
        raise BundleError(f"The bundle's files differ from its manifest: {sorted(set(contents) ^ set(expected))}")
    damaged = [
        name for name, content in contents.items()
        if len(content) != expected[name]['size'] or sha256(content) != expected[name]['sha256']
    ]
    if damaged:
        raise BundleError(f"Files don't match their checksums: {sorted(damaged)}")

    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name, content in [(MANIFEST, json.dumps(manifest, indent=2).encode())] + list(contents.items()):
        descriptor = os.open(data_dir / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as f:
            f.write(content)
    return manifest
