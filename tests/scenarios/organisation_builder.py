from src.breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory
from tests.utilities.inputs import UserInputGenerator

from src.breedgraph.domain.model.organisations import (
    TeamInput, TeamStored,
    Access, Affiliation, Authorisation
)


class OrganisationBuilder:
    user_input_generator = UserInputGenerator()

    def __init__(self, uow_factory: AbstractUnitOfWorkFactory):
        self.uow_factory = uow_factory

    @classmethod
    def team_input(cls) -> TeamInput:
        team_name = cls.user_input_generator.new_user_input().get('team_name')
        return TeamInput(name=team_name)

    async def organisation(self, user_id: int) -> int:
        async with self.uow_factory.get_uow(user_id=user_id) as uow:
            organisation = await uow.repositories.organisations.create(self.team_input())
            await uow.commit()
            return organisation.root.id

    async def authorise_access(self, user_id: int, team_id: int, access: Access, heritable = None ):
        async with self.uow_factory.get_uow(redacted=False, user_id=user_id) as uow:
            organisation = await uow.repositories.organisations.get(team_id=team_id)
            if not organisation:
                raise ValueError("Organisation not found for team")
            team = organisation.get_team(team_id)
            if not isinstance(team, TeamStored):
                raise ValueError("Team not stored in organisation")
            if user_id in team.affiliations.get_by_access(access):
                current_affiliation = team.affiliations.get_by_access(access).get(user_id)
                current_affiliation.authorisation = Authorisation.AUTHORISED
                if heritable is not None:
                    current_affiliation.heritable = heritable
            else:
                team.affiliations.set_by_access(
                    access,
                    user_id,
                    Affiliation(authorisation=Authorisation.AUTHORISED, heritable = heritable or False)
                )
            await uow.commit()

