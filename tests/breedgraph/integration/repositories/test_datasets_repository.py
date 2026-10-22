import pytest
from numpy import datetime64

from breedgraph.domain.model.contributions import Contribution
from breedgraph.domain.model.ontology import OntologyEntryLabel

from breedgraph.domain.model.datasets import DatasetInput, DataRecordInput, RecordGroup
from breedgraph.custom_exceptions import NoResultFoundError

async def create_dataset(uow_factory, user_id, team_id, dataset_input):
    async with uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
        await uow.repositories.datasets.create(dataset_input)
        await uow.commit()

@pytest.mark.asyncio(loop_scope="session")
async def test_create_and_get(
        uow_factory,
        dataset_build_context
):
    user_id = dataset_build_context['user_id']
    concept_id = dataset_build_context['concept_id']
    study_id = dataset_build_context['study_id']
    dataset_input = DatasetInput(
        concept=concept_id,
        study=study_id
    )
    await create_dataset(uow_factory, user_id, dataset_build_context['team_id'], dataset_input)
    async with uow_factory.get_uow(user_id=user_id) as uow:
        async for d in uow.repositories.datasets.get_all():
            assert d.concept == dataset_input.concept
            assert d.study == dataset_input.study
            break
        else:
            raise NoResultFoundError("Couldn't find created dataset by get all")

        async for d in uow.repositories.datasets.get_all(concept_ids=[concept_id]):
            assert d.study == dataset_input.study
            break
        else:
            raise NoResultFoundError("Couldn't find created dataset by get all with ontology id")


@pytest.mark.asyncio(loop_scope="session")
async def test_update_contributions(
        uow_factory,
        dataset_build_context
):
    user_id = dataset_build_context['user_id']
    concept_id = dataset_build_context['concept_id']
    study_id = dataset_build_context['study_id']
    person_id = dataset_build_context['person_id']
    dataset_input = DatasetInput(
        concept=concept_id,
        study=study_id
    )
    await create_dataset(uow_factory, user_id, dataset_build_context['team_id'], dataset_input)

    async with uow_factory.get_uow(user_id=user_id) as uow:
        role_ids = [
            (await uow.ontology.get_entry(name=name, label=OntologyEntryLabel.ROLE)).id
            for name in ('Investigation', 'Data curation')
        ]
        dataset = await uow.repositories.datasets.get()
        dataset.contributions.append(Contribution(person=person_id))
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        dataset = await uow.repositories.datasets.get(dataset_id=dataset.id)
        assert dataset.contributions == [Contribution(person=person_id, roles=[])]

        # roles can be declared later
        dataset.contributions[0].roles = role_ids
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        dataset = await uow.repositories.datasets.get(dataset_id=dataset.id)
        assert sorted(dataset.contributions[0].roles) == sorted(role_ids)

        dataset.contributions.pop(0)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        dataset = await uow.repositories.datasets.get(dataset_id=dataset.id)
        assert dataset.contributions == []


@pytest.mark.asyncio(loop_scope="session")
async def test_add_record(
        uow_factory,
        dataset_build_context
):
    user_id = dataset_build_context['user_id']
    concept_id = dataset_build_context['concept_id']
    study_id = dataset_build_context['study_id']
    dataset_input = DatasetInput(
        concept=concept_id,
        study=study_id
    )
    await create_dataset(uow_factory, user_id, dataset_build_context['team_id'], dataset_input)

    unit_id = dataset_build_context['unit_id']
    async with uow_factory.get_uow(user_id=user_id) as uow:
        dataset = await uow.repositories.datasets.get()
        if dataset is None:
            raise ValueError("Dataset not found to add record")
        new_record = DataRecordInput(unit=unit_id, value='50')
        dataset.records.append(new_record)
        await uow.repositories.datasets.update_seen()

        retrieved = await uow.repositories.datasets.get(dataset_id = dataset.id)
        if not retrieved:
            raise ValueError("Dataset not found to compare length of records")
        assert len(retrieved.records) == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_create_with_records(
        uow_factory,
        dataset_build_context
):
    """The dataset created holds its records, with their ids, as a read gives them; committing it adds none"""
    unit_id = dataset_build_context['unit_id']
    grouping_id = dataset_build_context['grouping_ids'][0]
    dataset_input = DatasetInput(
        concept=dataset_build_context['concept_id'],
        study=dataset_build_context['study_id'],
        records=[
            DataRecordInput(unit=unit_id, value='50', start=datetime64('2021-05-03T10:30'), groups=[RecordGroup(id=grouping_id, code='R1')]),
            DataRecordInput(unit=unit_id, value='60', end=datetime64('2021'))
        ]
    )
    async with uow_factory.get_uow(user_id=dataset_build_context['user_id'], write_team=dataset_build_context['team_id']) as uow:
        created = await uow.repositories.datasets.create(dataset_input)
        await uow.commit()
    async with uow_factory.get_uow(user_id=dataset_build_context['user_id']) as uow:
        stored = await uow.repositories.datasets.get(dataset_id=created.id)

    def fields(records):
        """Each record's fields, in id order: a read gives the records in no particular order"""
        return sorted((r.id, r.unit, r.value, str(r.start), str(r.end), list(r.groups), list(r.references)) for r in records)

    assert None not in {record.id for record in created.records}
    first, second = sorted(record.id for record in created.records)
    assert fields(created.records) == [
        (first, unit_id, '50', '2021-05-03T10:30', 'None', [RecordGroup(id=grouping_id, code='R1')], []),
        (second, unit_id, '60', 'None', '2021', [], []),
    ]
    assert fields(stored.records) == fields(created.records)
