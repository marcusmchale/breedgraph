"""
Updating records. A record on a complex scale cites references rather than holding a value: none is created citing
nothing, and no update leaves one citing nothing, so dropping a record's last reference means removing the record. An
update gives only what changes: its start, end and value are optional, as in RecordUpdate, and left as they are when
not given, but a start or end given as null removes it, and a unit given moves the record.
"""
import pytest
from numpy import datetime64

from breedgraph.domain.importers import DatasetUpdateImport
from breedgraph.domain.model.datasets import DatasetInput, DataRecordInput, DataRecordStored, DataRecordUpdate
from breedgraph.domain.model.ontology import ScaleStored, ScaleType

COMPLEX = ScaleStored(id=1, name="Reflectance spectrum", scale_type=ScaleType.COMPLEX)
NUMERICAL = ScaleStored(id=2, name="Millimeters", scale_type=ScaleType.NUMERICAL)


def dataset(
        value: str | None = None, references: list[int] | None = None, start: str | None = None, end: str | None = None
) -> DatasetInput:
    """A dataset holding one stored record, 10, on unit 5"""
    with_record = DatasetInput(concept=1, study=1)
    with_record.records = [DataRecordStored(
        id=10, unit=5, value=value, references=references,
        start=datetime64(start) if start else None, end=datetime64(end) if end else None
    )]
    return with_record


def test_a_new_record_on_a_complex_scale_must_cite_a_reference():
    assert list(dataset().add_records([DataRecordInput(unit_id=5, value='0.5')], COMPLEX, None, [])) == [
        "Complex scale records require at least one reference"
    ]


def test_an_update_cannot_leave_a_record_on_a_complex_scale_citing_nothing():
    stored = dataset(references=[7])
    assert list(stored.update_records([DataRecordUpdate(id=10, reference_ids=[])], COMPLEX, None, [])) == [
        "Complex scale records require at least one reference: remove the record instead"
    ]
    assert stored.records[0].references == [7]


def test_an_update_replaces_the_references_of_a_record_on_a_complex_scale():
    stored = dataset(references=[7])
    assert list(stored.update_records([DataRecordUpdate(id=10, reference_ids=[8, 9])], COMPLEX, None, [])) == [None]
    assert stored.records[0].references == [8, 9]


def test_an_update_giving_no_references_leaves_them():
    stored = dataset(references=[7])
    assert list(stored.update_records([DataRecordUpdate(id=10, start='2025-06-13')], COMPLEX, None, [])) == [None]
    assert (str(stored.records[0].start), stored.records[0].references) == ('2025-06-13', [7])


def test_a_record_holding_a_value_may_cite_nothing():
    stored = dataset(value='310', references=[7])
    assert list(stored.update_records([DataRecordUpdate(id=10, value='311', reference_ids=[])], NUMERICAL, None, [])) == [None]
    assert (stored.records[0].value, stored.records[0].references) == ('311', [])


def test_an_update_giving_only_references_leaves_the_rest():
    (update,) = DatasetUpdateImport(dataset_id=1, records=[{'id': 10, 'reference_ids': [8]}]).records_to_update()
    stored = dataset(references=[7], start='2025-06-12')
    assert list(stored.update_records([update], COMPLEX, None, [])) == [None]
    assert (str(stored.records[0].start), stored.records[0].references) == ('2025-06-12', [8])


def test_an_update_giving_only_a_value_leaves_the_rest():
    (update,) = DatasetUpdateImport(dataset_id=1, records=[{'id': 10, 'value': '311'}]).records_to_update()
    stored = dataset(value='310', start='2025-06-12')
    assert list(stored.update_records([update], NUMERICAL, None, [])) == [None]
    assert (stored.records[0].value, str(stored.records[0].start)) == ('311', '2025-06-12')


def test_an_update_giving_the_start_as_null_removes_it():
    (update,) = DatasetUpdateImport(dataset_id=1, records=[{'id': 10, 'start': None}]).records_to_update()
    assert update.cleared == {'start'}
    stored = dataset(value='310', start='2025-06-12', end='2025-06-30')
    assert list(stored.update_records([update], NUMERICAL, None, [])) == [None]
    assert (stored.records[0].start, str(stored.records[0].end), stored.records[0].value) == (None, '2025-06-30', '310')


def test_an_update_giving_the_end_as_null_removes_it():
    (update,) = DatasetUpdateImport(dataset_id=1, records=[{'id': 10, 'end': None}]).records_to_update()
    stored = dataset(value='310', start='2025-06-12', end='2025-06-30')
    assert list(stored.update_records([update], NUMERICAL, None, [])) == [None]
    assert (str(stored.records[0].start), stored.records[0].end) == ('2025-06-12', None)


def test_only_a_start_or_end_can_be_cleared():
    with pytest.raises(ValueError, match="Only a record's start and end can be cleared, not value"):
        DataRecordUpdate(id=10, cleared={'value'})


def test_an_update_giving_a_unit_moves_the_record():
    (update,) = DatasetUpdateImport(dataset_id=1, records=[{'id': 10, 'unit_id': 6}]).records_to_update()
    stored = dataset(value='310', start='2025-06-12')
    assert list(stored.update_records([update], NUMERICAL, None, [])) == [None]
    assert (stored.records[0].unit, stored.records[0].value, str(stored.records[0].start)) == (6, '310', '2025-06-12')
