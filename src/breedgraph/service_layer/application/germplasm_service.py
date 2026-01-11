from typing import List, Dict, Any, AsyncGenerator, Optional, Set

from src.breedgraph.domain.model.germplasm import (
    GermplasmInput, GermplasmStored, GermplasmSourceType, GermplasmRelationship
)
from src.breedgraph.domain.model.controls import ReadRelease, Access, ControlledModelLabel
from src.breedgraph.domain.events.base import Event
from src.breedgraph.service_layer.persistence.germplasm import GermplasmPersistenceService
from src.breedgraph.service_layer.application.access_control import AbstractAccessControlService
from src.breedgraph.custom_exceptions import IllegalOperationError, UnauthorisedOperationError

import logging

logger = logging.getLogger(__name__)


#todo control method should be enforced as subtype of a germplasm management method type in the ontology

class GermplasmApplicationService:
    """
    Application service for all germplasm operations.
    Handles validation, state management, persistence, access control, and event publishing.

    Unlike ontology, we don't version the germplasm as the underlying concepts are different.
      - With ontology, we are choosing to define things a certain way, and this can change ad-hoc.
      - With germplasm we are attempting to describe properties of and relationships among real-world entities.
        These properties/relationships do not change, only our knowledge of them can be refined/corrected.

    The Germplasm entries form a graph, with connected entries typically rooted at a Crop reference,
     e.g. coffee or cocoa.
    This service manages Sourcing and Maintenance details among/for entries.
    The source/maintenance details contain references to Ontology entries for Methods,
    and to Region (Location) entries for Locations.

    e.g. Coffee <- Coffea arabica <- Marsellesa <- Centroamericano -> MSH12 ...

    From the relationships we can infer some properties,
    e.g.
      - is an Accession where location and time are provided.
      - a hybrid has distinct maternal and paternal donors
      - a controlled self-fertilisation has the same maternal and paternal donor
      - a clonal tissue has a singular source Tissue relationship.

    But for now, we can leave interpretation and the attribution of these labels up to the end users.
    As we need to more robustly define distinct for hybrids for example,
    e.g. how far back can they share a relationship?
    """

    def __init__(
            self,
            persistence_service: GermplasmPersistenceService,
            access_control_service: AbstractAccessControlService,
            release: ReadRelease = ReadRelease.PRIVATE
    ):
        self.persistence = persistence_service
        self.access_control = access_control_service
        self.release = release
        self.events: List[Event] = []

    @property
    def user_id(self):
        return self.access_control.user_id

    @property
    def access_teams(self):
        return self.access_control.access_teams

    def validate_write_permission(self):
        if not self.user_id:
            raise UnauthorisedOperationError("User ID required to write to the germplasm service")
        if not self.access_teams[Access.WRITE]:
            raise UnauthorisedOperationError("Write access required to write to the germplasm service")

    def collect_events(self):
        """Collect and clear accumulated events."""
        while self.events:
            yield self.events.pop(0)

    async def create_entry(
            self,
            entry: GermplasmInput
    ) -> GermplasmStored:
        """Create a new germplasm entry with validation and access control"""
        logger.debug(f"Creating germplasm entry: {entry.name}")
        self.validate_write_permission()

        # Validate entry uniqueness (names and abbreviation)
        await self._validate_entry_uniqueness(entry)
        # Create and persist entry
        stored_entry = await self.persistence.create_entry(entry)

        # Set up access controls for the new entry using stored teams
        await self.access_control.set_controls(
            models=stored_entry,
            control_teams=self.access_teams[Access.WRITE],
            release=self.release,
            user_id=self.user_id
        )
        # Record write stamp
        await self.access_control.record_writes(
            models=stored_entry,
            user_id=self.user_id
        )
        return stored_entry

    async def get_entry(self, entry_id: int) -> Optional[GermplasmStored]:
        """Retrieve a germplasm entry by ID with access control"""
        entry = await self.persistence.get_entry(entry_id)
        if not entry:
            return None

        # Check access control using stored context
        controller = await self.access_control.get_controller(entry.label, entry_id)
        if not controller:
            # No controller means no access control - return as is
            return entry
        if not controller.has_access(Access.READ, self.user_id, self.access_teams[Access.READ]):
            if self.user_id is None:
                return None  # Anonymous users get nothing for private entries
            return entry.redacted(controller, self.user_id, self.access_teams[Access.READ])

        return entry

    async def get_root_entries(self, as_output=False) -> AsyncGenerator[GermplasmStored, None]:
        """ retrieve germplasm entries that have no parents """
        root_entries = [entry async for entry in self.persistence.get_root_entries()]
        if not root_entries:
            return

        async for controlled_entry in self.yield_controlled_entries(root_entries, as_output=as_output):
            yield controlled_entry

    async def get_entries(
            self,
            entry_ids: List[int] | None = None,
            names: List[str] | None = None,
            as_output: bool = False
    ) -> AsyncGenerator[GermplasmStored, None]:
        """Retrieve all germplasm entries with optional filtering and access control using stored context."""
        # Get all entry IDs first to batch fetch controllers
        all_entries = []
        async for entry in self.persistence.get_entries(entry_ids=entry_ids, names=names):
            all_entries.append(entry)
        if not all_entries:
            return

        async for controlled_entry in self.yield_controlled_entries(all_entries, as_output=as_output):
            yield controlled_entry

    async def yield_controlled_entries(self, entries: List[GermplasmStored], as_output=False):
        # Batch fetch controllers for access control
        entry_ids = [entry.id for entry in entries]
        controllers = await self.access_control.get_controllers(
            label=ControlledModelLabel.GERMPLASM,
            model_ids=entry_ids
        )

        # Apply access control and yield results using stored context
        for entry in entries:
            controller = controllers.get(entry.id)

            if not controller:
                raise ValueError("Controller not found for entry")

            if controller.has_access(Access.READ, self.user_id, self.access_teams[Access.READ]):
                if as_output:
                    # get relationships and return where we have read access to the related entries
                    sources = []
                    sinks = []
                    relationships = [rel async for rel in self.get_relationships(entry.id)]
                    # get controllers for related:
                    related_model_ids = [next(x for x in [rel.source_id, rel.sink_id] if x != entry.id) for rel in relationships]
                    controllers_to_fetch = [i for i in related_model_ids if i not in controllers]
                    related_controllers = await self.access_control.get_controllers(
                        label=ControlledModelLabel.GERMPLASM,
                        model_ids=controllers_to_fetch
                    )
                    for rel in relationships:
                        other_id = next(x for x in [rel.source_id, rel.sink_id] if x != entry.id)
                        controller = controllers.get(other_id) if other_id in controllers else related_controllers.get(other_id)
                        if controller.has_access(Access.READ, self.user_id, self.access_teams[Access.READ]):
                            if rel.source_id == entry.id:
                                sinks.append(rel)
                            elif rel.sink_id == entry.id:
                                sources.append(rel)
                    yield entry.to_output(sources=sources, sinks=sinks)

                else:
                    yield entry

            elif self.user_id is not None:
                # Registered users get redacted version
                redacted_entry = entry.redacted(controller, self.user_id, self.access_teams[Access.READ])
                if redacted_entry:  # Some entries might return None when redacted
                    if as_output:
                        yield redacted_entry.to_output(sources=[], sinks=[])
                    else:
                        yield redacted_entry

    async def delete_entry(
            self,
            entry_id: int
    ) -> None:
        """Delete a germplasm entry with validation and access control"""
        logger.debug(f"Deleting germplasm entry: {entry_id}")
        controller = await self.access_control.get_controller(GermplasmStored.label, entry_id)
        if controller and not controller.has_access(Access.CURATE, self.user_id, self.access_teams[Access.CURATE]):
            raise UnauthorisedOperationError(
                f"User {self.user_id} does not have permission to delete germplasm entry {entry_id}"
            )
        async for _ in self.persistence.get_sink_relationships(entry_id):
            raise IllegalOperationError("Cannot delete entries that have sinks")
        await self.persistence.delete_entry(entry_id)

    async def update_entry(self, entry: GermplasmStored) -> None:
        """Update an existing germplasm entry with validation and access control using stored context."""
        if not entry.id:
            raise ValueError("Entry must have an ID for updates")

        # Check access control - user must have CURATE access using stored context
        controller = await self.access_control.get_controller(entry.label, entry.id)
        if controller and not controller.has_access(Access.CURATE, self.user_id, self.access_teams[Access.CURATE]):
            raise UnauthorisedOperationError(
                f"User {self.user_id} does not have permission to update germplasm entry {entry.id}"
            )
        # Validate uniqueness excluding current entry
        await self._validate_entry_uniqueness(entry, exclude_id=entry.id)

        # Update entry
        await self.persistence.update_entry(entry)

        # Record write stamp
        await self.access_control.record_writes(
            models=entry,
            user_id=self.user_id
        )


    async def update_entry_relationships(
            self,
            entry_id: int,
            sources: List[GermplasmRelationship]|None = None,
            sinks: List[GermplasmRelationship] | None = None
    ) -> None:
        """
        Reconcile source and sink relationships for an entry.
        Creates new relationships, updates changed ones, and removes ones no longer present.
        """
        logger.debug(f"Updating source and sink relationships for entry {entry_id}")

        # Validate curate permission on the entry
        controller = await self.access_control.get_controller(ControlledModelLabel.GERMPLASM, entry_id)
        if controller and not controller.has_access(Access.CURATE, self.user_id, self.access_teams[Access.CURATE]):
            raise UnauthorisedOperationError(
                f"User {self.user_id} does not have curate permission required to update relationships for germplasm entry {entry_id}"
            )

        # Get stored relationships
        stored_relationships = []
        if sources is not None and sinks is not None:
            async for rel in self.persistence.get_relationships(entry_id):
                stored_relationships.append(rel)
        elif sources is not None:
            async for rel in self.persistence.get_source_relationships(entry_id):
                stored_relationships.append(rel)
        elif sinks is not None:
            async for rel in self.persistence.get_sink_relationships(entry_id):
                stored_relationships.append(rel)

        # Create lookup keys for comparison
        def relationship_key(rel: GermplasmRelationship) -> tuple:
            """Create a unique key for a relationship based on source_id and sink_id"""
            return (rel.source_id, rel.sink_id)

        stored_by_key = {relationship_key(rel): rel for rel in stored_relationships}
        submitted_by_key = {}
        if sources is not None:
            submitted_by_key.update({relationship_key(rel): rel for rel in sources})
        if sinks is not None:
            submitted_by_key.update({relationship_key(rel): rel for rel in sinks})

        # Determine what needs to be created, updated, or deleted
        to_create = []
        to_update = []
        to_delete = []

        # Find new relationships and changed relationships
        for key, submitted_rel in submitted_by_key.items():
            if key not in stored_by_key:
                to_create.append(submitted_rel)
            else:
                stored_rel = stored_by_key[key]
                # Check if relationship details changed
                if (submitted_rel.source_type != stored_rel.source_type or
                        submitted_rel.description != stored_rel.description):
                    to_update.append(submitted_rel)

        # Find relationships to delete (in stored but not in submitted)
        for key, stored_rel in stored_by_key.items():
            if key not in submitted_by_key:
                if sources is not None and stored_rel.sink_id == entry_id:
                    to_delete.append(stored_rel)
                elif sinks is not None and stored_rel.source_id == entry_id:
                    to_delete.append(stored_rel)

        # Execute the changes
        if to_delete:
            logger.debug(f"Deleting {len(to_delete)} relationships for entry {entry_id}")
            await self.delete_relationships(to_delete)

        if to_update:
            logger.debug(f"Updating {len(to_update)} relationships for entry {entry_id}")
            await self.update_relationships(to_update)

        if to_create:
            logger.debug(f"Creating {len(to_create)} relationships for entry {entry_id}")
            await self.create_relationships(to_create)

    async def create_relationships(self, relationships: List[GermplasmRelationship]) -> None:
        for relationship in relationships:
            await self.validate_new_relationship(relationship)
        # Create the relationships
        await self.persistence.create_relationships(relationships)

    async def create_relationship(self, relationship: GermplasmRelationship) -> None:
        await self. create_relationships(relationships=[relationship])

    async def validate_new_relationship(self, relationship: GermplasmRelationship) -> None:
        """Add a source relationship between germplasm entries with access control"""
        sink_id = relationship.sink_id
        source_id = relationship.source_id
        source_type = relationship.source_type

        logger.debug(f"Adding source relationship: {source_id} -[{source_type}]> {sink_id}")

        # Check that user has WRITE access to sink and READ access to source using stored context
        controllers = await self.access_control.get_controllers(
            label=ControlledModelLabel.GERMPLASM,
            model_ids=[sink_id, source_id]
        )

        sink_controller = controllers.get(sink_id)
        source_controller = controllers.get(source_id)

        if sink_controller and not sink_controller.has_access(
                Access.WRITE, self.user_id, self.access_teams[Access.WRITE]
        ):
            raise IllegalOperationError(
                f"User {self.user_id} does not have permission to write source relationships to sink germplasm entry {sink_id}"
            )

        if source_controller and not source_controller.has_access(
                Access.READ, self.user_id, self.access_teams[Access.READ]
        ):
            raise IllegalOperationError(
                f"User {self.user_id} does not have permission to read source germplasm entry {source_id}"
            )

        # Validate both entries exist
        entries_exist = await self.persistence.entries_exist([sink_id, source_id])
        if not entries_exist.get(sink_id):
            raise ValueError(f"sink entry {sink_id} does not exist")
        if not entries_exist.get(source_id):
            raise ValueError(f"Source entry {source_id} does not exist")

        # Check for circular dependencies
        if await self.persistence.has_path(sink_id, source_id):
            raise ValueError(
                f"Adding relationship from {source_id} to {sink_id} would create a circular dependency"
            )

    async def update_relationships(self, relationships: List[GermplasmRelationship]) -> None:
        """Update existing relationships with new details."""
        for relationship in relationships:
            await self.update_relationship(relationship)

    async def update_relationship(self, relationship: GermplasmRelationship) -> None:
        """Update an existing relationship between germplasm entries."""
        sink_id = relationship.sink_id
        source_id = relationship.source_id
        source_type = relationship.source_type

        logger.debug(f"Updating source relationship: {source_id} -[{source_type}]> {sink_id}")

        # Check that user has CURATE access to sink
        controllers = await self.access_control.get_controllers(
            label=ControlledModelLabel.GERMPLASM,
            model_ids=[sink_id]
        )
        sink_controller = controllers.get(sink_id)
        if sink_controller and not sink_controller.has_access(
                Access.CURATE, self.user_id, self.access_teams[Access.CURATE]
        ):
            raise IllegalOperationError(
                f"User {self.user_id} does not have permission to curate source relationships to sink germplasm entry {sink_id}"
            )
        # Create the relationship
        await self.persistence.update_relationship(relationship)

    async def delete_relationships(self, relationships: List[GermplasmRelationship]) -> None:
        """Delete multiple relationships."""
        for relationship in relationships:
            await self.delete_relationship(relationship)

    async def delete_relationship(self, relationship: GermplasmRelationship) -> None:
        """Delete a relationship between germplasm entries with access control."""
        sink_id = relationship.sink_id

        # Check that user has CURATE access to sink
        controller = await self.access_control.get_controller(ControlledModelLabel.GERMPLASM, sink_id)
        if controller and not controller.has_access(Access.CURATE, self.user_id, self.access_teams[Access.CURATE]):
            raise UnauthorisedOperationError(
                f"User {self.user_id} does not have permission to curate relationships from germplasm entry {sink_id}"
            )

        await self.persistence.delete_relationship(relationship)



    async def validate_read(self, entry_id: int) -> None:
        """Check if user has read access to a germplasm entry using stored context."""
        sink_controller = await self.access_control.get_controller(ControlledModelLabel.GERMPLASM, entry_id)
        if not sink_controller.has_access(Access.READ, self.user_id, self.access_teams[Access.READ]):
            raise UnauthorisedOperationError(f"User {self.user_id} does not have read access to entry {entry_id}")

    async def get_relationships(self, entry_id: int) -> AsyncGenerator[GermplasmRelationship, None]:
        """Get all source relationships for a germplasm entry with access control."""
        await self.validate_read(entry_id)
        async for rel in self.persistence.get_relationships(entry_id):
            yield rel

    async def get_source_relationships(self, entry_id: int) -> AsyncGenerator[GermplasmRelationship, None]:
        await self.validate_read(entry_id)
        async for rel in self.persistence.get_source_relationships(entry_id):
            yield rel

    async def get_sink_relationships(self, entry_id: int) -> AsyncGenerator[GermplasmRelationship, None]:
        await self.validate_read(entry_id)
        async for rel in self.persistence.get_sink_relationships(entry_id):
            yield rel

    async def get_ancestor_ids(self, entry_id: int, path_length_limit=None) -> List[int]:
        return await self.persistence.get_ancestor_ids(entry_id, path_length_limit)

    async def get_descendant_ids(self, entry_id: int, path_length_limit=None) -> List[int]:
        return await self.persistence.get_descendant_ids(entry_id, path_length_limit)

    async def validate_control_permission(self, entry_ids: List[int]):
        if not self.user_id:
            raise UnauthorisedOperationError("User ID required to set controls in germplasm service")
        # Check that user has ADMIN access to the entry
        controllers = await self.access_control.get_controllers(ControlledModelLabel.GERMPLASM, entry_ids)
        for entry_id in entry_ids:
            controller = controllers.get(entry_id)
            if controller and not controller.has_access(
                    Access.ADMIN, self.user_id, self.access_teams[Access.ADMIN]
            ):
                raise UnauthorisedOperationError(
                    f"User {self.user_id} does not have permission to set controls on germplasm entry {entry_id}"
                )

    async def update_entry_controls(
            self,
            entry_ids: List[int],
            control_teams: Set[int],
            release: ReadRelease
    ) -> None:
        """Set access controls for a germplasm entry using stored context for authorization."""
        await self.validate_control_permission(entry_ids)
        # Set controls
        await self.access_control.set_controls_by_id_and_label(
            ids = entry_ids,
            label = ControlledModelLabel.GERMPLASM,
            control_teams=control_teams,
            release=release,
            user_id=self.user_id
        )

    # Validation methods
    async def _validate_entry_uniqueness(
            self,
            entry: GermplasmInput | GermplasmStored,
            exclude_id: int = None
    ) -> None:
        """Validate that entry names and abbreviation are unique."""
        # Check all names (including synonyms)
        for name in entry.names:
            if await self.persistence.name_in_use(name, exclude_id=exclude_id):
                raise ValueError(
                    f"Another germplasm entry is using the name '{name}'"
                )
