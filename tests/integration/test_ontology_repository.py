import pytest

from src.breedgraph.domain.model.ontologies import OntologyEntry, OntologyEntryStored, Ontology

from src.breedgraph.adapters.repositories.ontologies import Neo4jOntologyRepository

from src.breedgraph.custom_exceptions import NoResultFoundError

async def create_ontology_reference(lorem_text_generator, parent: int = None) -> OntologyEntry:
    return OntologyEntry(name=lorem_text_generator.new_text(), parent=parent)

@pytest.mark.asyncio(scope="session")
async def test_create_ontology(neo4j_tx, lorem_text_generator):
    reference = await create_ontology_reference(lorem_text_generator)
    ontology = Ontology(references=[reference])

    repo = Neo4jOntologyRepository(neo4j_tx)
    stored_ontology = await repo.create(ontology)
    import pdb; pdb.set_trace()
    # test that retrieve by id works
    #retrieved_from_root_id = await organisations_repo.get(stored_organisation.root.id)
    #assert retrieved_from_root_id.root.name == team_input.name
    ## test that retrieve all includes the submitted entry
    #async for org in organisations_repo.get_all():
    #    # todo test filters by team, access and authorisation
    #    # for this we need to add affiliations etc.
    #    if org.root.name == team_input.name:
    #        break
    #else:
    #    raise NoResultFoundError


