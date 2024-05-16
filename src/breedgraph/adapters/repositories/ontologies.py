import logging
import re

from abc import ABC, abstractmethod
from neo4j import AsyncTransaction, AsyncResult, Record
from neo4j.exceptions import ConstraintError

from src.breedgraph.domain.model.people import Person
from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked, TrackedList
from src.breedgraph.custom_exceptions import ProtectedNodeError, IllegalOperationError
from src.breedgraph.domain.model.references import LegalReference, LegalReferenceStored
from src.breedgraph.adapters.repositories.base import BaseRepository, Aggregate, Entity

from typing import Set, AsyncGenerator

from src.breedgraph.domain.model.ontologies import (
    Ontology,
    Version, VersionStored,
    OntologyEntry, OntologyEntryStored,
    Term, TermStored,
    Subject, SubjectStored,
    Trait, TraitStored, Method, MethodStored, Scale, ScaleStored, Variable, VariableStored,
    Parameter, ParameterStored, Condition, ConditionStored,
    Exposure, ExposureStored, EventType, EventTypeStored,
    LocationType, LocationTypeStored
)

from typing import List

logger = logging.getLogger(__name__)

generic_ontology_entries = [
    Term, TermStored,
    Subject, SubjectStored,
    LocationType, LocationTypeStored
]

class Neo4jOntologyRepository(BaseRepository):

    def __init__(self, tx: AsyncTransaction):
        super().__init__()
        self.tx = tx

    async def _create(self, ontology: Ontology) -> Ontology:
        ontology.version = await self._create_version(ontology.version)
        await self._set_licence(ontology.licence, ontology.version.id)
        await self._set_copyright(ontology.copyright, ontology.version.id)
        await self._update_terms(ontology.terms, ontology.version.id)
        return ontology

    async def _create_version(self, version: Version) -> VersionStored:
        version_result = await self.tx.run(
            queries['ontologies']['create_version'],
            major=version.major,
            minor=version.minor,
            patch=version.patch,
            comment=version.comment
        )
        version_record = await version_result.single()
        return VersionStored(**dict(version_record))

    async def _set_licence(self, licence_id: int, version_id: int) -> None:
        await self.tx.run(
            queries['ontologies']['set_licence'],
            licence=licence_id,
            version=version_id
        )

    async def _set_copyright(self, copyright_id: int, version_id: int) -> None:
        await self.tx.run(
            queries['ontologies']['set_copyright'],
            copyright=copyright_id,
            version=version_id
        )

    async def _update_terms(self, terms, version_id):
        

    async def _update_entries(self, ontology):
        forked_entries = dict()
        for attr in ontology.model_fields_set:
            entries = getattr(ontology, attr)
            if isinstance(entries, TrackedList):
                for entry in value:




                if not isinstance(entries, TrackedList):
                    raise TypeError("OntologyEntries must be TrackedList for Neo4j repository updates")

                # iterate through added and adding and changed setting, then removed removing


                if not entries.changed:
                            return

                for entry in entries:
                    # replace forked references with their updated ID for creation
                    # each node takes care of updates only to its parents, so we can ignore children
                    # these can be repaired with the full pass performed at the end
                    for i, j in enumerate(entry.parents):
                        if i in forked_entries:
                            entry.parents[j] = forked_entries[i]

                    if entry.changed or entry in entries.added:
                        new_entry_id = await self._create_entry(entry, ontology.version)
                        if hasattr(entry, 'id'):
                            forked_entries[entry.id] = new_entry_id




                    elif entry in entries.removed:
                        await self._exclude_entry(entry, ontology.version)
                    else:
                        await self._include_entry(entry, ontology.version)

        for attr in ontology.model_fields_set:
            entries = getattr(ontology, attr)
            # todo after all DB updates; run through and replace all remaining forked references
            entries.reset_tracking()

    async def _create_entry(self, entry: OntologyEntry, version: Version) -> int:
        if isinstance(entry, Entity):
            # Fork entry:
            # Move any stored references with current version to the new node.
            # then create a new one and link it to the new version
            pass

        if isinstance(entry, Term):
            await self._create_term(entry, version)

    async def _create_term(self, term: Term, version: Version):
        await self.tx.run(
            queries['create_term'],

        )




    @staticmethod
    def record_to_reference(record: Record) -> OntologyEntryStored:
        version_tuple = re.split('\.|-',record['ontology']['version'],3)
        version = Version(
            major=int(version_tuple[0]),
            minor=int(version_tuple[1]),
            patch=int(version_tuple[2]),
            comment=version_tuple[3]
        )
        import pdb; pdb.set_trace()
        ontology = OntologyEntryStored(
            id=record['ontology']['id'],
            name=record['ontology']['name'],
            description=record['ontology']['description'],
            version=version,
            authors=record['ontology']['authors'],
            references=record['ontology']['references'],
            children=record['ontology']['children'],
            uses=record['ontology']['uses']
        )
        import pdb; pdb.set_trace()
        return OntologyEntryStored(**record['ontology'])

    async def _get(self, db_id: int) -> Ontology:
        raise NotImplementedError

    def _get_all(self) -> AsyncGenerator[Ontology, None]:
        raise NotImplementedError

    async def _remove(self, ontology: Ontology) -> None:
        raise NotImplementedError

    async def _update(self, ontology: Ontology):
        raise NotImplementedError

