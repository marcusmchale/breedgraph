from abc import ABC, abstractmethod
from src.breedgraph.custom_exceptions import ProtectedNodeError, IdentityExistsError, IllegalOperationError
from src.breedgraph.domain.model.accounts import (
    UserInput, UserStored,
    AccountInput, AccountStored
)
from src.breedgraph.domain.model.organisations import Affiliation, Access, Authorisation

from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked, TrackedList
from src.breedgraph.adapters.repositories.base import BaseRepository
from src.breedgraph.domain.events.accounts import AccountAdded

# for typing only
from typing import AsyncGenerator
from neo4j import Record, AsyncResult, AsyncTransaction


import logging


logger = logging.getLogger(__name__)

class Neo4jAccountRepository(BaseRepository):

    def __init__(self, tx: AsyncTransaction):
        super().__init__()
        self.tx = tx

    async def _create(self, account: AccountInput) -> AccountStored:
        user = await self._create_user(account.user)
        account = AccountStored(user=user)
        account.events.append(AccountAdded(user=account.user.id))
        return account

    async def _create_user(self, user: UserInput) -> UserStored:
        logger.debug(f"Create user: {user}")
        result = await self.tx.run(
            queries['accounts']['create_user'],
            name=user.name,
            name_lower=user.name.casefold(),
            fullname=user.fullname,
            password_hash=user.password_hash,
            email=user.email,
            email_lower=user.email.casefold(),
            email_verified=user.email_verified
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

        if not any([team_ids, access_types, authorisations]):
            if user_ids:
                result = await self.tx.run(queries['accounts']['get_accounts'], user_ids = user_ids)
            else:
                result = await self.tx.run(queries['accounts']['get_all_accounts'])
        elif team_ids and not any([access_types, authorisations]):
            result = await self.tx.run(
                queries['accounts']['get_accounts_by_teams'],
                team_ids=team_ids,
                access_types=[a.name for a in access_types],
                authorisations=[a.name for a in authorisations]
            )
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
                result = await self.tx.run(
                    queries['accounts']['get_accounts_by_teams_affiliation'],
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

    async def _update(self, account: Tracked|AccountStored):
        await self._set_user(account.user)
#        await self._update_affiliations(account.user, account.affiliations)
        await self._update_allowed_emails(account.user, account.allowed_emails)


    async def _set_user(self, user: Tracked|UserStored):
        if user.changed:
            await self.tx.run(
                queries['accounts']['set_user'],
                user=user.id,
                name = user.name,
                name_lower=user.name.casefold(),
                fullname = user.fullname,
                email = user.email,
                email_lower = user.email.casefold(),
                email_verified = user.email_verified,
                password_hash = user.password_hash
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
            password_hash=record['password_hash']
        ) if record else None

    def record_to_account(self, record: Record) -> AccountStored:
        return AccountStored(
            user=self.user_record_to_user(record['user']),
            allowed_emails=record['allowed_emails'],
            allowed_users=record['allowed_users']
        ) if record else None

