from src.breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory

from src.breedgraph.domain.model.organisations import Access

class AuthorisationManager:

    def __init__(self, uow_factory: AbstractUnitOfWorkFactory):
        self.uow_factory = uow_factory

    async def authorise_affiliation(self, agent_id: int, user_id: int, team_id: int, access: Access, heritable: bool = False):
        async with self.uow_factory.get_uow(user_id=agent_id) as uow:
            organisation = await uow.repositories.organisations.get(team_id = team_id)
            assert organisation
            organisation.request_affiliation(
                agent_id=user_id,
                user_id=user_id,
                team_id=team_id,
                access=access
            )
            organisation.authorise_affiliation(
                agent_id=agent_id,
                user_id=user_id,
                team_id=team_id,
                access=access,
                heritable=heritable
            )
            await uow.commit()