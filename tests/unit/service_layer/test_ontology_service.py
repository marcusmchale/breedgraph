import pytest
from typing import List, Dict, Any

from src.breedgraph.service_layer.application.ontology_service import OntologyApplicationService
from src.breedgraph.domain.model.ontology import (
    SubjectInput, TraitInput, VariableInput, ScaleInput, TermInput, ObservationMethodInput, ScaleCategoryInput, OntologyEntryLabel
)
from src.breedgraph.domain.model.accounts import OntologyRole
from src.breedgraph.domain.model.ontology.enums import ScaleType, OntologyRelationshipLabel
from src.breedgraph.domain.model.ontology.relationships import (
    OntologyRelationshipBase,
    ParentRelationship,
    VariableComponentRelationship
)
from src.breedgraph.domain.model.ontology.version import Version

from tests.unit.fixtures.mock_ontology_persistence import MockOntologyPersistenceService


class TestOntologyApplicationServiceEntryCreation:

    @pytest.fixture
    def mock_persistence(self):
        return MockOntologyPersistenceService()

    @pytest.fixture
    def service(self, mock_persistence):
        return OntologyApplicationService(mock_persistence, user_id=1, role=OntologyRole.ADMIN)

    @pytest.fixture
    def version(self):
        return Version(major=1, minor=0, patch=0)

    @pytest.mark.asyncio
    async def test_create_subject_entry(self, service, mock_persistence, version):
        # Arrange
        subject_input = SubjectInput(name="Tree", description="A woody plant")

        # Act
        result = await service.create_entry(subject_input)

        # Assert
        assert result.id == 1
        assert result.name == "Tree"
        assert result.description == "A woody plant"
        assert result.label == "Subject"

        # Verify it was stored
        stored_entry = await mock_persistence.get_entry(1)
        assert stored_entry == result

    @pytest.mark.asyncio
    async def test_create_entry_validates_uniqueness(self, service, mock_persistence, version):
        # Arrange - create first entry
        subject_input1 = SubjectInput(name="Tree")
        await service.create_entry(subject_input1)

        # Try to create duplicate
        subject_input2 = SubjectInput(name="Tree")

        # Act & Assert
        with pytest.raises(ValueError, match="Another.*is using the name"):
            await service.create_entry(subject_input2)

    @pytest.mark.asyncio
    async def test_create_entries_different_labels_allow_same_name(self, service, version):
        # Arrange
        subject_input = SubjectInput(name="Tree")
        trait_input = TraitInput(name="Tree")  # Same name, different label

        # Act
        subject_result = await service.create_entry(subject_input)
        trait_result = await service.create_trait(trait_input, subjects=[subject_result.id])
        # Assert - both should succeed
        assert subject_result.name == "Tree"
        assert trait_result.name == "Tree"
        assert subject_result.label == "Subject"
        assert trait_result.label == "Trait"

    @pytest.mark.asyncio
    async def test_create_scale_with_abbreviation_validates_uniqueness(self, service, version):
        # Arrange
        scale1 = ScaleInput(name="Centimeters", abbreviation="cm", scale_type=ScaleType.NUMERICAL)
        scale2 = ScaleInput(name="Centimetres", abbreviation="cm", scale_type=ScaleType.NUMERICAL)
        await service.create_entry(scale1)

        # Act & Assert
        with pytest.raises(ValueError, match="Another.*is using the abbreviation"):
            await service.create_entry(scale2)

class TestOntologyApplicationServiceRelationships:

    @pytest.fixture
    def mock_persistence(self):
        return MockOntologyPersistenceService()

    @pytest.fixture
    def service(self, mock_persistence):
        return OntologyApplicationService(mock_persistence, user_id=1, role=OntologyRole.ADMIN)

    @pytest.fixture
    def version(self):
        return Version(major=1, minor=0, patch=0)

    @pytest.mark.asyncio
    async def test_create_variable(self, service, mock_persistence, version):
        # Arrange - create Variable and Trait entries
        trait = await service.create_trait(TraitInput(name="Height"))
        observation_method = await service.create_entry(ObservationMethodInput(name="Tape Measure"))
        scale = await service.create_entry(ScaleInput(name="cm"))

        variable_input = VariableInput(name="Tree Height")
        variable = await service.create_variable(
            variable_input,
            trait_id=trait.id,
            observation_method_id=observation_method.id,
            scale_id=scale.id
        )

        # Assert - relationships should exist
        assert await mock_persistence.relationship_exists(
            variable.id, trait.id, OntologyRelationshipLabel.DESCRIBES_TRAIT
        )
        assert await mock_persistence.relationship_exists(
            variable.id, observation_method.id, OntologyRelationshipLabel.USES_OBSERVATION_METHOD
        )
        assert await mock_persistence.relationship_exists(
            variable.id, scale.id, OntologyRelationshipLabel.USES_SCALE
        )

    @pytest.mark.asyncio
    async def test_prevent_invalid_component_relationship(self, service, version):
        # Arrange - create Variable and Subject (invalid for DESCRIBES_TRAIT)
        observation_method = await service.create_entry(ObservationMethodInput(name="Tape Measure"))
        scale = await service.create_entry(ScaleInput(name="cm"))
        subject = await service.create_entry(SubjectInput(name="Tree"))

        variable_input = VariableInput(name="Tree Height 2")
        with pytest.raises(ValueError):
            await service.create_variable(
                variable_input,
                trait_id=subject.id,
                observation_method_id=observation_method.id,
                scale_id=scale.id
            )

    @pytest.mark.asyncio
    async def test_prevent_duplicate_relationship(self, service, version):
        # Arrange
        trait = await service.create_trait(TraitInput(name="Height"))
        observation_method = await service.create_entry(ObservationMethodInput(name="Tape Measure"))
        scale = await service.create_entry(ScaleInput(name="cm"))

        variable_input = VariableInput(name="Tree Height")
        variable = await service.create_variable(
            variable_input,
            trait_id=trait.id,
            observation_method_id=observation_method.id,
            scale_id=scale.id
        )
        relationship = VariableComponentRelationship.TraitRelationship.build(
            variable_id=variable.id,
            trait_id=trait.id
        )
        with pytest.raises(ValueError, match="Relationship already exists"):
            await service.create_relationship(relationship)

    @pytest.mark.asyncio
    async def test_prevent_circular_dependency(self, service, version):
        # Arrange - create two traits with parent relationship
        parent_trait = TraitInput(name="Parent Trait")
        child_trait = TraitInput(name="Child Trait")

        parent = await service.create_trait(parent_trait)
        child = await service.create_trait(child_trait)

        # Create parent -> child relationship
        parent_rel = ParentRelationship.build(
            parent_id=parent.id,
            child_id=child.id,
            source_label=OntologyEntryLabel.TRAIT,
            target_label=OntologyEntryLabel.TRAIT
        )
        await service.create_relationship(parent_rel)

        # Try to create child -> parent relationship (would create cycle)
        cycle_rel = ParentRelationship.build(
            parent_id=child.id,
            child_id=parent.id,
            source_label=OntologyEntryLabel.TRAIT,
            target_label=OntologyEntryLabel.TRAIT
        )
        # Act & Assert
        with pytest.raises(ValueError):
            await service.create_relationship(cycle_rel)



class TestOntologyApplicationServiceValidation:

    @pytest.fixture
    def mock_persistence(self):
        return MockOntologyPersistenceService()

    @pytest.fixture
    def service(self, mock_persistence):
        return OntologyApplicationService(mock_persistence, user_id = 1, role=OntologyRole.ADMIN)

    @pytest.fixture
    def version(self):
        return Version(major=1, minor=0, patch=0)

    @pytest.mark.asyncio
    async def test_entry_must_exist_for_relationship(self, service, version):
        # Try to create relationship with non-existent entries
        relationship = ParentRelationship.build(
            parent_id=999, # Doesn't exist
            child_id=1000, # Doesn't exist
            source_label= OntologyEntryLabel.TERM,
            target_label= OntologyEntryLabel.TERM
        )
        with pytest.raises(ValueError, match="do not exist"):
            await service.create_relationship(relationship)


class TestOntologyApplicationServiceScaleCategories:

    @pytest.fixture
    def mock_persistence(self):
        return MockOntologyPersistenceService()

    @pytest.fixture
    def service(self, mock_persistence):
        return OntologyApplicationService(mock_persistence, user_id=1, role=OntologyRole.ADMIN)

    @pytest.fixture
    def version(self):
        return Version(major=1, minor=0, patch=0)

    @pytest.mark.asyncio
    async def test_creates_with_rank_ordinal_scale(self, service):
        scale_input = ScaleInput(name="test scale", scale_type=ScaleType.ORDINAL)
        scale = await service.create_scale(scale_input)
        category_1 = await service.create_entry(ScaleCategoryInput(name='A'))
        category_2 = await service.create_entry(ScaleCategoryInput(name='B'))
        category_3 = await service.create_entry(ScaleCategoryInput(name='C'))
        await service.add_scale_categories(scale_id = scale.id, categories=[category_1.id,category_2.id,category_3.id], ranks=[2,1,0])
        categories = await service.get_scale_category_ids(scale_id = scale.id)
        assert categories == [category_3.id,category_2.id,category_1.id]

# Fixture for common test setup
@pytest.fixture
def basic_ontology_setup():
    """Create a basic ontology setup for integration-style tests."""

    async def _setup(service):
        # Create basic entries
        subject = await service.create_entry(SubjectInput(name="Tree", description="A woody plant"))
        trait = await service.create_entry(TraitInput(name="Height", description="Vertical measurement"))
        observation_method = await service.create_entry(ObservationMethodInput(name="Tape measurement"))
        scale = await service.create_entry(ScaleInput(name="Centimeters", abbreviation="cm", scale_type=ScaleType.NUMERICAL))
        return {"subject": subject, "trait": trait, "scale": scale, "observation_method": observation_method}

    return _setup


class TestOntologyApplicationServiceIntegration:
    """Integration-style tests using the mock persistence."""

    @pytest.fixture
    def mock_persistence(self):
        return MockOntologyPersistenceService()

    @pytest.fixture
    def service(self, mock_persistence):
        return OntologyApplicationService(mock_persistence, user_id=1, role=OntologyRole.ADMIN)

    @pytest.fixture
    def version(self):
        return Version(major=1, minor=0, patch=0)

    @pytest.mark.asyncio
    async def test_create_complete_variable_with_relationships(
            self, service, basic_ontology_setup, version
    ):
        # Arrange
        entries = await basic_ontology_setup(service)
        # Create a variable
        variable = await service.create_variable(
            VariableInput(name="Tree Height (cm)"),
            trait_id = entries['trait'].id,
            observation_method_id= entries['observation_method'].id,
            scale_id = entries['scale'].id
        )
        async for relationship in service.persistence.get_relationships(source_ids=[variable.id], labels = [OntologyRelationshipLabel.DESCRIBES_TRAIT]):
            if relationship.target_id == entries['trait'].id:
                break
        else:
            raise ValueError("Scale relationship not created for variable")
        async for relationship in service.persistence.get_relationships(source_ids=[variable.id], labels = [OntologyRelationshipLabel.USES_SCALE]):
            if relationship.target_id == entries['scale'].id:
                break
        else:
            raise ValueError("Observation method relationship not created for variable")
        async for relationship in service.persistence.get_relationships(source_ids=[variable.id], labels = [OntologyRelationshipLabel.USES_OBSERVATION_METHOD]):
            if relationship.target_id == entries['observation_method'].id:
                break
        else:
            raise ValueError("Trait relationship not created for variable")
