from abc import ABC, abstractmethod
from src.breedgraph.custom_exceptions import ProtectedNodeError, IdentityExistsError, IllegalOperationError
from src.breedgraph.domain.model.accounts import (
    UserInput, UserStored,
    TeamInput, TeamStored,
    Access, Authorisation, Affiliation,
    AccountInput, AccountStored
)

from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked, TrackedList
from src.breedgraph.adapters.neo4j.cypher import queries

# for typing only
from typing import Set, Optional, AsyncGenerator, Union, List, ValuesView, Dict, TypedDict
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

    async def get(self, user_id: int) -> AccountStored:
        account = await self._get(user_id)
        if account is not None:
            self._track(account)
        return account

    @abstractmethod
    async def _get(self, user_id: int) -> AccountStored:
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
            teams: Optional[List[int|str|TeamInput|TeamStored]] = None,
            access_types: Optional[List[Access]] = None,
            authorisations: Optional[List[Authorisation]] = None
    ) -> AsyncGenerator[AccountStored, None]:

        accounts = self._get_all(
            teams=teams,
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
            teams: Optional[List[int|str|TeamInput|TeamStored]] = None,
            access_types: Optional[List[Access]] = None,
            authorisations: Optional[List[Authorisation]] = None
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

class FakeAccountRepository(BaseAccountRepository):

    def __init__(self):
        super().__init__()
        self._accounts = set()
        self.user_id_counter = 0
        self.team_id_counter = 0

    @property
    def orphan_teams(self):
        for account in self._accounts:
            for affiliation in account.affiliations:
                if affiliation.team.parent_id is None:
                    yield affiliation.team

    async def _create(self, account: AccountInput) -> AccountStored:
        self.user_id_counter += 1
        account.user = UserStored(
            id=self.user_id_counter,
            name=account.user.name,
            email=account.user.email,
            password_hash=account.user.password_hash
        )
        account = AccountStored(
            user = account.user,
            affiliations = [
                Affiliation(
                    access=Access.NONE,
                    authorisation=Authorisation.NONE,
                    team=t
                ) for t in self.orphan_teams
            ])

        self._accounts.add(account)
        return account

    async def _get(self, user_id: int) -> AccountStored:
        return next(a for a in self._accounts if a.user.id == user_id)

    def _get_all(
            self,
            teams: List[int|str|TeamInput|TeamStored] = None,
            access_types: Optional[List[Access]] = None,
            authorisations: Optional[List[Authorisation]] = None
    ) -> AsyncGenerator[AccountStored, None]:
        account: AccountStored
        for account in self._accounts:
            for affiliation in account.affiliations:
                if affiliation.is_matched(
                        access_types=access_types,
                        authorisations=authorisations,
                        teams=teams
                ):
                    yield account

    async def _get_by_email(self, email: str) -> AccountStored:
        return next(a for a in self._accounts if a.user.email == email)

    async def _get_by_name(self, name: str) -> AccountStored:
        return next(a for a in self._accounts if a.user.name == name)

    async def _remove(self, account: AccountStored):
        self._accounts.remove(account)

    async def _update(self, user: AccountStored):
        pass


class Neo4jAccountRepository(BaseAccountRepository):

    def __init__(self, tx: AsyncTransaction):
        logger.debug("init neo4j account repo")
        super().__init__()
        self.tx = tx

    async def _create(self, account: AccountInput) -> AccountStored:
        user = await self._create_user(account.user)
        return await self._get(user_id=user.id)

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

    async def _set_affiliation(self, user_id, affiliation: Affiliation) -> Affiliation:
        # Ensure team is created if needed
        if isinstance(affiliation.team, TeamInput):
            affiliation.team = await self._add_team(affiliation.team)

        # if none type just return
        if affiliation == Access.NONE:
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
            user_id=user_id,
            team_id=affiliation.team.id,
            authorisation=affiliation.authorisation.name,
            heritable=affiliation.heritable
        )
        return affiliation

    async def _remove_affiliation(self, user_id, affiliation: Affiliation) -> None:

        if isinstance(affiliation.team, TeamInput):
            raise TypeError(
                "TeamInput provided to remove_affiliations, "
                "this function should only be applied to stored affiliations"
            )

        elif isinstance(affiliation.team, TeamStored):
            if affiliation == Access.NONE:
                return

            if affiliation == Access.READ:
                query = queries['remove_reads']
            elif affiliation == Access.WRITE:
                query = queries['remove_writes']
            elif affiliation == Access.ADMIN:
                query = queries['remove_admins']
            else:
                raise TypeError("Unknown affiliation")

            await self.tx.run(query, user_id=user_id, team_id=affiliation.team.id)

        else:
            raise TypeError("Unrecognised team type")

    async def _update_affiliations(self, user_id, affiliations: List[Affiliation]):
        if not isinstance(affiliations, TrackedList):
            raise TypeError("Affiliations must be TrackedList for neo4j repository updates")

        if not affiliations.changed:
            return

            # Can't just iterate over added and removed as there might be changes to affiliations
        for i, affiliation in enumerate(affiliations):
            if affiliation.changed or affiliation in affiliations.added:
                stored_affiliation = await self._set_affiliation(user_id, affiliation)
                # update the team in the list as it may have been created
                affiliation.team = stored_affiliation.team
            elif affiliation in affiliations.removed:
                await self._remove_affiliation(user_id, affiliation)

        affiliations.reset_tracking()

    async def _add_team(self, team: TeamInput):
        # Name + parent_id must be unique for names to make any sense.
        # todo consider where to enforce this constraint
        logger.debug(f"Add team: {team}")

        if team.parent_id is not None:
            result: AsyncResult = await self.tx.run(
                queries['create_team_with_parent'],
                name=team.name,
                name_lower=team.name.casefold(),
                fullname=team.fullname,
                parent_id=team.parent_id
            )
        else:
            result: AsyncResult = await self.tx.run(
                queries['create_team'],
                name=team.name,
                name_lower=team.name.casefold(),
                fullname=team.fullname
            )

        record: "Record" = await result.single()
        return self.team_record_to_team(record)

    #async def _update_team(self, team: TeamStored):
    #    if team.parent_id is not None:
    #        result = await self.tx.run(
    #            queries['set_team_with_parent_id'],
    #            team_id=team.id,
    #            parent_id=team.parent_id,
    #            name=team.name,
    #            name_lower=team.name.casefold(),
    #            fullname=team.fullname
    #        )
    #    else:
    #        result = await self.tx.run(
    #            queries['set_team'],
    #            team_id=team.id,
    #            name=team.name,
    #            name_lower=team.name.casefold(),
    #            fullname=team.fullname
    #        )
    #    record = await result.single()
    #    return TeamStored(**record)

    async def _get(self, user_id: int) -> AccountStored:
        result: AsyncResult = await self.tx.run(
            queries['get_account'],
            user_id=user_id
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
            teams: List[int | TeamStored] = None,
            access_types: Optional[List[Access]] = None,
            authorisations: Optional[List[Authorisation]] = None
    ) -> AsyncGenerator[AccountStored, None]:
        if not authorisations:
            authorisations = [a.name for a in Authorisation]
        else:
            authorisations = [a.name for a in authorisations]

        if not access_types:
            access_types = [a.name for a in Access]
        else:
            access_types = [a.name for a in access_types]

        if access_types is None or Access.NONE in access_types:
            result = self.tx.run(
                queries['get_accounts'],
                access_types=access_types,
                authorisations=authorisations
            )
        elif teams:
            team_ids = [team.id if isinstance(team, TeamStored) else team for team in teams]
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
            queries['delete_unverified_user'],
            email_lower=account.user.email.casefold()
        )

    async def _update(self, account: AccountStored):
        await self._update_user(account.user)
        await self._update_affiliations(account.user.id, account.affiliations)
        await self._update_allowed_emails(account.user.id, account.allowed_emails)

    async def _update_user(self, user: UserStored):

        if not isinstance(user, Tracked):
            raise IllegalOperationError("User changes must be tracked for neo4j updates")

        if user.changed:
            await self.tx.run(
                queries['set_user'],
                id=user.id,
                name = user.name,
                name_lower=user.name.casefold(),
                fullname = user.fullname,
                email = user.email,
                email_lower = user.email.casefold(),
                email_verified = user.email_verified,
                password_hash = user.password_hash
            )
            user.reset_tracking()

    async def _update_allowed_emails(self, user_id: int, allowed_emails: List[str]):

        if not isinstance(allowed_emails, TrackedList):
            raise IllegalOperationError("Allowed emails must be tracked for neo4j updates")

        if not allowed_emails.changed:
            return

        # Then create/remove allowed_emails
        for email in allowed_emails.added:
            await self.tx.run(
                queries['add_email'],
                user_id=user_id,
                email = email,
                email_lower=email.casefold()
            )
        for email in allowed_emails.removed:
            await self.tx.run(
                queries['remove_email'],
                user_id=user_id,
                email_lower=email.casefold()
            )
        allowed_emails.reset_tracking()

    @staticmethod
    def team_record_to_team(record) -> TeamStored:
        if 'parent_id' in record:
            return TeamStored(
                name=record['name'],
                fullname=record['fullname'],
                id=record['id'],
                parent_id=record['parent_id']
            )
        else:
            return TeamStored(
                name=record['name'],
                fullname=record['fullname'],
                id=record['id'],
                parent_id=None
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

    def affiliation_record_to_affiliation(self, record) -> Affiliation:
        return Affiliation(
            access=Access[record['access']] if record['access'] else Access.NONE,
            authorisation=Authorisation[record['authorisation']] if record['authorisation'] else Authorisation.NONE,
            team=self.team_record_to_team(record['team'])
        ) if record else None

    def record_to_account(self, record: Record) -> AccountStored:
        return AccountStored(
            user=self.user_record_to_user(record['user']),
            affiliations=[self.affiliation_record_to_affiliation(a) for a in record['affiliations']],
            allowed_emails=record['allowed_emails']
        ) if record else None

