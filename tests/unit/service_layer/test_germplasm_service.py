import pytest
from typing import Dict, Any, Set

from src.breedgraph.service_layer.application.germplasm_service import GermplasmApplicationService
from src.breedgraph.domain.model.germplasm import (
    GermplasmInput, GermplasmSourceType, Reproduction, GermplasmRelationship
)
from src.breedgraph.domain.model.controls import ReadRelease, Access
from src.breedgraph.domain.model.organisations import Access
from src.breedgraph.custom_exceptions import IllegalOperationError

from tests.unit.fixtures.mock_germplasm_persistence import MockGermplasmPersistenceService
from tests.unit.fixtures.mock_access_control_service import MockAccessControlService


class TestGermplasmApplicationService:

    @pytest.fixture
    def mock_persistence(self):
        return MockGermplasmPersistenceService()

    @pytest.fixture
    def mock_access_control(self):
        return MockAccessControlService()

    @pytest.fixture
    def germplasm_service(self, mock_persistence, mock_access_control):
        """Service instance with different access profiles."""
        mock_access_control.set_test_access_teams(
            user_id = 1,
            access_teams={
                Access.READ: {1, 2},
                Access.WRITE: {1},
                Access.CURATE: {1}
            }
        )
        mock_access_control.set_test_access_teams(
            user_id=2,
            access_teams={
                Access.READ: {2},
                Access.WRITE: set(),
                Access.CURATE: set()
            }
        )
        mock_access_control.set_test_access_teams(
            user_id=None,
            access_teams={}
        )
        return GermplasmApplicationService(
            persistence_service=mock_persistence,
            access_control_service=mock_access_control,
            release=ReadRelease.PRIVATE
        )

    @pytest.mark.asyncio
    async def test_create_entry_with_stored_context(self, germplasm_service):
        # Arrange
        germplasm_input = GermplasmInput(name="Admin Created Variety")
        # Act - no need to pass user_id or teams, they're stored on the service
        await germplasm_service.access_control.initialize_user_context(user_id=1)
        result = await germplasm_service.create_entry(germplasm_input)

        # Assert
        assert result.name == "Admin Created Variety"

        # Verify controls were set using stored context
        controller = await germplasm_service.access_control.get_controller("Germplasm", result.id)
        assert controller.teams == {1}  # WRITE teams from user 1
        assert controller.release == ReadRelease.PRIVATE # and release level from the initial setting

    @pytest.mark.asyncio
    async def test_get_entry_respects_stored_context(self, germplasm_service):
        # Arrange - admin creates entry
        germplasm_input = GermplasmInput(name="Private Variety")
        await germplasm_service.access_control.initialize_user_context(user_id=1)
        entry = await germplasm_service.create_entry(germplasm_input)
        # Act & Assert - admin can read (has team 1 which controls the entry)
        result = await germplasm_service.get_entry(entry.id)
        assert result.name == "Private Variety"

        await germplasm_service.access_control.initialize_user_context(user_id=2)
        # Act & Assert - user without access gets redacted version
        result = await germplasm_service.get_entry(entry.id)
        assert result.name == "REDACTED"

        await germplasm_service.access_control.initialize_user_context(user_id=None)
        # Act & Assert - anonymous user gets nothing
        result = await germplasm_service.get_entry(entry.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_update_entry_requires_curate_access_from_stored_context(self, germplasm_service):
        # Arrange - admin creates entry
        germplasm_input = GermplasmInput(name="Protected Variety")
        await germplasm_service.access_control.initialize_user_context(user_id=1)
        entry = await germplasm_service.create_entry(germplasm_input)

        # Modify the entry
        entry.description = "Updated by admin"

        # Act & Assert - admin can update (has CURATE access)
        await germplasm_service.update_entry(entry)

        # Act & Assert - user without CURATE access cannot update
        entry.description = "Updated by user"
        await germplasm_service.access_control.initialize_user_context(user_id=2)
        with pytest.raises(IllegalOperationError, match="does not have permission to update"):
            await germplasm_service.update_entry(entry)

    @pytest.mark.asyncio
    async def test_add_relationship_uses_stored_context(self, germplasm_service):
        # Arrange - admin creates two entries
        await germplasm_service.access_control.initialize_user_context(user_id=1)
        parent = await germplasm_service.create_entry(GermplasmInput(name="Parent"))
        child = await germplasm_service.create_entry(GermplasmInput(name="Child"))

        # Act & Assert - admin can create relationship (has necessary access)
        await germplasm_service.create_relationships([GermplasmRelationship(source_id=parent.id, sink_id=child.id)])

        # Act & Assert - user without CURATE access cannot create relationship
        await germplasm_service.access_control.initialize_user_context(user_id=2)
        with pytest.raises(IllegalOperationError, match="does not have permission"):
            await germplasm_service.create_relationships([GermplasmRelationship(source_id=parent.id, sink_id=child.id)])

    @pytest.mark.asyncio
    async def test_get_all_entries_applies_stored_context(self, germplasm_service):
        await germplasm_service.access_control.initialize_user_context(user_id=1)
        germplasm_service.release = ReadRelease.PUBLIC
        # Arrange - admin creates entries with different access levels
        public_entry = await germplasm_service.create_entry(GermplasmInput(name="Public Variety"))

        # Change admin service to create public entries
        germplasm_service.release = ReadRelease.REGISTERED
        public_entry2 = await germplasm_service.create_entry(GermplasmInput(name="Registered Variety"))

        # Reset to private for comparison
        germplasm_service.release = ReadRelease.PRIVATE
        private_entry = await germplasm_service.create_entry(GermplasmInput(name="Private Variety"))

        # Act - anonymous user (should only see public entries)
        await germplasm_service.access_control.initialize_user_context(user_id=None)
        entries = []
        async for entry in germplasm_service.get_entries():
            entries.append(entry)

        # Assert - only public entries visible
        names = [entry.name for entry in entries if entry.name != "REDACTED"]
        assert "Public Variety" in names
        # Private and registered entries should be filtered out for anonymous users
        assert len([e for e in entries if e.name in ["Private Variety", "Registered Variety"]]) == 0


        # Act - Registered user (should see public and registered entries)
        await germplasm_service.access_control.initialize_user_context(user_id=2)
        entries = []
        async for entry in germplasm_service.get_entries():
            entries.append(entry)

        # Assert entries visible
        names = [entry.name for entry in entries if entry.name != "REDACTED"]
        assert "Public Variety" in names
        assert "Registered Variety" in names
        # Private and registered entries should be filtered out for anonymous users
        assert len([e for e in entries if e.name in ["Private Variety"]]) == 0

        # Act - admin user (should see all entries they control)
        await germplasm_service.access_control.initialize_user_context(user_id=1)
        entries = []
        async for entry in germplasm_service.get_entries():
            entries.append(entry)

        # Assert - admin sees all entries
        names = [entry.name for entry in entries]
        assert "Public Variety" in names
        assert "Registered Variety" in names
        assert "Private Variety" in names

    @pytest.mark.asyncio
    async def test_service_without_user_id_fails_operations(self, mock_persistence, mock_access_control):
        # Arrange - service without user_id
        service = GermplasmApplicationService(
            persistence_service=mock_persistence,
            access_control_service=mock_access_control
        )

        # Act & Assert - creating entry without user_id fails
        with pytest.raises(IllegalOperationError, match="User ID required"):
            await service.create_entry(GermplasmInput(name="Test"))

    @pytest.mark.asyncio
    async def test_get_entry_sources_respects(self, germplasm_service):
        # Arrange - create parent and child
        await germplasm_service.access_control.initialize_user_context(user_id=1)
        parent = await germplasm_service.create_entry(GermplasmInput(name="Secret Parent"))
        child = await germplasm_service.create_entry(GermplasmInput(name="Child"))

        # Create relationship
        await germplasm_service.create_relationships([GermplasmRelationship(source_id=parent.id, sink_id=child.id)])

        # Admin can see the source (has access to both)
        async for relationship in germplasm_service.get_source_relationships(child.id):
            if parent.id == relationship.source_id:
                break
        else:
            raise ValueError("Parent not found in source relationships")
