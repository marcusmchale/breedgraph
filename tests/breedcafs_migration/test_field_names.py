"""Fields named after the farmers who host them are migrated under neutral names (field_names.csv, README §3)"""
import pytest

from breedcafs_migration import locations, units


def write(path, name, text):
    (path / name).write_text(text, encoding='utf-8')


@pytest.fixture
def data_dir(tmp_path):
    # values as exported: wrapped in extra quotes
    write(tmp_path, 'field_farm_region_country.csv', (
        'field_uid,field,farm,region,country\n'
        '1,"""Ana Perez""","""Las Colinas""","""Boaco""","""Nicaragua"""\n'
        '2,"""ED1""","""Muoi Noi""","""Son La""","""Vietnam"""\n'
    ))
    write(tmp_path, 'field_names.csv', 'field_uid,breedcafs_name,name\n1,Ana Perez,Las Colinas field\n')
    return tmp_path


def test_fields_named_after_people_get_neutral_names(data_dir):
    fields = {row['field_uid']: row['field'] for row in locations.read_fields(data_dir)}
    assert fields == {'1': 'Las Colinas field', '2': 'ED1'}


def test_a_field_unit_takes_its_fields_neutral_name(data_dir, monkeypatch):
    write(data_dir, 'skipped_items.csv', 'item_uid,reason\n')
    write(data_dir, 'item_name_subject_sources_sinks.csv', (
        'item_uid,name,subject,source_items,sink_items\n'
        '1,"""Ana Perez""","""Field""",[],[]\n'
        '1_T1,"""T1""","""Tree""",[1],[]\n'
    ))
    monkeypatch.setattr(units, 'BREEDCAFS_DATA_DIR', data_dir)
    items = units.read_items()
    assert (items['1'].name, items['1_T1'].name) == ("Las Colinas field", "T1")


def test_a_rename_of_another_name_is_refused(data_dir):
    write(data_dir, 'field_names.csv', 'field_uid,breedcafs_name,name\n1,Someone Else,Las Colinas field\n')
    with pytest.raises(ValueError, match="renames field 1 from 'Someone Else', but it is 'Ana Perez'"):
        locations.read_fields(data_dir)


def test_no_file_renames_nothing(data_dir):
    (data_dir / 'field_names.csv').unlink()
    assert locations.renamed_fields(data_dir) == {}
    assert {row['field'] for row in locations.read_fields(data_dir)} == {'Ana Perez', 'ED1'}
