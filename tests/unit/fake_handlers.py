from src.breedgraph.adapters.repositories.accounts import BaseAccountRepository
from src.breedgraph.domain.model.accounts import (
    UserBase, UserStored,
    Affiliation,
    Access, Authorisation,
    AccountInput, AccountStored
)

from src.breedgraph.adapters.notifications.notifications import AbstractNotifications
from src.breedgraph.adapters.notifications.emails import Email


from typing import List, AsyncGenerator

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
            fullname=account.user.fullname,
            email=account.user.email,
            password_hash=account.user.password_hash
        )
        account = AccountStored(
            user = account.user,
            affiliations = [
                Affiliation(
                    user=account.user.to_output(),
                    access=Access.NONE,
                    authorisation=Authorisation.NONE,
                    team=t.to_output()
                ) for t in self.orphan_teams
            ])

        self._accounts.add(account)
        return account

    async def _get(self, user_id: int) -> AccountStored:
        return next(a for a in self._accounts if a.user.id == user_id)

    def _get_all(
            self,
            team_ids: None|List[int] = None,
            access_types: None|List[Access] = None,
            authorisations: None|List[Authorisation] = None
    ) -> AsyncGenerator[AccountStored, None]:
        account: AccountStored
        for account in self._accounts:
            for affiliation in account.affiliations:
                if affiliation.is_matched(
                    user_ids=[account.user.id],
                    teams=team_ids,
                    access_types=access_types,
                    authorisations=authorisations,
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


class FakeNotifications(AbstractNotifications):

    @staticmethod
    async def send_to_unregistered(recipients: List[str], message: Email):
        pass

    @staticmethod
    async def send(recipients: List[UserBase], message: Email):
        pass