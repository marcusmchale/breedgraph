from neo4j import AsyncSession, AsyncResult, AsyncTransaction
from neo4j.exceptions import ResultNotSingleError

from breedgraph.domain.model.time_descriptors import deserialize_time

from breedgraph.domain.model.ontology import (
    OntologyCommit,
    Version,
    OntologyEntryLabel
)

from breedgraph.service_layer.queries.views import AbstractOntologyView
from breedgraph.service_layer.queries.read_models import (
    Ontology,
    OntologyEntryOutput,
    OntologyViewMode,
    OntologyRelationshipOutput
)

from breedgraph.service_layer.mappers import ontology_mapper
from breedgraph.adapters.neo4j.cypher import queries
from breedgraph.adapters.neo4j.ontology_records import record_to_entry, record_to_relationships

from typing import List

import logging
logger = logging.getLogger(__name__)


class Neo4jOntologyView(AbstractOntologyView):

    QUERY_MAP = {
        'ontology': {
            OntologyViewMode.EDITORIAL: {
                'current': queries['ontology']['ontology_editorial']
            },
            OntologyViewMode.PUBLISHED: {
                'current': queries['ontology']['ontology_published'],
                'historic': queries['ontology']['ontology_published_historic']
            }
        },
        'entries': {
            OntologyViewMode.EDITORIAL: {
                'current': {
                    'id': queries['ontology']['ontology_entries_editorial'],
                    'label': queries['ontology']['ontology_entries_by_label_editorial']
                }
            },
            OntologyViewMode.PUBLISHED: {
                'current': {
                    'id': queries['ontology']['ontology_entries_published'],
                    'label': queries['ontology']['ontology_entries_by_label_published']
                },
                'historic': {
                    'id': queries['ontology']['ontology_entries_published_historic'],
                    'label': queries['ontology']['ontology_entries_by_label_published_historic']
                }
            },
            OntologyViewMode.REFERENTIAL: {
                'current': {
                    'id': queries['ontology']['ontology_entries_referential']
                }
            }
        },
        'relationships': {
            OntologyViewMode.EDITORIAL: {
                'current': queries['ontology']['ontology_relationships_editorial']
            },
            OntologyViewMode.PUBLISHED: {
                'current': queries['ontology']['ontology_relationships_published'],
                'historic': queries['ontology']['ontology_relationships_published_historic']
            }
        }
    }

    def __init__(self, session: AsyncSession):
        super().__init__()
        self.session = session
        #todo ontology mapper might be class attribute
        self.ontology_mapper = ontology_mapper

    async def _get_current_version(self, tx: AsyncTransaction|None = None) -> Version:
        if tx is not None:
            return await self._get_current_version_tx(tx)

        async with await self.session.begin_transaction() as tx:
            return await self._get_current_version_tx(tx)

    @staticmethod
    async def _get_current_version_tx(tx: AsyncTransaction):
        query = queries['ontology']['get_latest_version']
        result = await tx.run(query)
        try:
            record = await result.single(strict=True)
            return Version.from_packed(record["commit.version"])
        except ResultNotSingleError:
            logger.debug("No version found, returning initial version")
        return Version(
            major=0,
            minor=0,
            patch=0
        )

    async def _get_ontology(self, version: Version, view: OntologyViewMode) -> Ontology:
        entries: List[OntologyEntryOutput] = []
        relationships: List[OntologyRelationshipOutput] = []
        async with await self.session.begin_transaction() as tx:
            current_version = await self._get_current_version_tx(tx)
            version_type = 'current' if current_version == version else 'historic'
            if view == OntologyViewMode.EDITORIAL and version_type == 'historic':
                raise ValueError("Editorial view is only supported for the current version")
            query = self.QUERY_MAP['ontology'][view][version_type]

            params = {'version': version.packed_version}
            result: AsyncResult = await tx.run(query, **params)
            async for record in result:
                entries.append(record_to_entry(record, version, view))
                relationships.extend(record_to_relationships(record, version, view))
            return Ontology(
                version=version,
                view=view,
                entries=tuple(entries),
                relationships=tuple(relationships)
            )

    async def _get_entries(
        self,
        version: Version,
        view: OntologyViewMode,
        entry_ids: list[int] | None = None,
        labels: list[OntologyEntryLabel] | None = None
    ) -> List[OntologyEntryOutput]:
        if not entry_ids and not labels:
            return []
        if entry_ids and labels:
            raise ValueError("Specify either entry_ids or labels, not both.")

        async with await self.session.begin_transaction() as tx:
            current_version = await self._get_current_version_tx(tx)
            version_type = 'current' if current_version == version else 'historic'
            if view in [OntologyViewMode.REFERENTIAL, OntologyViewMode.EDITORIAL] and version_type == 'historic':
                raise ValueError("Only published view is supported for historic versions")

            filter_type = 'id' if entry_ids else 'label'
            query = self.QUERY_MAP['entries'][view][version_type][filter_type]

            if entry_ids:
                params = {
                    'entry_ids': entry_ids,
                    'version': version.packed_version
                }
            elif labels:
                if view == OntologyViewMode.REFERENTIAL:
                    raise ValueError("Referential view is only supported for entries by ID, not by labels")
                params = {
                    'labels': [l.value for l in labels],
                    'version': version.packed_version
                }
            result: AsyncResult = await tx.run(query, **params)
            return [record_to_entry(record, version, view) async for record in result]

    async def _get_relationships(
        self,
        entry_ids: list[int],
        version: Version,
        view: OntologyViewMode
    ) -> List[OntologyRelationshipOutput]:
        async with await self.session.begin_transaction() as tx:
            current_version = await self._get_current_version_tx(tx)
            version_type = 'current' if current_version == version else 'historic'
            if view == OntologyViewMode.EDITORIAL and version_type == 'historic':
                raise ValueError("Editorial view is only supported for the current version")

            query = self.QUERY_MAP['relationships'][view][version_type]
            params = {
                'entry_ids': entry_ids,
                'version': version.packed_version
            }
            result: AsyncResult = await tx.run(query, **params)
            record = await result.single(strict=True)
            return record_to_relationships(record, version=version, view=view)


    @staticmethod
    def record_to_commit(record) -> OntologyCommit:
        commit_data = record['commit']
        commit_data['time'] = deserialize_time(commit_data['time'])
        commit_data['version'] = Version.from_packed(commit_data['version'])
        return OntologyCommit(**commit_data)

    async def _get_commits(self, limit: int|None = None, last_version_id: int|None = None) -> List[OntologyCommit]:
        async with await self.session.begin_transaction() as tx:
            if limit is None and last_version_id is None:
                query = queries['ontology']['get_commit_history']
                result = await tx.run(query)
            elif limit is None and last_version_id is not None:
                query = queries['ontology']['get_commit_history_with_last_version']
                result = await tx.run(query, last_version=last_version_id)

            elif limit is not None and last_version_id is None:
                query = queries['ontology']['get_commit_history_with_limit']
                result = await tx.run(query, limit=limit)

            else:
                query = queries['ontology']['get_commit_history_pagination']
                result = await tx.run(query, limit=limit, last_version=last_version_id)

            return [self.record_to_commit(record) async for record in result]