import pytest

from breedgraph.custom_exceptions import NoResultFoundError, UnauthorisedOperationError, IllegalOperationError
from breedgraph.domain.commands.ontologies import (
    CreateDesign, UpdateDesign, CommitOntologyVersion,
    CreateRole, UpdateRole, CreateTerm, CreateScale, UpdateScale, CreateScaleCategory,
    LockOntologyEntries, UnlockOntologyEntries, DeprecateOntologyEntries, UpdateLocationType
)
from breedgraph.domain.commands.setup import RefreshReadModels
from breedgraph.service_layer.application.ontology_seed import COUNTRY, credit_seed_key_for
from breedgraph.domain.commands.references import CreateExternalReference
from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.ontology import OntologyEntryLabel, OntologyRelationshipLabel, ScaleType, credit_roles, CREDIT_ATTRIBUTION


async def private_reference(bus, user_id: int, team_id: int) -> int:
    return await bus.handle(CreateExternalReference(agent_id=user_id, write_team=team_id, url='https://example.org/private'))


async def reference_released(bus, user_id: int, team_id: int, release: ReadRelease) -> int:
    return await bus.handle(CreateExternalReference(
        agent_id=user_id, write_team=team_id, release=release, url=f'https://example.org/{release.name.lower()}'
    ))


@pytest.mark.asyncio(loop_scope="session")
async def test_citing_an_unreadable_reference_is_refused(bus, uow_factory, ontology_build_context, lorem_text_generator):
    context = ontology_build_context
    hidden_id = await private_reference(bus, context['user_id'], context['team_id'])
    public_id = await reference_released(bus, context['user_id_2'], context['team_id_2'], ReadRelease.PUBLIC)
    name = lorem_text_generator.new_text()
    with pytest.raises(NoResultFoundError):
        await bus.handle(CreateDesign(agent_id=context['user_id_2'], name=name, reference_ids=[hidden_id]))

    await bus.handle(CreateDesign(agent_id=context['user_id_2'], name=name, reference_ids=[public_id]))
    async with uow_factory.get_uow(user_id=context['user_id_2']) as uow:
        design = await uow.ontology.get_entry(name=name, label=OntologyEntryLabel.DESIGN)
    with pytest.raises(NoResultFoundError):
        await bus.handle(UpdateDesign(agent_id=context['user_id_2'], ontology_entry_id=design.id, reference_ids=[public_id, hidden_id]))
    await bus.handle(UpdateDesign(agent_id=context['user_id_2'], ontology_entry_id=design.id, description='Edited'))


@pytest.mark.asyncio(loop_scope="session")
async def test_committing_with_an_unreadable_licence_is_refused(bus, ontology_build_context):
    context = ontology_build_context
    hidden_id = await private_reference(bus, context['user_id_2'], context['team_id_2'])
    with pytest.raises(NoResultFoundError):
        await bus.handle(CommitOntologyVersion(agent_id=context['user_id'], licence=hidden_id))
    with pytest.raises(NoResultFoundError):
        await bus.handle(CommitOntologyVersion(agent_id=context['user_id'], copyright=hidden_id))


async def entry_id(uow_factory, context, name: str, label: OntologyEntryLabel) -> int:
    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        return (await uow.ontology.get_entry(name=name, label=label)).id


@pytest.mark.asyncio(loop_scope="session")
async def test_only_ontology_admins_lock_entries(bus, uow_factory, ontology_build_context, lorem_text_generator):
    context = ontology_build_context
    name = lorem_text_generator.new_text()
    await bus.handle(CreateRole(agent_id=context['user_id_2'], name=name))
    role_id = await entry_id(uow_factory, context, name, OntologyEntryLabel.ROLE)
    with pytest.raises(UnauthorisedOperationError):
        await bus.handle(LockOntologyEntries(agent_id=context['user_id_2'], entry_ids=[role_id]))
    await bus.handle(LockOntologyEntries(agent_id=context['user_id'], entry_ids=[role_id]))
    with pytest.raises(UnauthorisedOperationError):
        await bus.handle(UnlockOntologyEntries(agent_id=context['user_id_2'], entry_ids=[role_id]))


@pytest.mark.asyncio(loop_scope="session")
async def test_a_locked_entry_keeps_its_attributes_and_defining_relationships(
        bus, uow_factory, ontology_build_context, lorem_text_generator
):
    context = ontology_build_context
    admin = context['user_id']
    names = [lorem_text_generator.new_text() for _ in range(6)]
    role_name, child_name, term_name, scale_name, category_name, other_category_name = names

    await bus.handle(CreateRole(
        agent_id=admin, name=role_name, description='A standard role',
        source_url='https://example.org/roles/standard', source_attribution='Example (2026). Roles.'
    ))
    role_id = await entry_id(uow_factory, context, role_name, OntologyEntryLabel.ROLE)
    await bus.handle(CreateTerm(agent_id=admin, name=term_name))
    term_id = await entry_id(uow_factory, context, term_name, OntologyEntryLabel.TERM)
    await bus.handle(CreateScaleCategory(agent_id=admin, name=category_name))
    await bus.handle(CreateScaleCategory(agent_id=admin, name=other_category_name))
    category_id = await entry_id(uow_factory, context, category_name, OntologyEntryLabel.CATEGORY)
    other_category_id = await entry_id(uow_factory, context, other_category_name, OntologyEntryLabel.CATEGORY)
    await bus.handle(CreateScale(agent_id=admin, name=scale_name, scale_type=ScaleType.NOMINAL, category_ids=[category_id]))
    scale_id = await entry_id(uow_factory, context, scale_name, OntologyEntryLabel.SCALE)

    await bus.handle(LockOntologyEntries(agent_id=admin, entry_ids=[role_id, scale_id]))

    # attributes fixed by the lock, and deprecation, are refused, even for admins
    for update in (
        UpdateRole(agent_id=admin, ontology_entry_id=role_id, description='Changed'),
        UpdateRole(agent_id=admin, ontology_entry_id=role_id, name=lorem_text_generator.new_text()),
        UpdateRole(agent_id=admin, ontology_entry_id=role_id, source_url='https://example.org/other'),
        # a scale's categories define it
        UpdateScale(agent_id=admin, ontology_entry_id=scale_id, scale_type=ScaleType.NOMINAL, category_ids=[category_id, other_category_id]),
        UpdateScale(agent_id=admin, ontology_entry_id=scale_id, scale_type=ScaleType.NOMINAL, category_ids=[]),
        DeprecateOntologyEntries(agent_id=admin, entry_ids=[role_id]),
    ):
        with pytest.raises(UnauthorisedOperationError):
            await bus.handle(update)

    # synonyms, children and terms stay open
    await bus.handle(UpdateRole(agent_id=admin, ontology_entry_id=role_id, synonyms=['DataCurator'], term_ids=[term_id]))
    await bus.handle(CreateRole(agent_id=context['user_id_2'], name=child_name, parent_ids=[role_id]))
    async with uow_factory.get_uow(user_id=admin) as uow:
        role = await uow.ontology.get_entry(entry_id=role_id)
        assert role.locked
        assert (role.description, role.source_url, role.synonyms) == ('A standard role', 'https://example.org/roles/standard', ['DataCurator'])
        child = await uow.ontology.get_entry(name=child_name, label=OntologyEntryLabel.ROLE)
        parents = [rel.source_id async for rel in uow.ontology.get_relationships(target_ids=[child.id], labels=[OntologyRelationshipLabel.PARENT_OF])]
        assert parents == [role_id]

    await bus.handle(UnlockOntologyEntries(agent_id=admin, entry_ids=[role_id]))
    await bus.handle(UpdateRole(agent_id=admin, ontology_entry_id=role_id, description='Changed'))
    async with uow_factory.get_uow(user_id=admin) as uow:
        role = await uow.ontology.get_entry(entry_id=role_id)
        assert (role.locked, role.description) == (False, 'Changed')


@pytest.mark.asyncio(loop_scope="session")
async def test_the_credit_roles_are_seeded_locked_and_active(views_factory, ontology_build_context):
    async with views_factory.get_views(user_id=ontology_build_context['user_id']) as views:
        roles = {role.name: role for role in await views.ontology.get_entries(labels=[OntologyEntryLabel.ROLE])}
    for credit_role in credit_roles():
        role = roles[credit_role.name]
        assert role.locked
        assert role.description == credit_role.definition
        assert (role.source_url, role.source_attribution) == (credit_role.url, CREDIT_ATTRIBUTION)


@pytest.mark.asyncio(loop_scope="session")
async def test_seeded_entries_are_found_by_key_whatever_their_name(bus, uow_factory, state_store, ontology_build_context):
    admin = ontology_build_context['user_id']
    async with uow_factory.get_uow(user_id=admin) as uow:
        country = await uow.ontology.get_seeded_entry(COUNTRY)
        curation = await uow.ontology.get_seeded_entry(credit_seed_key_for('Data curation'))
    assert (country.name, country.locked) == ('Country', True)
    assert (curation.name, curation.label) == ('Data curation', OntologyEntryLabel.ROLE)

    # locked, it cannot be deprecated; unlocked and renamed, it is still found
    with pytest.raises(UnauthorisedOperationError):
        await bus.handle(DeprecateOntologyEntries(agent_id=admin, entry_ids=[country.id]))
    await bus.handle(UnlockOntologyEntries(agent_id=admin, entry_ids=[country.id]))
    await bus.handle(UpdateLocationType(agent_id=admin, ontology_entry_id=country.id, name='Nation'))
    try:
        async with uow_factory.get_uow(user_id=admin) as uow:
            assert (await uow.ontology.get_seeded_entry(COUNTRY)).name == 'Nation'
        await bus.handle(RefreshReadModels(names=['countries']))
        assert (await state_store.get_country('VNM')).type == country.id
    finally:
        await bus.handle(UpdateLocationType(agent_id=admin, ontology_entry_id=country.id, name='Country'))
        await bus.handle(LockOntologyEntries(agent_id=admin, entry_ids=[country.id]))


async def lock_records(uow_factory, context, entry_id: int) -> list:
    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        result = await uow.tx.run(
            "MATCH (:User)-[:LOCKED]->(:UserOntologyLocks)-[lock:LOCKED]->(:OntologyEntry {id: $entry_id}) "
            "RETURN lock.locked AS locked ORDER BY lock.time",
            entry_id=entry_id
        )
        return [record['locked'] async for record in result]


@pytest.mark.asyncio(loop_scope="session")
async def test_locking_is_attributed_only_when_the_lock_changes(bus, uow_factory, ontology_build_context, lorem_text_generator):
    context = ontology_build_context
    name = lorem_text_generator.new_text()
    await bus.handle(CreateRole(agent_id=context['user_id'], name=name))
    role_id = await entry_id(uow_factory, context, name, OntologyEntryLabel.ROLE)

    await bus.handle(LockOntologyEntries(agent_id=context['user_id'], entry_ids=[role_id]))
    await bus.handle(LockOntologyEntries(agent_id=context['user_id'], entry_ids=[role_id]))
    assert await lock_records(uow_factory, context, role_id) == [True]
    await bus.handle(UnlockOntologyEntries(agent_id=context['user_id'], entry_ids=[role_id]))
    assert await lock_records(uow_factory, context, role_id) == [True, False]

    # a lock is not a contribution to the entry
    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        result = await uow.tx.run(
            "MATCH (:UserOntologyContributions)-[:CONTRIBUTED]->(:OntologyEntryLock) RETURN count(*) AS locks"
        )
        assert (await result.single())['locks'] == 0


async def managed_phases(uow_factory, context, entry_id: int) -> list:
    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        result = await uow.tx.run(
            "MATCH (:OntologyEntry {id: $entry_id})-[:HAS_LIFECYCLE]->(lifecycle)<-[managed:MANAGED]-() "
            "RETURN managed.phases AS phases, managed.times AS times",
            entry_id=entry_id
        )
        record = await result.single()
        assert len(record['phases']) == len(record['times'])
        return record['phases']


@pytest.mark.asyncio(loop_scope="session")
async def test_lifecycle_history_records_only_changes(bus, uow_factory, ontology_build_context, lorem_text_generator):
    context = ontology_build_context
    name = lorem_text_generator.new_text()
    await bus.handle(CreateRole(agent_id=context['user_id'], name=name))
    role_id = await entry_id(uow_factory, context, name, OntologyEntryLabel.ROLE)
    assert await managed_phases(uow_factory, context, role_id) == ['DRAFT']

    await bus.handle(DeprecateOntologyEntries(agent_id=context['user_id'], entry_ids=[role_id]))
    assert await managed_phases(uow_factory, context, role_id) == ['DRAFT', 'DEPRECATED']
    # deprecating it again changes nothing, so records nothing
    await bus.handle(DeprecateOntologyEntries(agent_id=context['user_id'], entry_ids=[role_id]))
    assert await managed_phases(uow_factory, context, role_id) == ['DRAFT', 'DEPRECATED']


@pytest.mark.asyncio(loop_scope="session")
async def test_the_ontology_cites_public_references_only(bus, uow_factory, ontology_build_context, lorem_text_generator):
    """
    The ontology is shared: what it cites is public, so no reader sees a placeholder (docs/read-access.md, rule 10).
    Last, as committing a version activates the drafts of the tests before it.
    """
    context = ontology_build_context
    user_id, team_id = context['user_id'], context['team_id']
    for release in (ReadRelease.REGISTERED, ReadRelease.PRIVATE):
        # the user reads the reference, through their team, but it is not public
        reference_id = await reference_released(bus, user_id, team_id, release)
        with pytest.raises(IllegalOperationError, match=f"Reference {reference_id} is released as {release.name}"):
            await bus.handle(CommitOntologyVersion(agent_id=user_id, licence=reference_id))
        with pytest.raises(IllegalOperationError, match=f"Reference {reference_id} is released as {release.name}"):
            await bus.handle(CommitOntologyVersion(agent_id=user_id, copyright=reference_id))
        with pytest.raises(IllegalOperationError, match="public references only"):
            await bus.handle(CreateDesign(agent_id=user_id, name=lorem_text_generator.new_text(), reference_ids=[reference_id]))

    public_id = await reference_released(bus, user_id, team_id, ReadRelease.PUBLIC)
    await bus.handle(CommitOntologyVersion(agent_id=user_id, licence=public_id, copyright=public_id))
    name = lorem_text_generator.new_text()
    await bus.handle(CreateDesign(agent_id=user_id, name=name, reference_ids=[public_id]))
    async with uow_factory.get_uow(user_id=user_id) as uow:
        assert (await uow.ontology.get_entry(name=name, label=OntologyEntryLabel.DESIGN)).references == [public_id]
