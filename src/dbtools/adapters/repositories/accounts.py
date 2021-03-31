from abc import ABC, abstractmethod
from dbtools.custom_exceptions import ProtectedNodeError, NoResultFoundError
from dbtools.domain.model.accounts import UserRegistered, Team, Affiliation, AffiliationLevel, Affiliations, Account

from dbtools.adapters.repositories.trackable_wrappers import TrackableObject, TrackableDict
from dbtools.adapters.repositories.cypher import queries
from dbtools.adapters.repositories.async_neo4j import AsyncNeo4j

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Set, Optional, AsyncGenerator
    from asyncio import AbstractEventLoop
    from neo4j import Transaction, Record, Result


class AccountRepository(ABC):
    # todo will need to consider a "reset_tracking" function
    #  where changes must be committed over multiple transactions
    #  e.g. batching of submissions when a single transaction is too big
    #  not likely with accounts but very much so when tackling records

    def __init__(self):
        self.seen: Set[Account] = set()

    def _track(self, account: Account):
        account.user = TrackableObject(account.user)
        account.affiliations = TrackableDict(account.affiliations)
        self.seen.add(account)

    async def add(self, account: Account):
        await self._add(account)
        self._track(account)

    @abstractmethod
    async def _add(self, account: Account):
        raise NotImplementedError

    async def get(self, username: str) -> Account:
        account = await self._get(username)
        if account:
            self._track(account)
        return account

    @abstractmethod
    async def _get(self, username: str) -> Account:
        raise NotImplementedError

    async def get_by_email(self, email: str) -> Account:
        account = await self._get_by_email(email)
        if account:
            self._track(account)
        return account

    @abstractmethod
    async def _get_by_email(self, email: str) -> Account:
        raise NotImplementedError

    async def get_all(
            self,
            primary_only: bool = True,
            min_affiliation_level: AffiliationLevel = AffiliationLevel.USER,
            team_name: Optional[str] = None
    ) -> AsyncGenerator[Account]:
        if team_name:
            accounts = self._get_from_team(team_name)
            async for account in accounts:
                affiliation = account.affiliations.get_by_team_name(team_name)
                if primary_only and affiliation != account.affiliations.primary:
                    continue
                if affiliation.level >= min_affiliation_level:
                    self._track(account)
                    yield account
        else:
            accounts = self._get_all()
            async for account in accounts:
                if primary_only:
                    if account.affiliations[account.affiliations.primary] >= min_affiliation_level:
                        self._track(account)
                        yield account
                else:
                    if account.affiliations.max_level() >= min_affiliation_level:
                        self._track(account)
                        yield account

    @abstractmethod
    async def _get_all(self) -> AsyncGenerator[Account]:
        yield None  # required for typing
        raise NotImplementedError

    @abstractmethod
    async def _get_from_team(self, team_name) -> AsyncGenerator[Account]:
        yield None  # required for typing
        raise NotImplementedError

    async def remove(self, account: Account):
        if account.user.email_confirmed:
            raise ProtectedNodeError
        await self._remove(account)

    @abstractmethod
    async def _remove(self, account: Account):
        raise NotImplementedError

    async def update_seen(self):
        for account in self.seen:
            await self.update(account)

    async def update(self, account: Account):
        # note that some of the automated type checking for this function fails due to proxy wrappers
        # for example the dirty flag and the new and changed dicts aren't on the source models for User and Affiliations
        if account.user.dirty:
            await self._update_user(account.user)
            account.user.reset_tracking()
        if account.affiliations.dirty:
            for team, affiliation_level in account.affiliations.new:
                affiliation = Affiliation(
                    team=team,
                    level=affiliation_level,
                    primary=team == account.affiliations.primary
                )
                await self._add_affiliation(account.user, affiliation)
            for team, affiliation_level in account.affiliations.changed:
                affiliation = Affiliation(
                    team=team,
                    level=affiliation_level,
                    primary=team == account.affiliations.primary
                )
                await self._update_affiliation(account.user, affiliation)
            account.affiliations.reset_tracking()

    @abstractmethod
    async def _update_user(self, user: UserRegistered):
        raise NotImplementedError

    @abstractmethod
    async def _add_affiliation(self, user: UserRegistered, affiliation: Affiliation):
        raise NotImplementedError

    @abstractmethod
    async def _update_affiliation(self, user: UserRegistered, affiliation: Affiliation):
        raise NotImplementedError


class FakeAccountRepository(AccountRepository):

    def __init__(self):
        super().__init__()
        self._accounts = set()
        self.id_counter = 0

    async def _add(self, account: Account):
        self._accounts.add(account)
        self.id_counter += 1
        account.id = self.id_counter

    async def _get(self, username: str) -> Account:
        return next(a for a in self._accounts if a.user.username.casefold() == username.casefold())

    async def _get_all(self) -> AsyncGenerator[Account]:
        for account in self._accounts:
            yield account

    async def _get_from_team(self, team_name) -> AsyncGenerator[Account]:
        for account in self._accounts:
            try:
                account.affiliations.get_by_team_name()
                yield account
            except NoResultFoundError:
                continue

    async def _get_by_email(self, email: str) -> Account:
        return next(a for a in self._accounts if a.user.email == email)

    async def _remove(self, account: Account):
        self._accounts.remove(account)

    async def _update_user(self, user: UserRegistered):
        pass

    async def _add_affiliation(self, user: UserRegistered, affiliation: Affiliation):
        pass

    async def _update_affiliation(self, user: UserRegistered, affiliation: Affiliation):
        pass


class Neo4jAccountRepository(AccountRepository):

    def __init__(self, tx: Transaction, loop: AbstractEventLoop):
        super().__init__()
        self.neo4j = AsyncNeo4j(tx, loop)

    async def _add(self, account: Account):
        record: Record = await self.neo4j.single(
            queries['add_account'],
            username=account.user.username,
            username_lower=account.user.username_lower,
            fullname=account.user.fullname,
            password_hash=account.user.password_hash,
            email=account.user.email,
            team_name=account.affiliations.primary.name,
            affiliation_level=account.affiliations.max_level,
            confirmed=account.user.email_confirmed
        )
        account.user.id = record['user']['id']

    async def _get(self, username: str) -> Account:
        record: Record = await self.neo4j.single(
            queries['get_account'],
            username_lower=username.casefold()
        )
        return self.record_to_account(record) if record else None

    async def _get_all(self) -> AsyncGenerator[Account]:
        async for record in self.neo4j.records(
                queries['get_accounts']
        ):
            yield self.record_to_account(record)

    async def _get_from_team(self, team_name) -> AsyncGenerator[Account]:
        async for record in self.neo4j.records(
                queries['get_accounts_by_team'],
                team_name=team_name
        ):
            yield self.record_to_account(record)

    async def _get_by_email(self, email: str) -> Account:
        record: Record = await self.neo4j.single(
            queries['get_account_by_email'],
            email=email
        )
        return self.record_to_account(record) if record else None

    async def _remove(self, account: Account):
        await self.neo4j.run(
            queries['delete_unconfirmed_account'],
            email=account.user.email
        )

    async def _update_user(self, user: UserRegistered):
        await self.neo4j.run(
            queries('update_user'),
            id=user.id,
            username=user.username,
            username_lower=user.username_lower,
            fullname=user.fullname,
            password_hash=user.password_hash,
            email=user.email
        )

    async def _update_affiliation(self, user: UserRegistered, affiliation: Affiliation):
        await self.neo4j.run(
            queries('update_affiliation'),
            username_lower=user.username_lower,
            team_name=affiliation.team.name,
            level=affiliation.level.value
        )

    async def _add_affiliation(self, user: UserRegistered, affiliation: Affiliation):
        await self.neo4j.run(
            queries('add_affiliation'),
            username_lower=user.username_lower,
            team_name=affiliation.team.name
        )

    @staticmethod
    def record_to_account(record: Record) -> Account:
        user = UserRegistered(
            username=record['user']['username'],
            fullname=record['user']['fullname'],
            email=record['user']['email'],
            password_hash=record['user']['password_hash'],
            confirmed=record['user']['email_confirmed'],
            id_=record['user']['id']
        )
        affiliations = Affiliations([
            Affiliation(
                team=Team(name=team_name, fullname=team_fullname),
                level=AffiliationLevel(affiliation_level)
            ) for team_name, team_fullname, affiliation_level in record['affiliations']
        ])
        account = Account(user=user, affiliations=affiliations)
        return account
