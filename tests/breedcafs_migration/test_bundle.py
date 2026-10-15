"""The data bundle that carries the extracted BreedCAFS data to the server. No database is used."""
import io
import json
import stat
import tarfile

import pytest

from breedcafs_migration.bundle import bundle, unbundle, BundleError, INPUT_FILES, MANIFEST


@pytest.fixture
def data_dir(tmp_path):
    """Every input file, and the outputs a run leaves beside them"""
    data = tmp_path / 'data'
    data.mkdir()
    for name in INPUT_FILES:
        (data / name).write_text(f"header\n{name} row\n")
    for output in ('unit_ids.csv', 'factor_records.csv', 'validation_report.md', 'fluorescence_curves_x.csv'):
        (data / output).write_text("output\n")
    return data


def test_round_trip_carries_only_the_inputs(data_dir, tmp_path):
    archive = tmp_path / 'bundle.tar.gz'
    manifest = bundle(data_dir, archive)
    assert stat.S_IMODE(archive.stat().st_mode) == 0o600
    assert [entry['name'] for entry in manifest['files']] == list(INPUT_FILES)

    target = tmp_path / 'server' / 'data'
    unbundle(archive, target)
    assert sorted(p.name for p in target.iterdir()) == sorted([*INPUT_FILES, MANIFEST])
    for name in INPUT_FILES:
        assert (target / name).read_bytes() == (data_dir / name).read_bytes()
        assert stat.S_IMODE((target / name).stat().st_mode) == 0o600


def test_missing_input_is_refused(data_dir, tmp_path):
    (data_dir / 'records.csv').unlink()
    with pytest.raises(BundleError, match="records.csv"):
        bundle(data_dir, tmp_path / 'bundle.tar.gz')
    assert not (tmp_path / 'bundle.tar.gz').exists()


def test_existing_bundle_is_not_overwritten(data_dir, tmp_path):
    archive = tmp_path / 'bundle.tar.gz'
    archive.write_text("kept")
    with pytest.raises(BundleError, match="exists"):
        bundle(data_dir, archive)
    assert archive.read_text() == "kept"


def test_unbundle_needs_an_empty_directory(data_dir, tmp_path):
    archive = tmp_path / 'bundle.tar.gz'
    bundle(data_dir, archive)
    with pytest.raises(BundleError, match="not empty"):
        unbundle(archive, data_dir)


def rewrite(archive, out, change):
    """A copy of the bundle with change(name, content) -> content | None applied to each file (None drops it)"""
    with tarfile.open(archive, 'r:gz') as source, tarfile.open(out, 'w:gz') as target:
        for member in source.getmembers():
            content = change(member.name, source.extractfile(member).read())
            if content is not None:
                info = tarfile.TarInfo(member.name)
                info.size = len(content)
                target.addfile(info, io.BytesIO(content))


@pytest.mark.parametrize('change, error', [
    (lambda name, content: content + b"tampered\n" if name == 'records.csv' else content, "checksums"),
    (lambda name, content: None if name == 'persons.csv' else content, "differ from its manifest"),
    (lambda name, content: None if name == MANIFEST else content, "no MANIFEST"),
])
def test_damaged_bundles_are_refused_and_nothing_is_written(data_dir, tmp_path, change, error):
    archive = tmp_path / 'bundle.tar.gz'
    bundle(data_dir, archive)
    damaged = tmp_path / 'damaged.tar.gz'
    rewrite(archive, damaged, change)
    target = tmp_path / 'server'
    with pytest.raises(BundleError, match=error):
        unbundle(damaged, target)
    assert not target.exists()


def test_paths_and_links_are_refused(data_dir, tmp_path):
    archive = tmp_path / 'bundle.tar.gz'
    bundle(data_dir, archive)
    with tarfile.open(archive, 'r:gz') as source:
        members = [(m, source.extractfile(m).read()) for m in source.getmembers()]
    evil = tmp_path / 'evil.tar.gz'
    with tarfile.open(evil, 'w:gz') as target:
        for member, content in members:
            info = tarfile.TarInfo(member.name)
            info.size = len(content)
            target.addfile(info, io.BytesIO(content))
        link = tarfile.TarInfo('link')
        link.type = tarfile.SYMTYPE
        link.linkname = '/etc/passwd'
        target.addfile(link)
    with pytest.raises(BundleError, match="only files"):
        unbundle(evil, tmp_path / 'server')


def test_manifest_records_the_checksums(data_dir, tmp_path):
    archive = tmp_path / 'bundle.tar.gz'
    bundle(data_dir, archive)
    with tarfile.open(archive, 'r:gz') as source:
        manifest = json.loads(source.extractfile(MANIFEST).read())
    entry = next(e for e in manifest['files'] if e['name'] == 'records.csv')
    assert entry['size'] == (data_dir / 'records.csv').stat().st_size and len(entry['sha256']) == 64
