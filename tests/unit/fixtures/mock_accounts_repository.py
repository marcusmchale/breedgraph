from src.breedgraph.service_layer.repositories import BaseRepository
from src.breedgraph.domain.model.accounts import (
    UserBase, UserStored,
    AccountInput, AccountStored
)

from src.breedgraph.service_layer.infrastructure.notifications import AbstractNotifications
from src.breedgraph.adapters.aiosmtp.notifications import Email

from typing import List, AsyncGenerator

TAggregateInput = AccountInput
TAggregate = AccountStored

class FakeAccountRepository(BaseRepository):

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
            fullname=account.user.fullname,
            email=account.user.email,
            password_hash=account.user.password_hash
        )
        account = AccountStored(user = account.user)
        self._accounts.add(account)
        return account

    async def _get(self, user_id: int) -> AccountStored:
        return next(a for a in self._accounts if a.user.id == user_id)

    #def _get_all(
    #        self,
    #        team_ids: None|List[int] = None,
    #        access_types: None|List[Access] = None,
    #        authorisations: None|List[Authorisation] = None
    #) -> AsyncGenerator[AccountStored, None]:
    #    if any([team_ids, access_types, authorisations]):
    #        raise NotImplementedError("Filters by affiliation are not implemented here yet")
    #    account: AccountStored
    #    for account in self._accounts:
    #        yield account

    async def _get_by_email(self, email: str) -> AccountStored:
        return next(a for a in self._accounts if a.user.email == email)

    async def _get_by_name(self, name: str) -> AccountStored:
        return next(a for a in self._accounts if a.user.name == name)

    async def _remove(self, account: AccountStored):
        self._accounts.remove(account)

    async def _update(self, user: AccountStored):
        pass


