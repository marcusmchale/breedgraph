import logging

from src.breedgraph.custom_exceptions import UnauthorisedOperationError

from src.breedgraph.adapters.neo4j.cypher import queries

from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked
from src.breedgraph.adapters.repositories.controlled import Neo4jControlledRepository

from typing import AsyncGenerator

from src.breedgraph.domain.model.germplasm import GermplasmEntryInput, GermplasmEntryStored, Germplasm

logger = logging.getLogger(__name__)


class Neo4jGermplasmRepository(Neo4jControlledRepository):

    async def _create_controlled(
            self,
            entry: GermplasmEntryInput
    ) -> Germplasm:
        params = entry.model_dump()
        params['writer'] = self.user_id
        controller = params.pop('controller')
        params['controls'] = [{'team': key, 'release': value['release']} for key, value in controller['controls'].items()]
        result = await self.tx.run(queries['germplasm']['create_entry'], **params)
        record = await result.single()
        entry = self.record_to_entry(record['entry'])
        return Germplasm(nodes=[entry])

    async def _get_controlled(
            self,
            entry_id: int = None
    ) -> Germplasm | None:
        if entry_id is None:
            try:
                return await anext(self._get_all_controlled())
            except StopAsyncIteration:
                return None

        result = await self.tx.run(
            queries['germplasm']['get_germplasm'],
            entry=entry_id
        )
        nodes = []
        edges = []
        async for record in result:
            entry = self.record_to_entry(record['entry'])
            nodes.append(entry)
            for edge in record.get('sources', []):
                import pdb; pdb.set_trace()
                edges.append(edge)

        if nodes:
            return Germplasm(nodes=nodes, edges=edges)
        else:
            return None

    async def _get_all_controlled(self) -> AsyncGenerator[Germplasm, None]:
        result = await self.tx.run(queries['germplasm']['get_germplasms'])
        async for record in result:
            entries = [self.record_to_entry(entry) for entry in record['germplasm']]
            edges = [edge for entry in record['germplasm'] for edge in entry.get('sources', [])]
            yield Germplasm(nodes=entries, edges=edges)

    async def _remove_controlled(self, germplasm: GermplasmEntryStored):
        if not germplasm.controller.can_admin(self.account):
            raise UnauthorisedOperationError("Person can only be removed by an admin for the person record")

        await self.tx.run(queries['people']['remove_person'], germplasm_id=germplasm.id)

    async def _update_controlled(self, germplasm: GermplasmEntryStored | Tracked):
        if germplasm.changed:
            if 'controller' in germplasm.changed:
                if not germplasm.controller.can_admin(self.account):
                    raise UnauthorisedOperationError("Only admins can change controls")

                await self._update_entity_controller(germplasm)

            if germplasm.changed != {'controller'}:
                if not germplasm.controller.can_curate(self.account):
                    raise UnauthorisedOperationError("Updates can only be performed by accounts with curate control")

                await self._update_germplasm(germplasm)

    async def _update_germplasm(self, germplasm: GermplasmEntryStored):
        params = germplasm.model_dump()
        params['writer'] = self.account.user.id
        await self.tx.run(
            queries['germplasm']['set_germplasm'],
            params
        )

    @staticmethod
    def record_to_entry(record) -> GermplasmEntryStored:
        record['controller']['controls'] = {
            control['team']: {
                'release': control['release'],
                'time': control['time']
            } for control in record['controller']['controls']
        }
        return GermplasmEntryStored(**record)
