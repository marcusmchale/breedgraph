from abc import ABC, abstractmethod
from src.dbtools.custom_exceptions import ProtectedNodeError, NoResultFoundError
from src.dbtools.domain.model.accounts import (
    UserBase, UserInput, UserOutput, UserStored,
    TeamBase, TeamInput, TeamOutput, TeamStored,
    Affiliation, AffiliationLevel, Affiliations,
    AccountBase, AccountInput, AccountOutput, AccountStored
)

from src.dbtools.adapters.repositories.trackable_wrappers import TrackableObject, TrackableMapping
from src.dbtools.adapters.neo4j.cypher import queries

# for typing only
from typing import Set, Optional, AsyncGenerator, Union, List, ValuesView
from neo4j import Record, AsyncResult, AsyncTransaction


class BaseAccountRepository(ABC):
    # todo will need to consider a "reset_tracking" function
    #  where changes must be committed over multiple transactions
    #  e.g. batching of submissions when a single transaction is too big
    #  not likely with accounts but very much so when tackling records

    def __init__(self):
        self.seen: Set[AccountStored] = set()

    def _track(self, account: AccountStored):
        account.user = TrackableObject(account.user)
        account.affiliations = TrackableMapping(account.affiliations)
        self.seen.add(account)

    async def create(self, account: AccountInput):
        account: AccountStored = await self._create(account)
        self._track(account)
        return account

    @abstractmethod
    async def _create(self, account: AccountInput) -> AccountStored:
        raise NotImplementedError

    async def get(self, user_id: int) -> AccountStored:
        account = await self._get(user_id)
        if account:
            self._track(account)
        return account

    @abstractmethod
    async def _get(self, user_id: int) -> AccountStored:
        raise NotImplementedError

    async def get_by_email(self, email: str) -> AccountStored:
        account = await self._get_by_email(email)
        if account:
            self._track(account)
        return account

    @abstractmethod
    async def _get_by_email(self, email: str) -> AccountStored:
        raise NotImplementedError

    async def get_by_username(self, username: str) -> AccountStored:
        account = await self._get_by_username(username)
        if account:
            self._track(account)
        return account

    @abstractmethod
    async def _get_by_username(self, username: str) -> AccountStored:
        raise NotImplementedError

    async def get_accounts(
            self,
            primary_only: bool = True,
            min_affiliation_level: AffiliationLevel = AffiliationLevel.USER,
            team_name: Optional[str] = None
    ) -> AsyncGenerator[AccountStored, None]:
        if team_name:
            accounts = await self._get_by_team(team_name)
            async for account in accounts:
                if primary_only and account.affiliations.write_team != team_name:
                    continue
                if account.affiliations[team_name] >= min_affiliation_level:
                    self._track(account)
                    yield account
        else:
            accounts = await self._get_all()
            async for account in accounts:
                if primary_only and account.affiliations[account.affiliations.write_team] >= min_affiliation_level:
                    self._track(account)
                    yield account
                elif account.affiliations.max_level >= min_affiliation_level:
                    self._track(account)
                    yield account

    @abstractmethod
    async def _get_all(self) -> AsyncGenerator[AccountStored, None]:
        raise NotImplementedError

    @abstractmethod
    async def _get_by_team(self, team_name) -> AsyncGenerator[AccountStored, None]:
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

    async def _update(self, account: AccountStored):
        # note that some automated type checking for this function fails due to proxy wrappers
        # for example the dirty flag and the new and changed dicts aren't on the source models for User and Affiliations
        if account.user.dirty:
            await self._update_user(account.user)
            account.user.reset_tracking()
        if account.affiliations.dirty:
            for key, value in account.affiliations.dirty:
                team = account.affiliations.get_team(key)
                level = value
                affiliation = Affiliation(
                    team=team,
                    level=level,
                    primary=team == account.affiliations.write_team  # write key does not change
                )
                await self._set_affiliation(account.user, affiliation)
            account.affiliations.reset_tracking()

    @abstractmethod
    async def _update_user(self, user: UserStored):
        raise NotImplementedError

    @abstractmethod
    async def _set_affiliation(self, user: UserStored, affiliation: Affiliation):
        raise NotImplementedError


class FakeAccountRepository(BaseAccountRepository):

    def __init__(self):
        super().__init__()
        self._accounts = set()
        self.team_id_counter = 0
        self.user_id_counter = 0

    async def _create(self, account: AccountInput) -> AccountStored:

        teams: "ValuesView[TeamBase]" = account.affiliations.all_teams
        for team in teams:
            if not team.id:
                self.team_id_counter += 1
                team.id = self.team_id_counter
        self.user_id_counter += 1
        account.user.id = self.user_id_counter
        account = AccountStored(user=account.user, affiliations=account.affiliations)
        self._accounts.add(account)
        return account

    async def _get(self, user_id: int) -> AccountStored:
        return next(a for a in self._accounts if a.user.id == user_id)

    async def _get_all(self) -> AsyncGenerator[AccountStored, None]:
        for account in self._accounts:
            yield account

    async def _get_by_team(self, team_name) -> AsyncGenerator[AccountStored, None]:
        for account in self._accounts:
            try:
                if team_name in account.affiliations:
                    yield account
            except NoResultFoundError:
                continue

    async def _get_by_email(self, email: str) -> AccountStored:
        return next(a for a in self._accounts if a.user.email == email)

    async def _get_by_username(self, username: str) -> AccountStored:
        return next(a for a in self._accounts if a.user.name.casefold() == username.casefold())

    async def _remove(self, account: AccountStored):
        self._accounts.remove(account)

    async def _update_user(self, user: UserStored):
        pass

    async def _set_affiliation(self, user: UserStored, affiliation: Affiliation):
        pass


class Neo4jAccountRepository(BaseAccountRepository):

    def __init__(self, tx: AsyncTransaction):
        super().__init__()
        self.tx = tx

    async def _create(self, account: AccountInput) -> AccountStored:
        await self._add_user(account)
        await self._set_affiliations(account)
        return AccountStored(user=account.user, affiliations=account.affiliations)

    async def _add_user(self, account: AccountInput):
        result = await self.tx.run(
            queries['create_user'],
            **dict(account.user)
        )
        record: Record = await result.single()
        account.user = UserStored(**record['user'])

    async def _set_affiliations(self, account):
        await self._add_teams(account)
        for team, level in account.affiliations:
            await self.tx.run(
                queries['set_affiliation'],
                user_id=account.user.id,
                team_id=team.id,
                level=level.value
            )

    async def _add_teams(self, account):
        for team in account.affiliations.all_teams:
            if not await self.tx.run(queries['get_team'], name_lower=team.name_lower):
                result: AsyncResult = await self.tx.run(
                    queries['create_team'],
                    **dict(team)
                )
                record = await result.single()
                account.affiliations[TeamStored(**record['key'])] = account.affiliations.pop(team)

    async def _get(self, user_id: int) -> AccountStored:
        result: AsyncResult = await self.tx.run(
            queries['get_account'],
            user_id=user_id
        )
        record: "Record" = await result.single()
        return self.record_to_account(record) if record else None

    async def _get_all(self) -> AsyncGenerator[AccountStored, None]:
        async for record in await self.tx.run(
                queries['get_accounts']
        ):
            yield self.record_to_account(record)

    async def _get_by_team(self, team_name) -> AsyncGenerator[AccountStored, None]:
        async for record in await self.tx.run(
                queries['get_accounts_by_team'],
                team_name=team_name
        ):
            yield self.record_to_account(record)

    async def _get_by_email(self, email: str) -> AccountStored:
        result: AsyncResult = await self.tx.run(
            queries['get_account_by_email'],
            email=email
        )
        record: Record = await result.single()
        return self.record_to_account(record) if record else None

    async def _get_by_username(self, username: str) -> AccountStored:
        result: AsyncResult = await self.tx.run(
            queries['get_account_by_username'],
            username_lower=username.casefold()
        )
        record: Record = await result.single()
        return self.record_to_account(record) if record else None

    async def _remove(self, account: AccountStored):
        await self.tx.run(
            queries['delete_unverified_user'],
            email=account.user.email
        )
        await self.tx.run(
            queries['delete_unaffiliated_teams']
        )

    async def _update_user(self, user: UserStored):
        await self.tx.run(
            queries('set_user'),
            **dict(user)
        )

    async def _set_affiliation(self, user: UserStored, affiliation: Affiliation):
        await self.tx.run(
            queries('set_affiliation'),
            username_lower=user.name_lower,
            team_name=affiliation.team.name,
            level=affiliation.level
        )

    @staticmethod
    def record_to_account(record: Record) -> AccountStored:
        user = UserStored(**record['user'])
        affiliations = Affiliations([
            Affiliation(
                team=TeamStored(name=team_name, fullname=team_fullname, id=team_id),
                level=AffiliationLevel(affiliation_level)
            ) for team_name, team_fullname, team_id, affiliation_level in record['affiliations']
        ])
        return AccountStored(user=user, affiliations=affiliations)
