import pytest
import pytest_asyncio
from typing import Dict, Any

from src.breedgraph.service_layer.application.ontology_service import OntologyApplicationService

from src.breedgraph.domain.model.ontology import (
    SubjectInput, TraitInput, ScaleInput, VariableInput,
    VariableComponentRelationship, Version, VersionChange, ObservationMethodInput
)
from src.breedgraph.domain.model.accounts import OntologyRole
from src.breedgraph.custom_exceptions import IllegalOperationError

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
class TestOntologyServiceIntegration:
    """Integration tests for the ontology application service using real persistence."""

    @pytest_asyncio.fixture(scope="session")
    async def test_version(self) -> Version:
        """Test version to use for operations."""
        return Version(major=1, minor=0, patch=0)

    @pytest_asyncio.fixture(scope="session")
    async def basic_entries(self, ontology_service, test_version) -> Dict[str, Any]:
        """Create basic ontology entries for testing relationships."""
        entries = {}

        # Create a subject
        subject = await ontology_service.create_entry(
            SubjectInput(name="Test Subject", description="A test subject"),
        )
        entries["subject"] = subject

        # Create a trait
        trait = await ontology_service.create_trait(
            TraitInput(name="Test Trait", description="A test trait"), subjects=[subject.id]
        )
        entries["trait"] = trait

        observation_method = await ontology_service.create_entry(
            ObservationMethodInput(name="Test Method", description="A test method"),
        )
        entries["observation_method"] = observation_method

        # Create a scale
        scale = await ontology_service.create_entry(
            ScaleInput(name="Test Scale", description="A test scale"),
        )
        entries["scale"] = scale

        return entries

    async def test_create_and_retrieve_subject_entry(self, ontology_service, test_version):
        """Test creating and retrieving a subject entry through the service."""
        # Arrange
        subject_input = SubjectInput(
            name="Coffee Plant",
            description="Coffee plant subject for breeding research"
        )

        # Act - Create entry
        created_subject = await ontology_service.create_entry(
            subject_input
        )

        # Assert - Entry was created with ID
        assert created_subject.id is not None
        assert created_subject.name == "Coffee Plant"
        assert created_subject.description == "Coffee plant subject for breeding research"

        # Act - Retrieve entry
        retrieved_subject = await ontology_service.get_entry(
            created_subject.id
        )

        # Assert - Retrieved entry matches created entry
        assert retrieved_subject.id == created_subject.id
        assert retrieved_subject.name == created_subject.name
        assert retrieved_subject.description == created_subject.description

    async def test_create_variable_with_component_relationships(
            self,
            ontology_service,
            basic_entries,
            test_version
    ):
        """Test creating a variable and establishing component relationships."""
        # Arrange
        variable_input = VariableInput(
            name="Plant Height",
            description="Height measurement of coffee plants"
        )
        # Act - Create variable
        variable = await ontology_service.create_variable(
            variable_input,
            trait_id = basic_entries["trait"].id,
            observation_method_id=basic_entries["observation_method"].id,
            scale_id = basic_entries["scale"].id,
        )
        # Assert - Check relationships exist through output format
        variable = await ontology_service.get_entry(entry_id=variable.id, as_output=True, label="Variable")
        assert variable.trait == basic_entries["trait"].id
        assert variable.scale == basic_entries["scale"].id

    async def test_commit_version_with_role_validation(self, ontology_service):
        """Test that version commits respect user role requirements."""
        # Assert - contributor cannot commit
        with pytest.raises(IllegalOperationError, match="Only admins and editors can commit"):
            await ontology_service.commit_version(
                version_change=VersionChange.PATCH,
                comment="Unauthorized commit attempt"
            )

        # Create service with contributor role
        admin_service = OntologyApplicationService(
            persistence_service=ontology_service.persistence,
            user_id=2,
            role=OntologyRole.ADMIN
        )
        # Assert - contributor can commit
        await admin_service.commit_version(
            version_change=VersionChange.PATCH,
            comment="Authorized commit attempt"
        )

    async def test_validation_across_persistence_layer(
            self,
            ontology_service,
            test_version
    ):
        """Test that service validation works with real persistence queries."""
        # Arrange - Create an entry
        await ontology_service.create_entry(
            SubjectInput(name="Unique Subject", description="Test")
        )

        # Act & Assert - Try to create duplicate name
        with pytest.raises(ValueError, match="using the name"):
            await ontology_service.create_entry(
                SubjectInput(name="Unique Subject", description="Duplicate")
            )

    async def test_get_version_history_integration(self, ontology_service):
        """Test retrieving version history through the service."""
        # Act
        history = [commit async for commit in ontology_service.get_commit_history(limit=5)]

        # Assert - Should return list of commits
        assert isinstance(history, list)
        # History might be empty in a fresh test database, but structure should be correct
        for commit in history:
            assert hasattr(commit, 'version')
            assert hasattr(commit, 'user')
            assert hasattr(commit, 'time')