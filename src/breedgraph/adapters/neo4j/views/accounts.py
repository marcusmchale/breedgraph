from neo4j import AsyncResult, AsyncSession
from typing import AsyncGenerator

from src.breedgraph.service_layer.queries.views.accounts import AbstractAccountsView
from src.breedgraph.domain.model.accounts import UserOutput, OntologyRole

from src.breedgraph.adapters.neo4j.cypher import queries

from typing import List

class Neo4jAccountsView(AbstractAccountsView):
    def __init__(
            self,
            session: AsyncSession,
            user_id: int | None = None
    ):
        self.session = session
        self.user_id = user_id

        self.admin_teams: List[int]|None = None
        self.read_teams: List[int]|None = None
        self.ontology_role: OntologyRole|None = None

    async def check_any_account(self) -> bool:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(queries['accounts']['check_any_account'])
            record = await result.single()
            return record.value()

    async def check_allowed_email(self, email: str) -> bool:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(
                queries['accounts']['check_allowed_email'],
                email_lower=email.casefold()
            )
            record = await result.single()
            return record.value()

    async def _get_user(self) -> UserOutput:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(queries['accounts']['get_user'], user_id=self.user_id)
            record = await result.single(strict=True)
            user = UserOutput(**record['user'])
            self.ontology_role = record['ontology_role']
            return user

    async def _get_ontology_role(self) -> OntologyRole:
        if self.ontology_role is None:
            async with await self.session.begin_transaction() as tx:
                result: AsyncResult = await tx.run(queries['controls']['get_ontology_role'], user_id=self.user_id)
                record = await result.single()
                self.ontology_role = OntologyRole(record.value() or 'viewer')
        return self.ontology_role

    async def _get_admin_teams(self) -> List[int]:
        query = queries['controls']['get_admin_teams']
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(query, user_id=self.user_id)
            record = await result.single()
            if record:
                return record.value() or []
            else:
                return []

    async def _get_read_teams(self) -> List[int]:
        query = queries['controls']['get_read_teams']
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(query, user_id=self.user_id)
            record = await result.single()
            if record:
                return record.value() or []
            else:
                return []

    async def _get_users_for_admin(self, user_ids: List[int], admin_teams: List[int]) -> AsyncGenerator[UserOutput, None]:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(
                queries['accounts']['get_users_for_admin'],
                admin_teams=admin_teams,
                user_ids=user_ids
            )
            async for record in result:
                user_output: UserOutput = UserOutput(**record['user'])
                yield user_output

    async def _get_users_with_ontology_role_requests(self) -> AsyncGenerator[UserOutput, None]:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(queries['accounts']['get_users_with_ontology_role_requests'])
            async for record in result:
                user_output: UserOutput = UserOutput(**record['user'])
                yield user_output

    async def _get_editors_for_ontology_admin(self) -> AsyncGenerator[UserOutput, None]:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(queries['accounts']['get_editors_for_ontology_admin'])
            async for record in result:
                user_output: UserOutput = UserOutput(**record['user'])
                yield user_output

    async def _get_admins_for_ontology_admin(self) -> AsyncGenerator[UserOutput, None]:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(queries['accounts']['get_admins_for_ontology_admin'])
            async for record in result:
                user_output: UserOutput = UserOutput(**record['user'])
                yield user_output



