from breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory

from breedgraph.domain.model import Access


class AuthorisationManager:

    def __init__(self, uow_factory: AbstractUnitOfWorkFactory):
        self.uow_factory = uow_factory

    async def authorise_affiliation(self, agent_id: int, user_id: int, team_id: int, access: Access, heritable: bool = False):
        async with self.uow_factory.get_uow(user_id=agent_id) as uow:
            team_tree = await uow.repositories.team_trees.get(team_id = team_id)
            assert team_tree
            team_tree.request_affiliation(
                agent_id=user_id,
                user_id=user_id,
                team_id=team_id,
                access=access
            )
            team_tree.authorise_affiliation(
                agent_id=agent_id,
                user_id=user_id,
                team_id=team_id,
                access=access,
                heritable=heritable
            )
            await uow.commit()