"""
exact_text_regex matches as intended in Neo4j, whose regular expressions are Java's, not Python's: Python's re folds
case for non-ASCII letters by default, Java's (?i) does not, so only Neo4j can show the difference.
Evaluates expressions only, reading and writing no data.
"""
import pytest
from neo4j import GraphDatabase

from breedgraph.adapters.neo4j.cypher.matching import exact_text_regex


@pytest.fixture(scope='module')
def session():
    from breedgraph.config import get_bolt_url, get_graphdb_auth, DATABASE_NAME
    driver = GraphDatabase.driver(get_bolt_url(), auth=get_graphdb_auth())
    with driver.session(database=DATABASE_NAME) as session:
        yield session
    driver.close()


def matches(session, text: str, search: str) -> bool:
    return session.run("RETURN $text =~ $regex AS matched", text=text, regex=exact_text_regex(search)).single()['matched']


@pytest.mark.parametrize('text, search', [
    ('José Martínez', 'JOSÉ MARTÍNEZ'),
    ('Côte d’Ivoire', 'côte d’ivoire'),
    ('Ørsted', 'ørsted'),
    ('Ελλάδα', 'ΕΛΛΆΔΑ'),
    ('Smith', 'smith'),
])
def test_ignores_case_beyond_ascii(session, text, search):
    assert matches(session, text, search)


@pytest.mark.parametrize('text, search', [
    ('José Martínez', 'José'),        # the whole text, not a part
    ('José Martínez', 'Jose Martinez'),  # accents are not ignored
    ('A.B', 'A?B'),                    # regex characters are literal
    ('AxB', 'A.B'),
    ('Smith (UK)', 'Smith UK'),
])
def test_matches_the_whole_text_literally(session, text, search):
    assert not matches(session, text, search)


def test_regex_characters_match_themselves(session):
    assert matches(session, 'Smith (UK) [2] *', 'smith (uk) [2] *')
