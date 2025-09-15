from src.breedgraph.domain.model.accounts import (
    UserInput, UserStored,
    AccountInput, AccountStored,
    OntologyRole
)
from src.breedgraph.domain.model.organisations import Access, Authorisation

from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.service_layer.tracking import TrackableProtocol, TrackedList
from src.breedgraph.service_layer.repositories.base import BaseRepository
from src.breedgraph.domain.events.accounts import AccountCreated

# for typing only
from typing import AsyncGenerator
from neo4j import Record, AsyncResult, AsyncTransaction

import logging

logger = logging.getLogger(__name__)

TAggregateInput = AccountInput
TAggregate = AccountStored

class Neo4jAccountRepository(BaseRepository):

    def __init__(self, tx: AsyncTransaction):
        super().__init__()
        self.tx = tx

    async def _create(self, account: AccountInput) -> AccountStored:
        user = await self._create_user(account.user)
        account = AccountStored(user=user)
        account.events.append(AccountCreated(user=account.user.id))
        return account

    async def _create_user(self, user: UserInput) -> UserStored:
        logger.debug(f"Create user: {user}")
        props = user.model_dump()
        props['name_lower'] = user.name.casefold()
        props['email_lower'] = user.email.casefold()
        result = await self.tx.run(
            queries['accounts']['create_user'],
            props=props
        )
        record = await result.single()
        return self.user_record_to_user(record['user'])

    async def _get(self, user_id=None, name=None, email=None) -> AccountStored|None:
        if user_id is not None:
            result: AsyncResult = await self.tx.run(
                queries['accounts']['get_account'],
                user=user_id
            )
        elif name is not None:
            result: AsyncResult = await self.tx.run(
                queries['accounts']['get_account_by_name'],
                name_lower=name.casefold()
            )
        elif email is not None:
            result: AsyncResult = await self.tx.run(
                queries['accounts']['get_account_by_email'],
                email_lower=email.casefold()
            )
        else:
            try:
                return await anext(self._get_all())
            except StopAsyncIteration:
                return None

        record: "Record" = await result.single()
        return self.record_to_account(record) if record else None

    async def _get_all(self, **kwargs) -> AsyncGenerator[AccountStored, None]:
        user_ids = kwargs.get('user_ids')
        team_ids = kwargs.get('team_ids')
        access_types = kwargs.get('access_types')
        authorisations = kwargs.get('authorisations')
        allowed_email = kwargs.get('allowed_email')

        if not any([team_ids, access_types, authorisations]):
            if user_ids:
                result = await self.tx.run(queries['accounts']['get_accounts'], user_ids = user_ids)
            else:
                if allowed_email:
                    result: AsyncResult = await self.tx.run(
                        queries['accounts']['get_accounts_by_allowed_email'],
                        email_lower=allowed_email.casefold()
                    )
                else:
                    result = await self.tx.run(queries['accounts']['get_all_accounts'])
        else:
            access_types = kwargs.get('access_types', [a for a in Access])
            authorisations = kwargs.get('authorisations', [a for a in Authorisation])
            if not team_ids and any([access_types, authorisations]):
                result = await self.tx.run(
                    queries['accounts']['get_accounts_by_affiliation'],
                    access_types=[a for a in access_types],
                    authorisations=[a for a in authorisations]
                )
            else:
                if isinstance(team_ids, set):
                    team_ids = list(team_ids)
                result = await self.tx.run(
                    queries['accounts']['get_accounts_by_teams_affiliations'],
                    teams=team_ids,
                    access_types=[a for a in access_types],
                    authorisations=[a for a in authorisations]
                )
        async for record in result:
            yield self.record_to_account(record)

    async def _remove(self, account: AccountStored):
        await self.tx.run(
            queries['accounts']['remove_unverified_user'],
            email_lower=account.user.email.casefold()
        )

    async def _update(self, account: TrackableProtocol|AccountStored):
        logger.debug("update user in neo4j")
        await self._set_user(account.user)
        logger.debug("update allowed emails in neo4j")
        await self._update_allowed_emails(account.user, account.allowed_emails)

    async def _set_user(self, user: TrackableProtocol|UserStored):
        if user.changed:
            props = user.model_dump()
            change_props = {
                attr: props[attr] for attr in user.changed
            }
            if 'name' in user.changed:
                change_props.update({'name_lower': user.name.casefold()})
            if 'email' in user.changed:
                change_props.update({'email_lower': user.email.casefold()})
            await self.tx.run(
                queries['accounts']['set_user'], props=props
            )

    async def _update_allowed_emails(self, user: UserStored, allowed_emails: TrackedList[str]):
        # Then create/remove allowed_emails (changes are not tracked for strings)
        for i in allowed_emails.added:
            await self.tx.run(
                queries['accounts']['create_allowed_email'],
                user=user.id,
                email=allowed_emails[i],
                email_lower=allowed_emails[i].casefold()
            )
        for email in allowed_emails.removed:
            await self.tx.run(
                queries['accounts']['remove_allowed_email'],
                user=user.id,
                email_lower=email.casefold()
            )

    @staticmethod
    def user_record_to_user(record) -> UserStored:
        return UserStored(
            name=record['name'],
            fullname=record['fullname'],
            email=record['email'],
            email_verified=record['email_verified'],
            id=record['id'],
            password_hash=record['password_hash'],
            ontology_role=OntologyRole(record['ontology_role'])
        ) if record else None

    def record_to_account(self, record: Record) -> AccountStored:
        return AccountStored(
            user=self.user_record_to_user(record['user']),
            allowed_emails=record['allowed_emails'],
            allowed_users=record['allowed_users']
        ) if record else None

