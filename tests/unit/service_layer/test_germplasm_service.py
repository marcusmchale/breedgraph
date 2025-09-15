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


class TestGermplasmApplicationServiceRepositoryPattern:

    @pytest.fixture
    def mock_persistence(self):
        return MockGermplasmPersistenceService()

    @pytest.fixture
    def mock_access_control(self):
        return MockAccessControlService()

    @pytest.fixture
    def admin_service(self, mock_persistence, mock_access_control):
        """Service instance with full admin access."""
        return GermplasmApplicationService(
            persistence_service=mock_persistence,
            access_control_service=mock_access_control,
            user_id=1,
            access_teams={
                Access.READ: {1, 2},
                Access.WRITE: {1},
                Access.CURATE: {1}
            },
            release=ReadRelease.PRIVATE
        )

    @pytest.fixture
    def user_service(self, mock_persistence, mock_access_control):
        """Service instance with limited user access."""
        return GermplasmApplicationService(
            persistence_service=mock_persistence,
            access_control_service=mock_access_control,
            user_id=2,
            access_teams={
                Access.READ: {2},
                Access.WRITE: set(),
                Access.CURATE: set()
            },
            release=ReadRelease.REGISTERED
        )

    @pytest.fixture
    def anonymous_service(self, mock_persistence, mock_access_control):
        """Service instance for anonymous access."""
        return GermplasmApplicationService(
            persistence_service=mock_persistence,
            access_control_service=mock_access_control,
            user_id=None,
            access_teams={
                Access.READ: set(),
                Access.WRITE: set(),
                Access.CURATE: set()
            },
            release=ReadRelease.PUBLIC
        )

    @pytest.mark.asyncio
    async def test_create_entry_with_stored_context(self, admin_service):
        # Arrange
        germplasm_input = GermplasmInput(name="Admin Created Variety")

        # Act - no need to pass user_id or teams, they're stored on the service
        result = await admin_service.create_entry(germplasm_input)

        # Assert
        assert result.name == "Admin Created Variety"

        # Verify controls were set using stored context
        controller = await admin_service.access_control.get_controller("Germplasm", result.id)
        assert controller.teams == {1}  # WRITE teams from admin_service
        assert controller.release == ReadRelease.PRIVATE  # release from admin_service

    @pytest.mark.asyncio
    async def test_get_entry_respects_stored_context(self, admin_service, user_service, anonymous_service):
        # Arrange - admin creates entry
        germplasm_input = GermplasmInput(name="Private Variety")
        entry = await admin_service.create_entry(germplasm_input)

        # Act & Assert - admin can read (has team 1 which controls the entry)
        result = await admin_service.get_entry(entry.id)
        assert result.name == "Private Variety"

        # Act & Assert - user without access gets redacted version
        result = await user_service.get_entry(entry.id)
        assert result.name == "REDACTED"

        # Act & Assert - anonymous user gets nothing
        result = await anonymous_service.get_entry(entry.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_update_entry_requires_curate_access_from_stored_context(self, admin_service, user_service):
        # Arrange - admin creates entry
        germplasm_input = GermplasmInput(name="Protected Variety")
        entry = await admin_service.create_entry(germplasm_input)

        # Modify the entry
        entry.description = "Updated by admin"

        # Act & Assert - admin can update (has CURATE access)
        await admin_service.update_entry(entry)

        # Act & Assert - user without CURATE access cannot update
        entry.description = "Updated by user"
        with pytest.raises(IllegalOperationError, match="does not have permission to update"):
            await user_service.update_entry(entry)

    @pytest.mark.asyncio
    async def test_add_relationship_uses_stored_context(self, admin_service, user_service):
        # Arrange - admin creates two entries
        parent = await admin_service.create_entry(GermplasmInput(name="Parent"))
        child = await admin_service.create_entry(GermplasmInput(name="Child"))

        # Act & Assert - admin can create relationship (has necessary access)
        await admin_service.create_relationship(GermplasmRelationship(source_id=parent.id, target_id=child.id))

        # Act & Assert - user without CURATE access cannot create relationship
        with pytest.raises(IllegalOperationError, match="does not have permission"):
            await user_service.create_relationship(GermplasmRelationship(source_id=parent.id, target_id=child.id))

    @pytest.mark.asyncio
    async def test_get_all_entries_applies_stored_context(self, admin_service, user_service, anonymous_service):
        admin_service.release = ReadRelease.PUBLIC
        # Arrange - admin creates entries with different access levels
        public_entry = await admin_service.create_entry(GermplasmInput(name="Public Variety"))

        # Change admin service to create public entries
        admin_service.release = ReadRelease.REGISTERED
        public_entry2 = await admin_service.create_entry(GermplasmInput(name="Registered Variety"))

        # Reset to private for comparison
        admin_service.release = ReadRelease.PRIVATE
        private_entry = await admin_service.create_entry(GermplasmInput(name="Private Variety"))

        # Act - anonymous user (should only see public entries)
        entries = []
        async for entry in anonymous_service.get_all_entries():
            entries.append(entry)

        # Assert - only public entries visible
        names = [entry.name for entry in entries if entry.name != "REDACTED"]
        assert "Public Variety" in names
        # Private and registered entries should be filtered out for anonymous users
        assert len([e for e in entries if e.name in ["Private Variety", "Registered Variety"]]) == 0


        # Act - Registered user (should see public and registered entries)
        entries = []
        async for entry in user_service.get_all_entries():
            entries.append(entry)

        # Assert entries visible
        names = [entry.name for entry in entries if entry.name != "REDACTED"]
        assert "Public Variety" in names
        assert "Registered Variety" in names
        # Private and registered entries should be filtered out for anonymous users
        assert len([e for e in entries if e.name in ["Private Variety"]]) == 0

        # Act - admin user (should see all entries they control)
        entries = []
        async for entry in admin_service.get_all_entries():
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
            access_control_service=mock_access_control,
            user_id=None
        )

        # Act & Assert - creating entry without user_id fails
        with pytest.raises(IllegalOperationError, match="User ID required"):
            await service.create_entry(GermplasmInput(name="Test"))

    @pytest.mark.asyncio
    async def test_get_entry_sources_respects(self, admin_service, user_service):
        # Arrange - create parent and child
        parent = await admin_service.create_entry(GermplasmInput(name="Secret Parent"))
        child = await admin_service.create_entry(GermplasmInput(name="Child"))

        # Create relationship
        await admin_service.create_relationship(GermplasmRelationship(source_id=parent.id, target_id=child.id))

        # Admin can see the source (has access to both)
        async for relationship in admin_service.get_source_relationships(child.id):
            if parent.id == relationship.source_id:
                break
        else:
            raise ValueError("Parent not found in source relationships")
