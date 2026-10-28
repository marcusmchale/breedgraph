"""
The database runs the Cypher the queries are written in (adapters/neo4j/driver.py), which the API checks at startup and
scripts/setup_initial_data.py sets: the test services are made with it (scripts/scratch_services.sh), and a database
running another is refused, saying how to set it.
"""
import pytest

from breedgraph.adapters.neo4j.driver import WrongCypherLanguage, CYPHER_LANGUAGE


@pytest.mark.asyncio(loop_scope="session")
async def test_the_database_runs_the_queries_cypher(uow_factory):
    await uow_factory.driver.set_cypher_language()
    assert await uow_factory.driver.cypher_language() == CYPHER_LANGUAGE
    await uow_factory.driver.check_cypher_language()


@pytest.mark.asyncio(loop_scope="session")
async def test_a_database_running_another_cypher_is_refused(uow_factory, monkeypatch):
    async def cypher_5():
        return 'CYPHER 5'
    monkeypatch.setattr(uow_factory.driver, 'cypher_language', cypher_5)
    with pytest.raises(WrongCypherLanguage, match=r'runs CYPHER 5.*ALTER DATABASE \S+ SET DEFAULT LANGUAGE CYPHER 25'):
        await uow_factory.driver.check_cypher_language()
