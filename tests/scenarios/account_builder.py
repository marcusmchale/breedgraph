from breedgraph.domain.model import OntologyRole
from breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory
from tests.utilities.inputs import UserInputGenerator

from breedgraph.domain.model.accounts import UserInput, AccountInput
from breedgraph.domain.model.organisations import Access

from .organisation_builder import OrganisationBuilder

from typing import Dict

class AccountBuilder:
    user_input_generator = UserInputGenerator()

    def __init__(self, uow_factory: AbstractUnitOfWorkFactory):
        self.uow_factory = uow_factory

    @classmethod
    def account_input(cls, ontology_role=OntologyRole.CONTRIBUTOR) -> AccountInput:
        user_input = cls.user_input_generator.new_user_input()
        user = UserInput(
            name=user_input['name'],
            fullname=user_input['name'],
            email=user_input['email'],
            password_hash=user_input['password_hash'],
            ontology_role=ontology_role
        )
        return AccountInput(user=user)

    async def account(self, ontology_role: OntologyRole = OntologyRole.CONTRIBUTOR) -> int:
        account_input = self.account_input(ontology_role=ontology_role)
        async with self.uow_factory.get_uow() as uow:
            account = await uow.repositories.accounts.create(account_input)
            await uow.commit()
            return account.user.id

    async def account_with_affiliations(self, ontology_role: OntologyRole = OntologyRole.CONTRIBUTOR) -> Dict[str, int]:
        user_id = await self.account(ontology_role=ontology_role)
        organisation_builder = OrganisationBuilder(uow_factory=self.uow_factory)
        team_id = await organisation_builder.organisation(user_id=user_id)
        for a in Access:
            await organisation_builder.authorise_access(user_id=user_id, team_id=team_id, access=a)
        return {
            'user_id': user_id,
            'team_id': team_id
        }
