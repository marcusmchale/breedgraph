import pytest

from breedgraph.custom_exceptions import NoResultFoundError
from breedgraph.domain.commands.ontologies import CreateDesign, UpdateDesign, CommitOntologyVersion
from breedgraph.domain.commands.references import CreateExternalReference
from breedgraph.domain.model.ontology import OntologyEntryLabel


async def private_reference(bus, user_id: int, team_id: int) -> int:
    return await bus.handle(CreateExternalReference(agent_id=user_id, write_team=team_id, url='https://example.org/private'))


@pytest.mark.asyncio(loop_scope="session")
async def test_citing_an_unreadable_reference_is_refused(bus, uow_factory, ontology_build_context, lorem_text_generator):
    context = ontology_build_context
    hidden_id = await private_reference(bus, context['user_id'], context['team_id'])
    readable_id = await private_reference(bus, context['user_id_2'], context['team_id_2'])
    name = lorem_text_generator.new_text()
    with pytest.raises(NoResultFoundError):
        await bus.handle(CreateDesign(agent_id=context['user_id_2'], name=name, reference_ids=[hidden_id]))

    await bus.handle(CreateDesign(agent_id=context['user_id_2'], name=name, reference_ids=[readable_id]))
    async with uow_factory.get_uow(user_id=context['user_id_2']) as uow:
        design = await uow.ontology.get_entry(name=name, label=OntologyEntryLabel.DESIGN)
    with pytest.raises(NoResultFoundError):
        await bus.handle(UpdateDesign(agent_id=context['user_id_2'], ontology_entry_id=design.id, reference_ids=[readable_id, hidden_id]))

    # a reference the user cannot read, already cited by someone else, does not stop them editing the entry
    await bus.handle(UpdateDesign(agent_id=context['user_id'], ontology_entry_id=design.id, reference_ids=[readable_id, hidden_id]))
    await bus.handle(UpdateDesign(agent_id=context['user_id_2'], ontology_entry_id=design.id, description='Edited'))


@pytest.mark.asyncio(loop_scope="session")
async def test_committing_with_an_unreadable_licence_is_refused(bus, ontology_build_context):
    context = ontology_build_context
    hidden_id = await private_reference(bus, context['user_id_2'], context['team_id_2'])
    with pytest.raises(NoResultFoundError):
        await bus.handle(CommitOntologyVersion(agent_id=context['user_id'], licence=hidden_id))
    with pytest.raises(NoResultFoundError):
        await bus.handle(CommitOntologyVersion(agent_id=context['user_id'], copyright=hidden_id))
