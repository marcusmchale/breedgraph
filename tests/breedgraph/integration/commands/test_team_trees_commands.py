import pytest

from breedgraph.custom_exceptions import ProtectedNodeError
from breedgraph.domain.commands.accounts import SetWriteTeam
from breedgraph import config
from breedgraph.custom_exceptions import IllegalOperationError, UnauthorisedOperationError
from breedgraph.domain.commands.team_trees import CreateTeam, DeleteTeam, DeclareLegalEntity, LegalEntity, WithdrawLegalEntity
from breedgraph.domain.model.control_transfers import ControlledEntity
from breedgraph.domain.model.controls import Access, ControlledModelLabel

from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.team_tree_builder import TeamTreeBuilder
from tests.breedgraph.scenarios.program_builder import ProgramBuilder
from tests.breedgraph.scenarios.person_builder import PersonBuilder


async def child_team(bus, uow_factory, user_id: int, parent_id: int) -> int:
    name = TeamTreeBuilder.team_input().name
    await bus.handle(CreateTeam(agent_id=user_id, name=name, parent=parent_id))
    async with uow_factory.get_uow(user_id=user_id) as uow:
        team_tree = await uow.repositories.team_trees.get(team_id=parent_id)
        [team_id] = [team.id for team in team_tree.teams if team.name == name]
    team_tree_builder = TeamTreeBuilder(uow_factory)
    for access in Access:
        await team_tree_builder.authorise_access(user_id=user_id, team_id=team_id, access=access)
    return team_id


async def create_program(uow_factory, user_id: int, team_id: int) -> ControlledEntity:
    async with uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
        program = await uow.repositories.programs.create(ProgramBuilder.program_input())
        await uow.commit()
    return ControlledEntity(label=ControlledModelLabel.PROGRAM, id=program.id)


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_team_that_controls_entities_is_refused(bus, uow_factory, isolated_state):
    account = await AccountBuilder(uow_factory).account_with_affiliations()
    user_id = account['user_id']
    team_id = await child_team(bus, uow_factory, user_id, account['team_id'])
    await create_program(uow_factory, user_id, team_id)

    with pytest.raises(ProtectedNodeError, match="controls entities"):
        await bus.handle(DeleteTeam(agent_id=user_id, team_id=team_id))

    async with uow_factory.get_uow(user_id=user_id) as uow:
        team_tree = await uow.repositories.team_trees.get(team_id=account['team_id'])
        assert team_id in [team.id for team in team_tree.teams]


@pytest.mark.asyncio(loop_scope="session")
async def test_deleted_team_keeps_control_history(bus, uow_factory, isolated_state):
    account = await AccountBuilder(uow_factory).account_with_affiliations()
    user_id = account['user_id']
    root_id = account['team_id']
    team_id = await child_team(bus, uow_factory, user_id, root_id)
    program = await create_program(uow_factory, user_id, team_id)
    await bus.handle(SetWriteTeam(user_id=user_id, team_id=team_id))

    # Move control to the root team, then delete the child team
    async with uow_factory.get_uow(user_id=user_id) as uow:
        await uow.controls.offer_transfer(
            entities=[program], from_teams={team_id}, recipient_team=root_id, to_teams={root_id}
        )
        await uow.commit()
    await bus.handle(DeleteTeam(agent_id=user_id, team_id=team_id))

    async with uow_factory.get_uow(user_id=user_id) as uow:
        # The team is no longer part of the team tree or the user's access
        team_tree = await uow.repositories.team_trees.get(team_id=root_id)
        assert team_id not in [team.id for team in team_tree.teams]
        assert await uow.repositories.team_trees.get(team_id=team_id) is None
        assert all(team_id not in teams for teams in uow.controls.access_teams.values())

        # Controls of the program are unaffected
        controller = await uow.controls.get_controller(program.label, program.id)
        assert controller.teams == {root_id}

        # The deleted team keeps its control history and records its parent
        result = await uow.tx.run(
            "MATCH (team:DeletedTeam {id: $team_id}) "
            "OPTIONAL MATCH (team)-[:CONTROLS]->(:TeamPrograms)-[:CONTROLS]->(control:Control)"
            "-[:CONTROLS]->(:Program {id: $program_id}) "
            "WITH team, control ORDER BY control.sequence "
            "RETURN team.parent AS parent, team.deleted_by AS deleted_by, "
            "team.deleted_at IS NOT NULL AS deleted, collect(control.ended) AS ended",
            team_id=team_id,
            program_id=program.id
        )
        record = await result.single()
        assert record['parent'] == root_id
        assert record['deleted_by'] == user_id
        assert record['deleted']
        assert record['ended'] == [True]

        account_stored = await uow.repositories.accounts.get(user_id=user_id)
        assert account_stored.user.default_write_team is None


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_team_cancels_pending_transfers(bus, uow_factory, isolated_state):
    account = await AccountBuilder(uow_factory).account_with_affiliations()
    user_id = account['user_id']
    root_id = account['team_id']
    team_id = await child_team(bus, uow_factory, user_id, root_id)

    shared_program = await create_program(uow_factory, user_id, team_id)
    root_program = await create_program(uow_factory, user_id, root_id)
    async with uow_factory.get_uow(user_id=user_id) as uow:
        # Share control of the first program with the root team, then offer it from the child team
        await uow.controls.offer_transfer(
            entities=[shared_program], from_teams={team_id}, recipient_team=root_id,
            keep_from_teams=True, to_teams={root_id}
        )
        offered_from = await uow.controls.offer_transfer(
            entities=[shared_program], from_teams={team_id}, recipient_team=root_id
        )
        # Offer the second program to the child team
        offered_to = await uow.controls.offer_transfer(
            entities=[root_program], from_teams={root_id}, recipient_team=team_id
        )
        # The child team gives up its control, so it can be deleted
        await uow.controls.renounce_controls(entities=[shared_program], team_ids={team_id})
        await uow.commit()

    await bus.handle(DeleteTeam(agent_id=user_id, team_id=team_id))

    async with uow_factory.get_uow(user_id=user_id) as uow:
        for transfer_id in (offered_from.id, offered_to.id):
            transfer = await uow.controls.get_transfer(transfer_id)
            assert transfer.status.value == 'CANCELLED'
            assert transfer.cancelled_by == user_id
            assert transfer.cancelled_at is not None


@pytest.fixture
def terms_version(monkeypatch) -> str:
    monkeypatch.setattr(config, 'DATA_PROCESSING_TERMS_VERSION', 'test-terms-1')
    return 'test-terms-1'


def legal_entity(terms_version: str, legal_name: str = 'Test University') -> LegalEntity:
    return LegalEntity(
        legal_name=legal_name,
        privacy_contact='dataprotection@test.example',
        terms_version=terms_version
    )


async def get_team_tree(uow_factory, user_id: int | None, team_id: int):
    async with uow_factory.get_uow(user_id=user_id) as uow:
        return await uow.repositories.team_trees.get(team_id=team_id)


@pytest.mark.asyncio(loop_scope="session")
async def test_create_team_tree_with_legal_entity(bus, uow_factory, isolated_state, terms_version):
    user_id = await AccountBuilder(uow_factory).account()
    name = TeamTreeBuilder.team_input().name
    await bus.handle(CreateTeam(agent_id=user_id, name=name, parent=None, legal_entity=legal_entity(terms_version)))

    async with uow_factory.get_uow(user_id=user_id) as uow:
        [root_id] = [
            team_tree.root.id async for team_tree in uow.repositories.team_trees.get_all()
            if team_tree.root.name == name
        ]
    team_tree = await get_team_tree(uow_factory, user_id, root_id)
    assert team_tree.legal_entity.legal_name == 'Test University'
    assert team_tree.legal_entity.privacy_contact == 'dataprotection@test.example'
    assert team_tree.legal_entity.terms_version == terms_version
    assert team_tree.legal_entity.declared_by == user_id
    assert team_tree.legal_entity.declared_at is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_declare_legal_entity_later_keeps_history(bus, uow_factory, isolated_state, terms_version):
    account = await AccountBuilder(uow_factory).account_with_affiliations()
    user_id, root_id = account['user_id'], account['team_id']
    assert (await get_team_tree(uow_factory, user_id, root_id)).legal_entity is None

    await bus.handle(DeclareLegalEntity(agent_id=user_id, team_id=root_id, legal_entity=legal_entity(terms_version)))
    await bus.handle(DeclareLegalEntity(
        agent_id=user_id, team_id=root_id, legal_entity=legal_entity(terms_version, legal_name='Renamed University')
    ))

    assert (await get_team_tree(uow_factory, user_id, root_id)).legal_entity.legal_name == 'Renamed University'
    async with uow_factory.get_uow() as uow:
        result = await uow.tx.run(
            "MATCH (:Team {id: $team_id})-[declared:DECLARED]->(declaration:LegalEntityDeclaration) "
            "RETURN declaration.legal_name AS legal_name, declared.current AS current ORDER BY declaration.declared_at",
            team_id=root_id
        )
        history = [(record['legal_name'], record['current']) async for record in result]
    assert history == [('Test University', False), ('Renamed University', True)]


@pytest.mark.asyncio(loop_scope="session")
async def test_legal_entity_visible_to_others_without_declared_by(bus, uow_factory, isolated_state, terms_version):
    account = await AccountBuilder(uow_factory).account_with_affiliations()
    other_user_id = await AccountBuilder(uow_factory).account()
    await bus.handle(DeclareLegalEntity(
        agent_id=account['user_id'], team_id=account['team_id'], legal_entity=legal_entity(terms_version)
    ))

    for user_id in (other_user_id, None):
        # Repositories return whole team trees, reads redact them for the user
        team_tree = (await get_team_tree(uow_factory, user_id, account['team_id'])).redacted(user_id)
        assert team_tree.legal_entity.legal_name == 'Test University'
        assert team_tree.legal_entity.declared_by is None


@pytest.mark.asyncio(loop_scope="session")
async def test_legal_entity_only_on_root(bus, uow_factory, isolated_state, terms_version):
    account = await AccountBuilder(uow_factory).account_with_affiliations()
    user_id, root_id = account['user_id'], account['team_id']
    with pytest.raises(IllegalOperationError, match="root team"):
        await bus.handle(CreateTeam(
            agent_id=user_id, name=TeamTreeBuilder.team_input().name, parent=root_id,
            legal_entity=legal_entity(terms_version)
        ))

    team_id = await child_team(bus, uow_factory, user_id, root_id)
    with pytest.raises(IllegalOperationError, match="root team"):
        await bus.handle(DeclareLegalEntity(agent_id=user_id, team_id=team_id, legal_entity=legal_entity(terms_version)))


@pytest.mark.asyncio(loop_scope="session")
async def test_declare_legal_entity_requires_root_admin_and_current_terms(bus, uow_factory, isolated_state, terms_version):
    account = await AccountBuilder(uow_factory).account_with_affiliations()
    other_user_id = await AccountBuilder(uow_factory).account()
    with pytest.raises(UnauthorisedOperationError):
        await bus.handle(DeclareLegalEntity(
            agent_id=other_user_id, team_id=account['team_id'], legal_entity=legal_entity(terms_version)
        ))
    with pytest.raises(IllegalOperationError, match="current data processing terms"):
        await bus.handle(DeclareLegalEntity(
            agent_id=account['user_id'], team_id=account['team_id'], legal_entity=legal_entity('old-terms')
        ))
    assert (await get_team_tree(uow_factory, account['user_id'], account['team_id'])).legal_entity is None


@pytest.mark.asyncio(loop_scope="session")
async def test_withdraw_legal_entity(bus, uow_factory, isolated_state, terms_version):
    account = await AccountBuilder(uow_factory).account_with_affiliations()
    user_id, root_id = account['user_id'], account['team_id']
    await bus.handle(DeclareLegalEntity(agent_id=user_id, team_id=root_id, legal_entity=legal_entity(terms_version)))

    # Refused while the team tree controls a Person, including from a child team
    team_id = await child_team(bus, uow_factory, user_id, root_id)
    person_id = await PersonBuilder(uow_factory).person(user_id=user_id, team_id=team_id)
    with pytest.raises(ProtectedNodeError, match="controls Persons"):
        await bus.handle(WithdrawLegalEntity(agent_id=user_id, team_id=root_id))

    # After transferring the Person to another team tree with a legal entity, it can be withdrawn
    other = await AccountBuilder(uow_factory).account_with_affiliations()
    await bus.handle(DeclareLegalEntity(agent_id=other['user_id'], team_id=other['team_id'], legal_entity=legal_entity(terms_version)))
    async with uow_factory.get_uow(user_id=user_id) as uow:
        transfer = await uow.controls.offer_transfer(
            entities=[ControlledEntity(label=ControlledModelLabel.PERSON, id=person_id)],
            from_teams={team_id}, recipient_team=other['team_id']
        )
        await uow.commit()
    async with uow_factory.get_uow(user_id=other['user_id']) as uow:
        await uow.controls.accept_transfer(transfer.id, to_teams={other['team_id']})
        await uow.commit()

    await bus.handle(WithdrawLegalEntity(agent_id=user_id, team_id=root_id))
    assert (await get_team_tree(uow_factory, user_id, root_id)).legal_entity is None
    async with uow_factory.get_uow() as uow:
        result = await uow.tx.run(
            "MATCH (:Team {id: $team_id})-[declared:DECLARED]->(declaration:LegalEntityDeclaration) "
            "RETURN declared.current AS current, declaration.withdrawn_by AS withdrawn_by, declaration.withdrawn_at IS NOT NULL AS withdrawn",
            team_id=root_id
        )
        record = await result.single()
    assert record['current'] is False and record['withdrawn'] and record['withdrawn_by'] == user_id
