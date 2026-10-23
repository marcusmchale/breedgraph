"""
Data citing removed ontology entries is still read, edited and analysed, but nothing new links to them
(OntologyApplicationService.get_cited_entry and require_entries)
"""
import pytest
import pytest_asyncio

from breedgraph.custom_exceptions import IllegalOperationError
from breedgraph.domain.commands.layout_trees import CreateLayout, UpdateLayout
from breedgraph.domain.commands.unit_graphs import CreateUnit, UpdateUnit
from breedgraph.domain.events.datasets import DatasetSubmitted, DatasetRecordsSubmitted, DatasetUpdateSubmitted
from breedgraph.domain.model import SubmissionStatus
from breedgraph.domain.model.accounts import OntologyRole
from breedgraph.domain.model.layout_trees import LayoutInput
from breedgraph.domain.model.location_trees import LocationInput
from breedgraph.domain.model.ontology import (
    OntologyEntryLabel, LifecyclePhase, VersionChange, ScaleType, ObservationMethodType, AxisType,
    SubjectInput, TraitInput, ObservationMethodInput, ScaleInput, ScaleCategory, VariableInput,
    LocationTypeInput, LayoutTypeInput
)
from breedgraph.domain.model.unit_graphs import UnitInput, Position
from breedgraph.service_layer.application.analysis_context import AnalysisContextLoader

from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.dataset_builder import DatasetBuilder
from tests.breedgraph.scenarios.location_tree_builder import LocationTreeBuilder
from tests.breedgraph.scenarios.ontology_builder import OntologyBuilder
from tests.breedgraph.scenarios.program_builder import ProgramBuilder


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def context(isolated_state, uow_factory, state_store) -> dict:
    """
    A dataset of an ordinal variable with a record on a tree, positioned in a grid layout at a plot; then the variable,
    its components, the subject, the location type and the layout type are removed
    """
    account = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations(ontology_role=OntologyRole.EDITOR)
    user_id, team_id = account['user_id'], account['team_id']
    record_group_types = await OntologyBuilder(uow_factory=uow_factory).record_group_types(user_id=user_id)
    program = await ProgramBuilder(uow_factory=uow_factory).program_trial_study(
        user_id, team_id,
        replicate_type=record_group_types['ontology_record_group_replicate'],
        batch_type=record_group_types['ontology_record_group_batch']
    )
    async with uow_factory.get_uow(user_id=user_id) as uow:
        ontology = uow.ontology
        subject = await ontology.create_subject(SubjectInput(name="Removed Tree"))
        trait = await ontology.create_trait(TraitInput(name="Removed Vigour"), subjects=[subject.id])
        method = await ontology.create_entry(
            ObservationMethodInput(name="Removed Look", observation_type=ObservationMethodType.ESTIMATION)
        )
        scale = await ontology.create_scale(ScaleInput(
            name="Removed Classes", scale_type=ScaleType.ORDINAL,
            categories=[ScaleCategory("Removed Low"), ScaleCategory("Removed High")]
        ))
        variable = await ontology.create_variable(
            VariableInput(name="Removed Vigour Class"), trait_id=trait.id, observation_method_id=method.id, scale_id=scale.id
        )
        plot_type = await ontology.create_entry(LocationTypeInput(name="Removed Plot"))
        grid = await ontology.create_entry(LayoutTypeInput(name="Removed Grid", axes=[AxisType.ORDINAL, AxisType.ORDINAL]))
        await ontology.commit_version(version_change=VersionChange.MINOR)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
        location_tree = await LocationTreeBuilder(uow_factory=uow_factory, state_store=state_store).location_tree_from_country(uow)
        location_tree.add_location(LocationInput(name="Removed Plot 1", type=plot_type.id), parent_id=location_tree.get_root_id())
        await uow.commit()
    plot_id = next(location_tree.yield_locations_by_type(plot_type.id)).id
    async with uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
        layout_tree = await uow.repositories.layout_trees.create(
            LayoutInput(name="Removed Grid Layout", type=grid.id, location=plot_id, axes=["Row", "Column"])
        )
        await uow.commit()
    layout_id = layout_tree.root.id
    async with uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
        unit_graph = await uow.repositories.unit_graphs.create(UnitInput(
            name="Removed Tree 1", subject=subject.id,
            positions=[Position(location_id=plot_id, layout_id=layout_id, coordinates=[1, 1])]
        ))
        await uow.commit()
    unit_id = unit_graph.get_root_id()
    dataset_id = (await DatasetBuilder(uow_factory=uow_factory).dataset(
        user_id=user_id, team_id=team_id, concept_id=variable.id, study_id=program['study_id'],
        records=[DatasetBuilder.record_input(unit_id=unit_id, value="Removed Low")]
    ))['dataset_id']

    async with uow_factory.get_uow(user_id=user_id) as uow:
        await uow.ontology.deprecate_entries([
            variable.id, trait.id, method.id, scale.id, subject.id, plot_type.id, grid.id
        ])
        await uow.ontology.commit_version(version_change=VersionChange.MAJOR)
        await uow.commit()
    return {
        'user_id': user_id, 'team_id': team_id, 'study_id': program['study_id'], 'variable_id': variable.id,
        'scale_id': scale.id, 'subject_id': subject.id, 'grid_id': grid.id, 'plot_id': plot_id,
        'layout_id': layout_id, 'unit_id': unit_id, 'dataset_id': dataset_id
    }


async def submit(bus, state_store, event_queue, user_id: int, submission: dict, event_class, **event_fields):
    """The submission's status and errors once handled"""
    submission_id = await state_store.store_submission(agent_id=user_id, submission=submission)
    await bus.handle(event_class(agent_id=user_id, submission_id=submission_id, **event_fields))
    await event_queue.join()
    status = await state_store.get_status(agent_id=user_id, key=submission_id)
    errors = await state_store.get_errors(agent_id=user_id, key=submission_id)
    item_errors = await state_store.get_submission_item_errors(agent_id=user_id, submission_id=submission_id)
    return status, errors, item_errors


@pytest.mark.asyncio(loop_scope="session")
async def test_removed_entries_are_read_as_cited(uow_factory, context):
    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        assert await uow.ontology.get_entry(entry_id=context['variable_id']) is None, "not in the current version"
        scale = await uow.ontology.get_concept_scale(context['variable_id'])
        assert scale.id == context['scale_id'] and scale.phase is LifecyclePhase.REMOVED
        assert [category.name for category in scale.categories] == ["Removed Low", "Removed High"]
        subject = await uow.ontology.get_cited_entry(context['subject_id'], label=OntologyEntryLabel.SUBJECT)
        assert subject.name == "Removed Tree"
        concept = await AnalysisContextLoader(uow, user_id=context['user_id'], warnings=[])._load_concept(context['variable_id'])
        assert concept.categories == ["Removed Low", "Removed High"] and not concept.factor


@pytest.mark.asyncio(loop_scope="session")
async def test_a_dataset_of_a_removed_variable_is_still_edited(bus, state_store, event_queue, context):
    status, errors, item_errors = await submit(
        bus, state_store, event_queue, context['user_id'],
        {'dataset_id': context['dataset_id'], 'records': [{'unit_id': context['unit_id'], 'value': "Removed High"}]},
        DatasetRecordsSubmitted
    )
    assert status is SubmissionStatus.COMPLETED and not errors and not item_errors
    status, errors, item_errors = await submit(
        bus, state_store, event_queue, context['user_id'],
        {'dataset_id': context['dataset_id'], 'contributions': []},
        DatasetUpdateSubmitted
    )
    assert status is SubmissionStatus.COMPLETED and not errors and not item_errors


@pytest.mark.asyncio(loop_scope="session")
async def test_no_new_dataset_of_a_removed_variable(bus, state_store, event_queue, context):
    status, errors, _ = await submit(
        bus, state_store, event_queue, context['user_id'],
        {'study_id': context['study_id'], 'concept_id': context['variable_id'], 'records': []},
        DatasetSubmitted, write_team=context['team_id']
    )
    assert status is SubmissionStatus.FAILED
    assert "Removed from the ontology" in str(errors) and "Removed Vigour Class" in str(errors)


@pytest.mark.asyncio(loop_scope="session")
async def test_units_are_placed_in_a_layout_of_a_removed_type_but_not_given_a_removed_subject(bus, context):
    position = {'location_id': context['plot_id'], 'layout_id': context['layout_id'], 'coordinates': [2, 2]}
    await bus.handle(CreateUnit(agent_id=context['user_id'], write_team=context['team_id'], name="Removed Tree 2", **position))
    with pytest.raises(IllegalOperationError, match=r"Removed from the ontology.*Subject \d+ \(Removed Tree\)"):
        await bus.handle(CreateUnit(
            agent_id=context['user_id'], write_team=context['team_id'], subject_id=context['subject_id'], **position
        ))
    # a unit keeps the removed subject it has
    await bus.handle(UpdateUnit(agent_id=context['user_id'], unit_id=context['unit_id'], name="Removed Tree One"))


@pytest.mark.asyncio(loop_scope="session")
async def test_a_layout_of_a_removed_type_is_updated_but_no_new_one_made(bus, context):
    await bus.handle(UpdateLayout(
        agent_id=context['user_id'], layout_id=context['layout_id'], location_id=None, type_id=context['grid_id'],
        name=None, axes=["Row number", "Column number"], parent=None
    ))
    with pytest.raises(IllegalOperationError, match=r"Removed from the ontology.*\(Removed Grid\)"):
        await bus.handle(CreateLayout(
            agent_id=context['user_id'], write_team=context['team_id'], type_id=context['grid_id'],
            location_id=context['plot_id'], name="Another Grid", axes=["Row", "Column"]
        ))
