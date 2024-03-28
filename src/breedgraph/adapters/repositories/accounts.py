from abc import ABC, abstractmethod
from src.breedgraph.custom_exceptions import ProtectedNodeError, IdentityExistsError, IllegalOperationError
from src.breedgraph.domain.model.accounts import (
    UserInput, UserStored,
    TeamInput, TeamStored,
    AccountInput, AccountStored,
    Email, Name,
    AffiliationType, AffiliationsHolder, Affiliation, Authorisation
)

from src.breedgraph.adapters.repositories.trackable_wrappers import TrackedObject, TrackedList
from src.breedgraph.adapters.neo4j.cypher import queries

# for typing only
from typing import Set, Optional, AsyncGenerator, Union, List, ValuesView, Dict, TypedDict
from neo4j import Record, AsyncResult, AsyncTransaction

import logging


logger = logging.getLogger(__name__)

class BaseAccountRepository(ABC):
    # todo will need to consider a "reset_tracking" function
    #  where changes must be committed over multiple transactions
    #  e.g. batching of submissions when a single transaction is too big
    #  not likely with accounts but very much so when tackling records

    def __init__(self):
        self.seen: Set[AccountStored] = set()

    def _track(self, account: AccountStored):
        account.user = TrackedObject(account.user)
        account.affiliations.affiliations = TrackedList(account.affiliations.affiliations)
        account.allowed_emails = TrackedList(account.allowed_emails)
        self.seen.add(account)

    async def create(self, account: AccountInput):
        logger.debug("Create account")
        account: AccountStored = await self._create(account)
        self._track(account)
        return account

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

    async def get_by_email(self, email:Email) -> AccountStored:
        account = await self._get_by_email(email)
        if account:
            self._track(account)
        return account

    @abstractmethod
    async def _get_by_email(self, email: Email) -> AccountStored:
        raise NotImplementedError

    async def get_by_name(self, name: str) -> AccountStored:
        account = await self._get_by_name(name.casefold())
        if account:
            self._track(account)
        return account

    @abstractmethod
    async def _get_by_name(self, name: str) -> AccountStored:
        raise NotImplementedError


    async def get_by_affiliation(
            self,
            teams: List[int|TeamStored] = None,
            affiliation_types: Optional[List[AffiliationType]] = None,
            authorisations: Optional[List[Authorisation]] = None
    ) -> AsyncGenerator[AccountStored, None]:
        accounts = self._get_by_affiliation(
            teams=teams,
            affiliation_types=affiliation_types,
            authorisations=authorisations
        )
        # typing issue here seems to be a bug in pycharm https://youtrack.jetbrains.com/issue/PY-40458
        async for account in accounts:
            self._track(account)
            logger.debug(account)
            yield account


    @abstractmethod
    def _get_by_affiliation(
            self,
            teams: List[int|TeamStored] = None,
            affiliation_types: Optional[List[AffiliationType]] = None,
            authorisations: Optional[List[Authorisation]] = None
    ) -> AsyncGenerator[AccountStored, None]:
        raise NotImplementedError

    async def get_all(self, affiliation_types: Optional[List[AffiliationType]] = None) -> AsyncGenerator[AccountStored, None]:
        if affiliation_types is None:
            affiliation_types = [e for e in AffiliationType]

        accounts = self._get_all(affiliation_types)
        async for account in accounts:
            self._track(account)
            logger.debug(account)
            yield account

    @abstractmethod
    def _get_all(self, affiliation_types: List[AffiliationType]) -> AsyncGenerator[AccountStored, None]:
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

    async def _create(self, account: AccountInput) -> AccountStored:
        self.user_id_counter += 1
        user = UserStored(
            id=self.user_id_counter,
            name= account.user.name,
            email=account.user.email,
            password_hash=account.user.password_hash
        )
        #todo these account.reads_from etc should be coerced into TeamStored objects if included
        account = AccountStored(user=user, affiliations=account.affiliations)
        self._accounts.add(account)
        return account

    async def _get(self, user_id: int) -> AccountStored:
        return next(a for a in self._accounts if a.user.id == user_id)

    async def _get_all(self, affiliation_types: List[AffiliationType]) -> AsyncGenerator[AccountStored, None]:
        account: AccountStored
        for account in self._accounts:
            if account.affiliations.get(affiliation_types=affiliation_types):
                yield account

    def _get_by_affiliation(
            self,
            teams: List[int|TeamStored] = None,
            affiliation_types: Optional[List[AffiliationType]] = None,
            authorisations: Optional[List[Authorisation]] = None
    ) -> AsyncGenerator[AccountStored, None]:
        account: AccountStored
        for account in self._accounts:
            if account.affiliations.get(teams=teams, affiliation_types=affiliation_types, authorisations=authorisations):
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
        result = await self.tx.run(
            queries['create_user'],
            name = account.user.name.display,
            name_lower = account.user.name.lower,
            fullname = account.user.name.full,
            password_hash = account.user.password_hash,
            email = account.user.email.address,
            email_lower = account.user.email.lower,
            email_verified = account.user.email.verified
        )
        record: Record = await result.single()
        return self.record_to_account(record)

    async def _update_teams(
            self,
            affiliations: TrackedList[Affiliation]
    ) -> None:
        for i, affiliation in enumerate(affiliations):  # update any remaining teams
            if isinstance(affiliation.team, TeamInput):
                affiliation.team = await self._add_team(affiliation.team)
            elif isinstance(affiliation.team, int):
                affiliation.team = await self._get_team(affiliation.team)
            elif isinstance(affiliation.team, TeamStored):
                if isinstance(affiliation, TrackedObject):
                    if affiliation.changed:
                        affiliation.team = await self._update_team(affiliation.team)
                else:
                    raise ValueError("This tracked list item should have been tracked")

    async def _add_team(self, team: TeamInput):
        # todo think about where logic for asserting team name uniqueness should go,
        #  for user we handled this at the service layer (command handler)
        #  this seems appropriate there as there is a single user per account and vice-versa,
        #  but for teams this isn't the case and it seems like it may be better handled..
        #  .. in the repository that is aware of all accounts?

        # TODO basically this escapes the bounds of the Account aggregate, we are sharing teams across aggregates...
        # TODO does a team even need to have a unique combination of name and parent at all?

        # maybe not a big issue, basically a value (unless creating a new one and need to ensure unique)
        logger.debug(f"Add team: {team}")

        if await self._get_team_by_name(team.name_lower, team.parent_id) is not None:
            raise IdentityExistsError(f"Team exists: (name: {team.name_lower}, parent_id {team.parent_id})")

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
        return TeamStored(**record)

    async def _get_team(self, team_id: int):
        query = queries['get_team']
        result = await self.tx.run(query, team_id=team_id)
        record = await result.single()
        if record is not None:
            return TeamStored(**record)

    async def _get_team_by_name(self, name_lower: str, parent_id: Optional[int] = None):
        if parent_id is None:
            result = await self.tx.run(
                queries['get_team_without_parent_by_name'],
                name_lower = name_lower
            )
        else:
            result = await self.tx.run(
                queries['get_team_with_parent_by_name'],
                name_lower = name_lower,
                parent_id = parent_id
            )
        record = await result.single()
        if record is not None:
            return TeamStored(**record)

    async def _update_team(self, team: TeamStored):
        if team.parent_id is not None:
            result = await self.tx.run(
                queries['set_team_with_parent_id'],
                team_id=team.id,
                parent_id=team.parent_id,
                name=team.name,
                name_lower=team.name_lower,
                fullname=team.fullname
            )
        else:
            result = await self.tx.run(
                queries['set_team'],
                team_id=team.id,
                name=team.name,
                name_lower=team.name_lower,
                fullname=team.fullname
            )
        record = await result.single()
        return TeamStored(**record)

    async def _get(self, user_id: int) -> AccountStored:
        result: AsyncResult = await self.tx.run(
            queries['get_account'],
            user_id=user_id
        )
        record: "Record" = await result.single()
        return self.record_to_account(record) if record else None

    async def _get_by_email(self, email: Email) -> AccountStored:
        result: AsyncResult = await self.tx.run(
            queries['get_account_by_email'],
            email_lower=email.address_lower
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

    async def _get_all(self, affiliation_types: List[AffiliationType]) -> AsyncGenerator[AccountStored, None]:
        if affiliation_types:
            result = self.tx.run(
                query = queries['get_accounts_by_affiliation_type'],
                affiliation_types=[a.name for a in affiliation_types]
            )
        else:
            result = self.tx.run(query = queries['get_accounts'])
        async for record in await result:
            yield self.record_to_account(record)
    async def _get_by_affiliation(
            self,
            teams: List[int|TeamStored] = None,
            affiliation_types: Optional[List[AffiliationType]] = None,
            authorisations: Optional[List[Authorisation]] = None
    ) -> AsyncGenerator[AccountStored, None]:
        if not affiliation_types:
            affiliation_types = [a for a in AffiliationType]
        if not authorisations:
            authorisations = [a for a in Authorisation]
        if teams:
            team_ids = [team.id if isinstance(team, TeamStored) else team for team in teams]
            result = self.tx.run(
                queries['get_accounts_by_teams'],
                team_ids=team_ids,
                affiliation_types=affiliation_types,
                authorisations=authorisations
            )
        else:
            result = self.tx.run(
                queries['get_accounts_by_affiliation'],
                affiliation_types=affiliation_types,
                authorisations=authorisations
            )
        async for record in await result:
            yield self.record_to_account(record)

    async def _remove(self, account: AccountStored):
        await self.tx.run(
            queries['delete_unverified_user'],
            email_lower=account.user.email_lower
        )

    async def _update(self, account: AccountStored):
        await self._update_user(account.user)
        await self._update_affiliations(account.user.id, account.affiliations.affiliations)
        await self._update_allowed_emails(account.user.id, account.allowed_emails)

    async def _update_user(self, user: UserStored):

        if not isinstance(user, TrackedObject):
            raise IllegalOperationError("User changes must be tracked for neo4j updates")

        if user.changed:
            await self.tx.run(
                queries['set_user'],
                id=user.id,
                name = user.name.display,
                name_lower=user.name.lower,
                fullname = user.name.full,
                email = user.email.address,
                email_lower = user.email.lower,
                email_verified = user.email.verified,
                password_hash = user.password_hash
            )
            user.reset_tracking()

    async def _update_affiliations(self, user_id: int, affiliations: TrackedList[Affiliation]):
        if not affiliations.changed:
            return

        # first ensure the teams list is all stored
        await self._update_teams(affiliations)

        # Then create/remove affiliations
        for affiliation in affiliations.added:
            if affiliation.type == AffiliationType.READ:
                await self.tx.run(
                    queries['add_reads'],
                    user_id=user_id,
                    team_id=affiliation.team.id,
                    authorisation=affiliation.authorisation.name
                )

            elif affiliation == AffiliationType.WRITE:
                await self.tx.run(queries['add_writes'], user_id=user_id, team_id=team.id)
            elif affiliation == AffiliationType.ADMIN:
                await self.tx.run(queries['add_admins'], user_id=user_id, team_id=team.id)
        for team in teams.removed:
            if affiliation == AffiliationType.READ:
                await self.tx.run(queries['remove_reads'], user_id=user_id, team_id=team.id)
            elif affiliation == AffiliationType.WRITE:
                await self.tx.run(queries['remove_writes'], user_id=user_id, team_id=team.id)
            elif affiliation == AffiliationType.ADMIN:
                await self.tx.run(queries['remove_admins'], user_id=user_id, team_id=team.id)

        teams.reset_tracking()

    async def _update_allowed_emails(self, user_id: int, allowed_emails: TrackedList[Email]):

        if not isinstance(allowed_emails, TrackedList):
            raise IllegalOperationError("Allowed emails must be tracked for neo4j updates")

        if not allowed_emails.changed:
            return

        # Then create/remove allowed_emails
        for email in allowed_emails.added:
            await self.tx.run(
                queries['add_email'],
                user_id=user_id,
                address = email.address,
                address_lower=email.address_lower
            )
        for email in allowed_emails.removed:
            await self.tx.run(
                queries['remove_email'],
                user_id=user_id,
                address_lower=email.address_lower
            )
        allowed_emails.reset_tracking()

    @staticmethod
    def record_to_account(record: Record) -> AccountStored:

        def team_record_to_team(team_record):
            return TeamStored(
                name=team_record['team']['name'],
                fullname=team_record['team']['fullname'],
                id=team_record['team']['id'],
                parent_id=team_record['parent']['id'] if team_record['parent'] else None
            )

        return AccountStored(
            user = UserStored(**record['user']),
            reads_from = {team_record_to_team(t) for t in record['reads_from'] if t['team']},
            writes_for = {team_record_to_team(t) for t in record['writes_for'] if t['team']},
            admins_for={team_record_to_team(t) for t in record['admins_for'] if t['team']},
            allowed_emails={Email(**e) for e in record['allowed_emails']}
        )





