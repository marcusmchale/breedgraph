"""
Records are of a variable or factor as it is defined, and hold values as its scale reads them: once records cite a
variable or factor, its trait, method and scale (a factor's condition, control method and scale) stay, and while
records cite a scale, its type stays (handlers.commands.ontologies.require_unrecorded_definition, require_recorded_scale)
"""
import pytest
import pytest_asyncio

from breedgraph.custom_exceptions import IllegalOperationError
from breedgraph.domain.commands.ontologies import UpdateVariable, UpdateFactor, UpdateScale, DeprecateOntologyEntries
from breedgraph.domain.model.accounts import OntologyRole
from breedgraph.domain.model.ontology import (
    VersionChange, ScaleType, ObservationMethodType, ControlMethodType, LifecyclePhase, OntologyRelationshipLabel,
    SubjectInput, TraitInput, ObservationMethodInput, ScaleInput, ScaleCategory, VariableInput,
    ConditionInput, ControlMethodInput, FactorInput
)
from breedgraph.domain.model.unit_graphs import UnitInput

from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.dataset_builder import DatasetBuilder
from tests.breedgraph.scenarios.ontology_builder import OntologyBuilder
from tests.breedgraph.scenarios.program_builder import ProgramBuilder


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def context(isolated_state, uow_factory) -> dict:
    """
    A variable and a factor with records, a variable without, and a scale nothing records: two of each component, so
    that each can be swapped
    """
    account = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations(ontology_role=OntologyRole.EDITOR)
    user_id, team_id = account['user_id'], account['team_id']
    record_group_types = await OntologyBuilder(uow_factory=uow_factory).record_group_types(user_id=user_id)
    program = await ProgramBuilder(uow_factory=uow_factory).program_trial_study(
        user_id, team_id,
        replicate_type=record_group_types['ontology_record_group_replicate'],
        batch_type=record_group_types['ontology_record_group_batch']
    )
    ids = {'user_id': user_id}
    async with uow_factory.get_uow(user_id=user_id) as uow:
        ontology = uow.ontology
        subject = await ontology.create_subject(SubjectInput(name="Measured Plant"))
        for key, name in (('trait', "Measured Height"), ('other_trait', "Measured Spread")):
            ids[key] = (await ontology.create_trait(TraitInput(name=name), subjects=[subject.id])).id
        for key, name in (('method', "Measured with Tape"), ('other_method', "Measured with Laser")):
            ids[key] = (await ontology.create_entry(
                ObservationMethodInput(name=name, observation_type=ObservationMethodType.MEASUREMENT)
            )).id
        for key, name in (('scale', "Measured Centimetres"), ('other_scale', "Measured Millimetres")):
            ids[key] = (await ontology.create_scale(ScaleInput(name=name, scale_type=ScaleType.NUMERICAL))).id
        ids['unrecorded_scale'] = (await ontology.create_scale(ScaleInput(name="Measured Notes", scale_type=ScaleType.TEXT))).id
        ids['variable'] = (await ontology.create_variable(
            VariableInput(name="Measured Height (cm)"),
            trait_id=ids['trait'], observation_method_id=ids['method'], scale_id=ids['scale']
        )).id
        ids['unrecorded_variable'] = (await ontology.create_variable(
            VariableInput(name="Measured Height (mm)"),
            trait_id=ids['trait'], observation_method_id=ids['method'], scale_id=ids['other_scale']
        )).id
        for key, name in (('condition', "Measured Watering"), ('other_condition', "Measured Shading")):
            ids[key] = (await ontology.create_condition(ConditionInput(name=name), subjects=[subject.id])).id
        control_method = await ontology.create_entry(
            ControlMethodInput(name="Measured Irrigation", control_type=ControlMethodType.MANAGEMENT)
        )
        ids['control_method'] = control_method.id
        ids['treatment_scale'] = (await ontology.create_scale(ScaleInput(
            name="Measured Treatments", scale_type=ScaleType.NOMINAL, categories=[ScaleCategory("Watered")]
        ))).id
        ids['factor'] = (await ontology.create_factor(
            FactorInput(name="Measured Watering Treatment"),
            ids['condition'], ids['control_method'], ids['treatment_scale']
        )).id
        await ontology.commit_version(version_change=VersionChange.MINOR)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
        unit_graph = await uow.repositories.unit_graphs.create(UnitInput(name="Measured Plant 1", subject=subject.id))
        await uow.commit()
    for concept, value in (('variable', "12.5"), ('factor', "Watered")):
        await DatasetBuilder(uow_factory=uow_factory).dataset(
            user_id=user_id, team_id=team_id, concept_id=ids[concept], study_id=program['study_id'],
            records=[DatasetBuilder.record_input(unit_id=unit_graph.get_root_id(), value=value)]
        )
    return ids


def update_variable(context, variable='variable', **changes) -> UpdateVariable:
    components = {'trait_id': context['trait'], 'observation_method_id': context['method'], 'scale_id': context['scale']}
    return UpdateVariable(
        agent_id=context['user_id'], ontology_entry_id=context[variable], **{**components, **changes}
    )


async def scale_of(uow_factory, context, variable: str) -> set[int]:
    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        return {
            r.target_id async for r in uow.ontology.get_relationships(
                source_ids=[context[variable]], labels=[OntologyRelationshipLabel.USES_SCALE],
                phases=[LifecyclePhase.DRAFT, LifecyclePhase.ACTIVE]
            )
        }


@pytest.mark.asyncio(loop_scope="session")
async def test_a_recorded_variable_keeps_its_trait_method_and_scale(bus, uow_factory, context):
    for change in (
            {'trait_id': context['other_trait']},
            {'observation_method_id': context['other_method']},
            {'scale_id': context['other_scale']},
    ):
        with pytest.raises(
                IllegalOperationError,
                match="Records cite Variable Measured Height \\(cm\\), so its trait, observation method and scale can't change"
        ):
            await bus.handle(update_variable(context, **change))
    assert await scale_of(uow_factory, context, 'variable') == {context['scale']}, "nothing changed"
    # what doesn't define it stays open
    await bus.handle(update_variable(context, name="Measured Plant Height (cm)", description="To the highest leaf"))
    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        variable = await uow.ontology.get_entry(entry_id=context['variable'])
    assert (variable.name, variable.description) == ("Measured Plant Height (cm)", "To the highest leaf")


@pytest.mark.asyncio(loop_scope="session")
async def test_a_variable_without_records_can_be_redefined(bus, uow_factory, context):
    await bus.handle(update_variable(context, variable='unrecorded_variable', scale_id=context['scale']))
    assert await scale_of(uow_factory, context, 'unrecorded_variable') == {context['scale']}


@pytest.mark.asyncio(loop_scope="session")
async def test_a_recorded_factor_keeps_its_condition_method_and_scale(bus, context):
    with pytest.raises(IllegalOperationError, match="so its condition, control method and scale can't change"):
        await bus.handle(UpdateFactor(
            agent_id=context['user_id'], ontology_entry_id=context['factor'], condition_id=context['other_condition'],
            control_method_id=context['control_method'], scale_id=context['treatment_scale']
        ))


@pytest.mark.asyncio(loop_scope="session")
async def test_a_recorded_scale_keeps_its_type(bus, uow_factory, context):
    def update_scale(scale: str, scale_type: ScaleType, **changes) -> UpdateScale:
        return UpdateScale(
            agent_id=context['user_id'], ontology_entry_id=context[scale], scale_type=scale_type, **changes
        )

    with pytest.raises(IllegalOperationError, match="Records cite Measured Centimetres, so its scale type can't change"):
        await bus.handle(update_scale('scale', ScaleType.TEXT))
    await bus.handle(update_scale('scale', ScaleType.NUMERICAL, description="Length in centimetres"))
    await bus.handle(update_scale('unrecorded_scale', ScaleType.NUMERICAL))
    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        assert (await uow.ontology.get_entry(entry_id=context['scale'])).scale_type is ScaleType.NUMERICAL
        assert (await uow.ontology.get_entry(entry_id=context['unrecorded_scale'])).scale_type is ScaleType.NUMERICAL


@pytest.mark.asyncio(loop_scope="session")
async def test_a_recorded_variable_can_still_be_deprecated(bus, uow_factory, context):
    await bus.handle(DeprecateOntologyEntries(agent_id=context['user_id'], entry_ids=[context['variable']]))
    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        assert (await uow.ontology.get_cited_entry(context['variable'])).phase is LifecyclePhase.DEPRECATED
