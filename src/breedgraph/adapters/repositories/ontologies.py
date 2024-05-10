import logging
import re

from abc import ABC, abstractmethod
from neo4j import AsyncTransaction, AsyncResult, Record
from neo4j.exceptions import ConstraintError

from src.breedgraph.domain.model.ontologies import (
    OntologyEntry, OntologyEntryStored, Ontology, Version
)
from src.breedgraph.domain.model.people import Person

from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked, TrackedList
from src.breedgraph.custom_exceptions import ProtectedNodeError, IllegalOperationError

from src.breedgraph.adapters.repositories.base import BaseRepository, Aggregate

from typing import Set, AsyncGenerator

logger = logging.getLogger(__name__)


class Neo4jOntologyRepository(BaseRepository):

    def __init__(self, tx: AsyncTransaction):
        super().__init__()
        self.tx = tx

    async def _create(self, ontology: Ontology) -> Ontology:
        for i, ref in enumerate(ontology.references):
            ontology.references[i] = await self._create_reference(ref)
        return ontology

    async def _create_reference(self, reference: OntologyEntry) -> OntologyEntryStored:
        params = {
            'parent': reference.parent,
            'name': reference.name,
            'description': reference.description,
            'version': reference.version.name,
            'authors': reference.authors,
            'references': reference.references,
            'copyright': reference.copyright,
            'licence': reference.licence
        }
        if reference.parent is None:
            result = await self.tx.run(queries['create_ontology_reference'], params)
        else:
            result = await self.tx.run(queries['create_ontology_reference_with_parent'], params)
        record = await result.single()
        return self.record_to_reference(record)

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

