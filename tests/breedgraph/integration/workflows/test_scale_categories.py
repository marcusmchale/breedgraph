"""
A scale's categories are part of it, in order, and records hold their names: a scale keeps the categories records
cite, and an earlier version reads the categories the scale had then (handlers.commands.ontologies.update_scale)
"""
import pytest
import pytest_asyncio

from breedgraph.custom_exceptions import IllegalOperationError
from breedgraph.domain.commands.ontologies import UpdateScale
from breedgraph.domain.model.accounts import OntologyRole
from breedgraph.domain.model.ontology import (
    VersionChange, ScaleType, ObservationMethodType,
    SubjectInput, TraitInput, ObservationMethodInput, ScaleInput, ScaleCategory, VariableInput
)
from breedgraph.domain.model.unit_graphs import UnitInput
from breedgraph.service_layer.queries.read_models import OntologyViewMode

from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.dataset_builder import DatasetBuilder
from tests.breedgraph.scenarios.ontology_builder import OntologyBuilder
from tests.breedgraph.scenarios.program_builder import ProgramBuilder

CATEGORIES = [ScaleCategory("Low", "Few lesions"), ScaleCategory("Mid"), ScaleCategory("High"), ScaleCategory("Spare")]


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def context(isolated_state, uow_factory) -> dict:
    """
    An ordinal scale of two variables, each with a dataset: "Low" is recorded for the first, "Mid" for the second,
    which is then removed
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
        subject = await ontology.create_subject(SubjectInput(name="Graded Tree"))
        trait = await ontology.create_trait(TraitInput(name="Graded Vigour"), subjects=[subject.id])
        method = await ontology.create_entry(
            ObservationMethodInput(name="Graded Look", observation_type=ObservationMethodType.ESTIMATION)
        )
        scale = await ontology.create_scale(
            ScaleInput(name="Graded Classes", scale_type=ScaleType.ORDINAL, categories=CATEGORIES)
        )
        variable = await ontology.create_variable(
            VariableInput(name="Graded Vigour Class"), trait_id=trait.id, observation_method_id=method.id, scale_id=scale.id
        )
        removed_variable = await ontology.create_variable(
            VariableInput(name="Graded Vigour Class Before"), trait_id=trait.id, observation_method_id=method.id,
            scale_id=scale.id
        )
        await ontology.commit_version(version_change=VersionChange.MINOR)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
        unit_graph = await uow.repositories.unit_graphs.create(UnitInput(name="Graded Tree 1", subject=subject.id))
        await uow.commit()
    unit_id = unit_graph.get_root_id()
    for concept_id, value in ((variable.id, "Low"), (removed_variable.id, "Mid")):
        await DatasetBuilder(uow_factory=uow_factory).dataset(
            user_id=user_id, team_id=team_id, concept_id=concept_id, study_id=program['study_id'],
            records=[DatasetBuilder.record_input(unit_id=unit_id, value=value)]
        )

    async with uow_factory.get_uow(user_id=user_id) as uow:
        await uow.ontology.deprecate_entries([removed_variable.id])
        await uow.ontology.commit_version(version_change=VersionChange.MAJOR)
        await uow.commit()
    return {'user_id': user_id, 'scale_id': scale.id}


def update(context, *categories: ScaleCategory, scale_type=ScaleType.ORDINAL) -> UpdateScale:
    return UpdateScale(
        agent_id=context['user_id'], ontology_entry_id=context['scale_id'], scale_type=scale_type,
        categories=[{'name': category.name, 'description': category.description} for category in categories]
    )


async def categories_of(uow_factory, context) -> list[ScaleCategory]:
    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        return (await uow.ontology.get_entry(entry_id=context['scale_id'])).categories


@pytest.mark.asyncio(loop_scope="session")
async def test_a_cited_category_stays(bus, uow_factory, context):
    low, mid, high, spare = CATEGORIES
    for categories in (
            (mid, high, spare),  # "Low" removed
            (ScaleCategory("Lowest"), mid, high, spare),  # renamed
            (low, high, spare),  # the removed variable's records cite "Mid"
    ):
        with pytest.raises(IllegalOperationError, match="Records cite the categories (Low|Mid) of Graded Classes"):
            await bus.handle(update(context, *categories))
    # a nominal or ordinal scale keeps its categories, so changing the type would drop them
    with pytest.raises(IllegalOperationError, match="Records cite the categories Low, Mid"):
        await bus.handle(update(context, scale_type=ScaleType.TEXT))
    assert await categories_of(uow_factory, context) == CATEGORIES, "nothing changed"


@pytest.mark.asyncio(loop_scope="session")
async def test_categories_are_added_reordered_and_described(bus, uow_factory, context):
    low, mid, high, spare = CATEGORIES
    changed = [high, ScaleCategory("Mid", "Some lesions"), low, ScaleCategory("Top")]  # "Spare" was cited by nothing
    await bus.handle(update(context, *changed))
    assert await categories_of(uow_factory, context) == changed


@pytest.mark.asyncio(loop_scope="session")
async def test_an_earlier_version_reads_the_categories_it_had(bus, uow_factory, views_factory, context):
    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        before = await uow.ontology.persistence.get_current_version()
    await bus.handle(update(context, *CATEGORIES))
    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        await uow.ontology.commit_version(version_change=VersionChange.MINOR)
        await uow.commit()
    await bus.handle(update(context, *reversed(CATEGORIES)))
    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        after = await uow.ontology.commit_version(version_change=VersionChange.MINOR)
        await uow.commit()

    async with views_factory.get_views(user_id=context['user_id']) as views:
        async def published(version):
            (scale,) = await views.ontology.get_entries(
                version=version, view=OntologyViewMode.PUBLISHED, entry_ids=[context['scale_id']]
            )
            return list(scale.categories)
        # the version the scale was used at, before the tests changed its categories
        assert await published(before) == CATEGORIES
        assert await published(after.version) == list(reversed(CATEGORIES))
