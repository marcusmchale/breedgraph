import pytest

from breedgraph.custom_exceptions import UnauthorisedOperationError, IdentityExistsError
from breedgraph.domain.model.accounts import OntologyRole
from breedgraph.domain.model.ontology import (
    OntologyEntryLabel,
    SubjectInput,
    VersionChange,
    VariableComponentRelationship,
)
from breedgraph.domain.model.ontology.enums import OntologyRelationshipLabel

from tests.scenarios.ontology_builder import OntologyBuilder


@pytest.mark.asyncio(loop_scope="session")
async def test_create_and_retrieve_subject_entry(
        uow_factory,
        ontology_build_context
):
    user_id = ontology_build_context["user_id"]
    subject_input = OntologyBuilder.subject_input(name="Coffee Plant")

    async with uow_factory.get_uow(user_id=user_id) as uow:
        created_subject = await uow.ontology.create_entry(subject_input)
        await uow.commit()

    assert created_subject.id is not None
    assert created_subject.name == subject_input.name
    assert created_subject.description == subject_input.description

    async with uow_factory.get_uow(user_id=user_id) as uow:
        retrieved_subject = await uow.ontology.get_entry(created_subject.id)

    assert retrieved_subject
    assert retrieved_subject.id == created_subject.id
    assert retrieved_subject.name == created_subject.name
    assert retrieved_subject.description == created_subject.description


@pytest.mark.asyncio(loop_scope="session")
async def test_create_variable_with_component_relationships(
        uow_factory,
        ontology_build_context
):
    user_id = ontology_build_context["user_id"]
    trait_id = ontology_build_context["ontology_trait"]
    observation_method_id = ontology_build_context["ontology_observation_method"]
    scale_id = ontology_build_context["ontology_scale"]
    variable_input = OntologyBuilder.variable_input(name="Plant Height")

    async with uow_factory.get_uow(user_id=user_id) as uow:
        variable = await uow.ontology.create_variable(
            variable_input,
            trait_id=trait_id,
            observation_method_id=observation_method_id,
            scale_id=scale_id,
        )
        await uow.commit()

    trait_found = False
    method_found = False
    scale_found = False

    async with uow_factory.get_uow(user_id=user_id) as uow:
        async for rel in uow.ontology.get_relationships(entry_ids=[variable.id]):
            if all([
                isinstance(rel, VariableComponentRelationship.TraitRelationship),
                rel.target_id == trait_id,
                rel.label == OntologyRelationshipLabel.DESCRIBES_TRAIT
            ]):
                trait_found = True

            if all([
                isinstance(rel, VariableComponentRelationship.ObservationMethodRelationship),
                rel.target_id == observation_method_id,
                rel.label == OntologyRelationshipLabel.USES_OBSERVATION_METHOD
            ]):
                method_found = True

            if all([
                isinstance(rel, VariableComponentRelationship.ScaleRelationship),
                rel.target_id == scale_id,
                rel.label == OntologyRelationshipLabel.USES_SCALE
            ]):
                scale_found = True

    if not all([trait_found, method_found, scale_found]):
        raise ValueError(
            f"Some relationships not found, "
            f"trait: {trait_found}, method: {method_found}, scale: {scale_found}"
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_commit_version_with_role_validation(
        uow_factory,
        ontology_build_context
):
    user_id_1 = ontology_build_context['user_id_1']
    user_id_2 = ontology_build_context["user_id_2"]

    async with uow_factory.get_uow(user_id=user_id_2) as uow:
        with pytest.raises(UnauthorisedOperationError, match="Only admins and editors can commit"):
            await uow.ontology.commit_version(
                version_change=VersionChange.PATCH,
                comment="Unauthorized commit attempt"
            )

    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        await uow.ontology.commit_version(
            version_change=VersionChange.PATCH,
            comment="Authorized commit attempt"
        )
        await uow.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_validation_across_persistence_layer(
        uow_factory,
        ontology_build_context
):
    user_id = ontology_build_context["user_id"]
    subject_name = "Unique Subject"

    async with uow_factory.get_uow(user_id=user_id) as uow:
        await uow.ontology.create_entry(
            SubjectInput(name=subject_name, description="Test")
        )
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        with pytest.raises(IdentityExistsError, match="using the name"):
            await uow.ontology.create_entry(
                SubjectInput(name=subject_name, description="Duplicate")
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_get_version_history_integration(
        uow_factory,
        ontology_build_context
):
    user_id = ontology_build_context["user_id"]

    async with uow_factory.get_uow(user_id=user_id) as uow:
        history = [
            commit async for commit in uow.ontology.get_commit_history(limit=5)
        ]

    assert isinstance(history, list)

    for commit in history:
        assert hasattr(commit, "version")
        assert hasattr(commit, "user")
        assert hasattr(commit, "time")


@pytest.mark.asyncio(loop_scope="session")
async def test_create_complete_variable_with_relationships(
        uow_factory,
        ontology_build_context
):
    user_id = ontology_build_context["user_id"]
    variable_ids = await OntologyBuilder(uow_factory).variable(user_id=user_id)

    variable_id = variable_ids["ontology_variable"]
    trait_id = variable_ids["ontology_trait"]
    scale_id = variable_ids["ontology_scale"]
    observation_method_id = variable_ids["ontology_observation_method"]

    async with uow_factory.get_uow(user_id=user_id) as uow:
        async for relationship in uow.ontology.persistence.get_relationships(
                source_ids=[variable_id],
                labels=[OntologyRelationshipLabel.DESCRIBES_TRAIT]
        ):
            if relationship.target_id == trait_id:
                break
        else:
            raise ValueError("Trait relationship not created for variable")

        async for relationship in uow.ontology.persistence.get_relationships(
                source_ids=[variable_id],
                labels=[OntologyRelationshipLabel.USES_SCALE]
        ):
            if relationship.target_id == scale_id:
                break
        else:
            raise ValueError("Scale relationship not created for variable")

        async for relationship in uow.ontology.persistence.get_relationships(
                source_ids=[variable_id],
                labels=[OntologyRelationshipLabel.USES_OBSERVATION_METHOD]
        ):
            if relationship.target_id == observation_method_id:
                break
        else:
            raise ValueError("Observation method relationship not created for variable")


@pytest.mark.asyncio(loop_scope="session")
async def test_get_entry_by_name_and_label(
        uow_factory,
        ontology_build_context
):
    user_id = ontology_build_context["user_id"]
    subject_id = ontology_build_context["ontology_subject"]

    async with uow_factory.get_uow(user_id=user_id) as uow:
        subject = await uow.ontology.get_entry(subject_id)
        assert subject

        retrieved_subject = await uow.ontology.get_entry(
            name=subject.name,
            label=OntologyEntryLabel.SUBJECT
        )

    assert retrieved_subject
    assert retrieved_subject.id == subject.id