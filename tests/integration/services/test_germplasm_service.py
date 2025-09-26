import pytest

from src.breedgraph.domain.model.germplasm import (
    GermplasmInput, GermplasmStored, GermplasmSourceType, GermplasmRelationship
)

from src.breedgraph.custom_exceptions import UnauthorisedOperationError


@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
class TestGermplasmServiceIntegration:
    """Integration tests for the germplasm application service using real persistence and access control."""

    async def test_create_and_retrieve_germplasm_entry(
            self,
            germplasm_service,
            neo4j_access_control_service,
            first_unstored_account,
            lorem_text_generator
    ):
        """Test creating and retrieving a germplasm entry through the service."""
        # Arrange
        germplasm_input = GermplasmInput(
            name=lorem_text_generator.new_text(10),
            description="Integration test variety",
            synonyms=[lorem_text_generator.new_text(5)]
        )
        await neo4j_access_control_service.initialize_user_context(user_id=first_unstored_account.user.id)
        # Act - Create entry
        created_entry = await germplasm_service.create_entry(germplasm_input)

        # Assert - Entry was created with ID
        assert created_entry.id is not None
        assert created_entry.name == germplasm_input.name
        assert created_entry.description == germplasm_input.description
        assert created_entry.synonyms == germplasm_input.synonyms

        # Act - Retrieve entry
        retrieved_entry = await germplasm_service.get_entry(created_entry.id)

        # Assert - Retrieved entry matches created entry
        assert retrieved_entry.id == created_entry.id
        assert retrieved_entry.name == created_entry.name
        assert retrieved_entry.description == created_entry.description

    async def test_create_germplasm_with_source_relationships(
            self,
            germplasm_service,
            example_crop,
            lorem_text_generator
    ):
        """Test creating germplasm with source relationships."""
        # Arrange
        variety_input = GermplasmInput(
            name=lorem_text_generator.new_text(10),
            description="Variety derived from crop"
        )

        sources = {
            example_crop.id: {
                'type': GermplasmSourceType.SEED,
                'notes': 'Seed selection from crop'
            }
        }

        # Act - Create entry with sources
        created_variety = await germplasm_service.create_entry(variety_input)
        # Assert - Entry was created
        assert created_variety.id is not None
        assert created_variety.name == variety_input.name

        relationship = GermplasmRelationship(
            source_id=example_crop.id,
            target_id=created_variety.id,
            source_type=GermplasmSourceType.SEED,
            description="Seed selection from crop"
        )
        # create source relationships
        await germplasm_service.create_relationship(relationship)
        # Act - Get source relationships
        async for rel in germplasm_service.get_source_relationships(created_variety.id):
            if rel.source_id == example_crop.id:
                assert rel.source_type == GermplasmSourceType.SEED
                assert rel.description == 'Seed selection from crop'
                break
        else:
            raise ValueError("No source relationships found")

    async def test_access_control_integration(
            self,
            germplasm_service,
            neo4j_access_control_service,
            second_unstored_account,
            lorem_text_generator
    ):
        """Test that access control works with real persistence layer."""
        # Arrange - Admin service creates private entry
        private_entry_input = GermplasmInput(
            name=lorem_text_generator.new_text(10),
            description="Private germplasm entry"
        )

        # Act - Create with admin service (has WRITE access)
        private_entry = await germplasm_service.create_entry(private_entry_input)

        # Assert - Admin service can retrieve the entry
        retrieved_by_admin = await germplasm_service.get_entry(private_entry.id)
        assert retrieved_by_admin is not None
        assert retrieved_by_admin.name == private_entry_input.name

        # Assert - service for registered user without read access to that entry gets a redacted form
        await neo4j_access_control_service.initialize_user_context(user_id = second_unstored_account.user.id)
        retrieved_by_no_read = await germplasm_service.get_entry(private_entry.id)
        assert retrieved_by_no_read.name == GermplasmStored.redacted_str

    async def test_update_entry_with_access_control(
            self,
            germplasm_service,
            neo4j_access_control_service,
            first_unstored_account,
            second_unstored_account,
            lorem_text_generator
    ):
        """Test updating entries respects access control."""
        # Arrange - Create entry with admin service

        entry_input = GermplasmInput(
            name=lorem_text_generator.new_text(10),
            description="Original description"
        )
        await neo4j_access_control_service.initialize_user_context(user_id=first_unstored_account.user.id)
        created_entry = await germplasm_service.create_entry(entry_input)
        # Modify the entry
        created_entry.description = "Updated by admin"
        # Act & Assert - Admin service can update
        await germplasm_service.update_entry(created_entry)

        # Verify update worked
        updated_entry = await germplasm_service.get_entry(created_entry.id)
        assert updated_entry.description == "Updated by admin"

        # Act & Assert - User with read only access cannot update
        created_entry.description = "Updated by readonly"
        await neo4j_access_control_service.initialize_user_context(user_id = second_unstored_account.user.id)
        with pytest.raises(UnauthorisedOperationError, match="does not have permission to update germplasm entry"):
            await germplasm_service.update_entry(created_entry)

    async def test_add_source_relationship_with_validation(
            self,
            germplasm_service,
            neo4j_access_control_service,
            first_unstored_account,
            example_crop,
            lorem_text_generator
    ):
        """Test adding source relationships with validation through service."""
        await neo4j_access_control_service.initialize_user_context(user_id=first_unstored_account.user.id)
        # Arrange - Create two entries
        parent_input = GermplasmInput(name=lorem_text_generator.new_text(8))
        child_input = GermplasmInput(name=lorem_text_generator.new_text(8))

        parent = await germplasm_service.create_entry(parent_input)
        child = await germplasm_service.create_entry(child_input)
        relationship = GermplasmRelationship(
            source_id=parent.id,
            target_id=child.id,
            source_type=GermplasmSourceType.SEED,
            description="TEST"
        )
        # Act - Add source relationship
        await germplasm_service.create_relationship(relationship)

        # Assert - Relationship exists
        async for rel in germplasm_service.get_source_relationships(child.id):
            if rel.source_id == parent.id:
                assert rel.source_type == GermplasmSourceType.SEED
                assert rel.description == 'TEST'
                break

    async def test_get_all_entries_with_filtering_and_access_control(
            self,
            germplasm_service,
            neo4j_access_control_service,
            first_unstored_account,
            second_unstored_account,
            lorem_text_generator
    ):
        """Test getting all entries with filtering and access control."""
        # Arrange - Create entries with specific names
        await neo4j_access_control_service.initialize_user_context(user_id=first_unstored_account.user.id)
        test_name_base = lorem_text_generator.new_text(6)
        entry1_input = GermplasmInput(name=f"{test_name_base}_1")
        entry2_input = GermplasmInput(name=f"{test_name_base}_2")

        entry1 = await germplasm_service.create_entry(entry1_input)
        entry2 = await germplasm_service.create_entry(entry2_input)

        # Act - Get entries by name filter (admin service)
        admin_results = []
        async for entry in germplasm_service.get_all_entries(
                names=[entry1.name, entry2.name]
        ):
            admin_results.append(entry)

        # Assert - Admin sees both entries
        assert len(admin_results) == 2
        entry_names = {entry.name for entry in admin_results}
        assert entry1.name in entry_names
        assert entry2.name in entry_names

        # Get entries with read-only service
        await neo4j_access_control_service.initialize_user_context(user_id=second_unstored_account.user.id)
        no_read_results = []
        async for entry in germplasm_service.get_all_entries(
                names=[entry1.name, entry2.name]
        ):
            no_read_results.append(entry)
        # Assert - Read-only service gets redacted results
        if not no_read_results:
            raise ValueError("No entries found")
        for entry in no_read_results:
            assert entry.name == "REDACTED"

        # Get entries with unregistered service
        await neo4j_access_control_service.initialize_user_context(user_id=None)
        unregistered_results = []
        async for entry in germplasm_service.get_all_entries(
                names=[entry1.name, entry2.name]
        ):
            unregistered_results.append(entry)
        # Assert - Read-only service gets redacted results
        for _ in unregistered_results:
            raise ValueError("Unregistered service should not be able to get private entries")

    async def test_circular_dependency_prevention(
            self,
            germplasm_service,
            neo4j_access_control_service,
            first_unstored_account,
            lorem_text_generator
    ):
        """Test that circular dependencies are prevented in source relationships."""
        await neo4j_access_control_service.initialize_user_context(user_id=first_unstored_account.user.id)
        # Arrange - Create a chain of entries: A -> B -> C
        entry_a_input = GermplasmInput(name=f"{lorem_text_generator.new_text(5)}_A")
        entry_b_input = GermplasmInput(name=f"{lorem_text_generator.new_text(5)}_B")
        entry_c_input = GermplasmInput(name=f"{lorem_text_generator.new_text(5)}_C")

        entry_a = await germplasm_service.create_entry(entry_a_input)
        entry_b = await germplasm_service.create_entry(entry_b_input)
        entry_c = await germplasm_service.create_entry(entry_c_input)

        # Create chain: A -> B -> C
        await germplasm_service.create_relationship(GermplasmRelationship(source_id=entry_a.id, target_id=entry_b.id))
        await germplasm_service.create_relationship(GermplasmRelationship(source_id=entry_b.id, target_id=entry_c.id))
        # Act & Assert - Try to create circular dependency C -> A
        with pytest.raises(ValueError, match="circular dependency"):
            await germplasm_service.create_relationship(GermplasmRelationship(source_id=entry_c.id, target_id=entry_a.id))


    async def test_get_descendants_and_ancestors(
            self,
            germplasm_service,
            example_crop,
            lorem_text_generator
    ):
        """Test retrieving descendants and ancestors through the service."""
        # Arrange - Create hierarchy: crop -> variety -> selection
        variety_input = GermplasmInput(name=f"{lorem_text_generator.new_text(6)}_variety")
        selection_input = GermplasmInput(name=f"{lorem_text_generator.new_text(6)}_selection")
        variety = await germplasm_service.create_entry(variety_input)
        selection = await germplasm_service.create_entry(selection_input)
        await germplasm_service.create_relationship(GermplasmRelationship(source_id=example_crop.id, target_id=variety.id))
        await germplasm_service.create_relationship(GermplasmRelationship(source_id=variety.id, target_id=selection.id))

        # Act - Get descendants of crop
        crop_descendants = await germplasm_service.get_descendant_ids(
            example_crop.id
        )
        # Assert - Descendants include variety and selection
        assert variety.id in crop_descendants
        assert selection.id in crop_descendants

        # Act - Get ancestors of selection
        selection_ancestors = await germplasm_service.get_ancestor_ids(
            selection.id
        )

        # Assert - Ancestors include variety and crop
        assert variety.id in selection_ancestors
        assert example_crop.id in selection_ancestors