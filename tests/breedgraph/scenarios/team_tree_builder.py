from breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory
from tests.breedgraph.utilities.inputs import UserInputGenerator

from breedgraph.domain.model.team_trees import (
    TeamInput, TeamStored,
    Affiliation, Authorisation
)
from breedgraph.domain.model import Access


class TeamTreeBuilder:
    user_input_generator = UserInputGenerator()

    def __init__(self, uow_factory: AbstractUnitOfWorkFactory):
        self.uow_factory = uow_factory

    @classmethod
    def team_input(cls) -> TeamInput:
        team_name = cls.user_input_generator.new_user_input().get('team_name')
        return TeamInput(name=team_name)

    async def team_tree(self, user_id: int) -> int:
        async with self.uow_factory.get_uow(user_id=user_id) as uow:
            team_tree = await uow.repositories.team_trees.create(self.team_input())
            await uow.commit()
            return team_tree.root.id

    async def authorise_access(self, user_id: int, team_id: int, access: Access, heritable = None ):
        async with self.uow_factory.get_uow(user_id=user_id) as uow:
            team_tree = await uow.repositories.team_trees.get(team_id=team_id)
            if not team_tree:
                raise ValueError("TeamTree not found for team")
            team = team_tree.get_team(team_id)
            if not isinstance(team, TeamStored):
                raise ValueError("Team not stored in team tree")
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

