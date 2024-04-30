from abc import ABC, abstractmethod
from src.breedgraph.custom_exceptions import ProtectedNodeError, IdentityExistsError, IllegalOperationError
from src.breedgraph.domain.model.accounts import (
    UserInput, UserStored,
    Access, Authorisation, Affiliation,
    AccountInput, AccountStored
)

from src.breedgraph.domain.model.organisations import (
    TeamOutput
)


from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked, TrackedList
from src.breedgraph.adapters.neo4j.cypher import queries

# for typing only
from typing import Set, AsyncGenerator, Union, List, ValuesView, Dict, TypedDict
from neo4j import Record, AsyncResult, AsyncTransaction

import logging


logger = logging.getLogger(__name__)

class BaseAccountRepository(ABC):

    def __init__(self):
        self.seen: Set[AccountStored] = set()

    def _track(self, account: AccountStored):
        account.user = Tracked(account.user)
        account.affiliations = TrackedList(account.affiliations)
        account.allowed_emails = TrackedList(account.allowed_emails)
        self.seen.add(account)

    async def create(self, account: AccountInput) -> AccountStored:
        account_stored = await self._create(account)
        self._track(account_stored)
        return account_stored

    @abstractmethod
    async def _create(self, account: AccountInput) -> AccountStored:
        raise NotImplementedError

    async def get(self, user: int) -> AccountStored:
        account = await self._get(user)
        if account is not None:
            self._track(account)
        return account

    @abstractmethod
    async def _get(self, user: int) -> AccountStored:
        raise NotImplementedError

    async def get_by_email(self, email: str) -> AccountStored:
        account = await self._get_by_email(email.casefold())
        if account:
            self._track(account)
        return account

    @abstractmethod
    async def _get_by_email(self, email: str) -> AccountStored:
        raise NotImplementedError

    async def get_by_name(self, name: str) -> AccountStored:
        account = await self._get_by_name(name)
        if account:
            self._track(account)
        return account

    @abstractmethod
    async def _get_by_name(self, name: str) -> AccountStored:
        raise NotImplementedError

    async def get_all(
            self,
            team_ids: None|List[int] = None,
            access_types: None|List[Access] = None,
            authorisations: None|List[Authorisation] = None
    ) -> AsyncGenerator[AccountStored, None]:

        accounts = self._get_all(
            team_ids=team_ids,
            access_types=access_types,
            authorisations=authorisations
        )
        # typing issue here seems to be a bug in pycharm https://youtrack.jetbrains.com/issue/PY-40458
        async for account in accounts:
            self._track(account)
            yield account

    @abstractmethod
    def _get_all(
            self,
            team_ids: None|List[int] = None,
            access_types: None|List[Access] = None,
            authorisations: None|List[Authorisation] = None
    ) -> AsyncGenerator[AccountStored, None]:
        raise NotImplementedError

    async def remove(self, account: AccountStored):
        if account.user.email_verified:
            raise ProtectedNodeError
        await self._remove(account)

    @abstractmethod
    async def _remove(self, account: AccountStored):
        raise NotImplementedError

    async def update_seen(self):
        for account in self.seen:
            await self._update(account)

    @abstractmethod
    async def _update(self, account: AccountStored):
        raise NotImplementedError

class Neo4jAccountRepository(BaseAccountRepository):

    def __init__(self, tx: AsyncTransaction):
        super().__init__()
        self.tx = tx

    async def _create(self, account: AccountInput) -> AccountStored:
        user = await self._create_user(account.user)
        return await self._get(user=user.id)

    async def _create_user(self, user: UserInput) -> UserStored:
        logger.debug(f"Create user: {user}")
        result = await self.tx.run(
            queries['create_user'],
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

    async def _set_affiliation(self, user: UserStored, affiliation: Affiliation) -> Affiliation:
        # if none type just return, these are inferred from exposed root teams and not stored
        if affiliation.access == Access.NONE:
            return affiliation

        if affiliation.access == Access.READ:
            query = queries['set_read']
        elif affiliation.access == Access.WRITE:
            query = queries['set_write']
        elif affiliation.access == Access.ADMIN:
            query = queries['set_admin']
        else:
            raise TypeError("Unknown affiliation type")

        await self.tx.run(
            query,
            user=user.id,
            team=affiliation.team,
            authorisation=affiliation.authorisation.name,
            heritable=affiliation.heritable
        )
        return affiliation

    async def _remove_affiliation(self, user: UserStored, affiliation: Affiliation) -> None:

        if affiliation.access == Access.NONE:
            return

        if affiliation.access == Access.READ:
            query = queries['remove_read']
        elif affiliation.access == Access.WRITE:
            query = queries['remove_write']
        elif affiliation.access == Access.ADMIN:
            query = queries['remove_admin']
        else:
            raise TypeError("Unknown affiliation")

        await self.tx.run(query, user=user.id, team=affiliation.team)

    async def _get(self, user: int) -> AccountStored:
        result: AsyncResult = await self.tx.run(
            queries['get_account'],
            user=user
        )
        record: "Record" = await result.single()
        return self.record_to_account(record) if record else None

    async def _get_by_email(self, email: str) -> AccountStored:
        result: AsyncResult = await self.tx.run(
            queries['get_account_by_email'],
            email_lower=email
        )
        record: Record = await result.single()
        return self.record_to_account(record) if record else None

    async def _get_by_name(self, name: str) -> AccountStored:
        result: AsyncResult = await self.tx.run(
            queries['get_account_by_name'],
            name_lower=name.casefold()
        )
        record: Record = await result.single()
        return self.record_to_account(record) if record else None

    async def _get_all(
            self,
            team_ids: None|List[int] = None,
            access_types: None|List[Access] = None,
            authorisations: None|List[Authorisation] = None
    ) -> AsyncGenerator[AccountStored, None]:

        if not authorisations:
            authorisations = [a for a in Authorisation]
        else:
            authorisations = [a.name for a in authorisations]

        if not access_types:
            access_types = [a for a in Access]
        else:
            access_types = [a.name for a in access_types]

        if 'NONE' in access_types:
            result = self.tx.run(
                queries['get_accounts'],
                access_types=access_types,
                authorisations=authorisations
            )
        elif team_ids:
            result = self.tx.run(
                queries['get_accounts_by_teams'],
                team_ids=team_ids,
                access_types=access_types,
                authorisations=authorisations
            )
        else:
            result = self.tx.run(
                queries['get_accounts_by_affiliation'],
                access_types=access_types,
                authorisations=authorisations
            )

        async for record in await result:
            yield self.record_to_account(record)

    async def _remove(self, account: AccountStored):
        await self.tx.run(
            queries['remove_unverified_user'],
            email_lower=account.user.email.casefold()
        )

    async def _update(self, account: AccountStored):
        await self._set_user(account.user)
        await self._update_affiliations(account.user, account.affiliations)
        await self._update_allowed_emails(account.user, account.allowed_emails)

    async def _set_user(self, user: UserStored):

        if not isinstance(user, Tracked):
            raise IllegalOperationError("User changes must be tracked for neo4j updates")

        if user.changed:
            await self.tx.run(
                queries['set_user'],
                user=user.id,
                name = user.name,
                name_lower=user.name.casefold(),
                fullname = user.fullname,
                email = user.email,
                email_lower = user.email.casefold(),
                email_verified = user.email_verified,
                password_hash = user.password_hash
            )
            user.reset_tracking()

    async def _update_affiliations(self, user: UserStored, affiliations: List[Affiliation]):
        if not isinstance(affiliations, TrackedList):
            raise TypeError("Affiliations must be TrackedList for neo4j repository updates")

        if not affiliations.changed:
            return

        # Can't just iterate over added as there might be changes to affiliations
        for affiliation in affiliations:
            if affiliation.changed or affiliation in affiliations.added:
                await self._set_affiliation(user, affiliation)

        for affiliation in affiliations.removed:
            await self._remove_affiliation(user, affiliation)

        affiliations.reset_tracking()


    async def _update_allowed_emails(self, user: UserStored, allowed_emails: List[str]):

        if not isinstance(allowed_emails, TrackedList):
            raise IllegalOperationError("Allowed emails must be tracked for neo4j updates")

        if not allowed_emails.changed:
            return

        # Then create/remove allowed_emails
        for email in allowed_emails.added:
            await self.tx.run(
                queries['create_allowed_email'],
                user=user.id,
                email=email,
                email_lower=email.casefold()
            )
        for email in allowed_emails.removed:
            await self.tx.run(
                queries['remove_allowed_email'],
                user=user.id,
                email_lower=email.casefold()
            )
        allowed_emails.reset_tracking()

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

    @staticmethod
    def affiliation_record_to_affiliation(record) -> Affiliation:
        return Affiliation(
            team=record['team_id'],
            access=Access[record['access']] if record['access'] else Access.NONE,
            authorisation=Authorisation[record['authorisation']] if record['authorisation'] else Authorisation.NONE,
            heritable=record['heritable'] if record['heritable'] else False
        ) if record else None

    def record_to_account(self, record: Record) -> AccountStored:
        return AccountStored(
            user=self.user_record_to_user(record['user']),
            affiliations=[self.affiliation_record_to_affiliation(a) for a in record['affiliations']],
            allowed_emails=record['allowed_emails']
        ) if record else None

