"""
The full text query a references search runs for what someone typed (query_builders.references.search_terms): every
word as a prefix, all of them required, and nothing Lucene's query syntax would read as an operator.
"""
import pytest

from breedgraph.adapters.neo4j.cypher.query_builders.references import search_terms


@pytest.mark.parametrize('text, terms', [
    # a word as far as it is typed
    ('Exampl', 'exampl*'),
    ('exampl lic', 'exampl* AND lic*'),
    # operators are words like any other, in lower case
    ('AND', 'and*'),
    ('licence OR NOT', 'licence* AND or* AND not*'),
    # the syntax's characters split words, as spaces do
    ('Licence (2026)', 'licence* AND 2026*'),
    ('https://example.org/licence', 'https* AND example.org* AND licence*'),
    ('doi:10.1234', 'doi* AND 10.1234*'),
    ('Partner Data-Licence', 'partner* AND data* AND licence*'),
    ('"quoted" [range] {x} a~2 b^3 c? d* e\\f g!h i&&j k||l m+n', (
        'quoted* AND range* AND x* AND a* AND 2* AND b* AND 3* AND c* AND d* AND e* AND f* AND g* AND h* AND i* AND j* '
        'AND k* AND l* AND m* AND n*'
    )),
])
def test_words_as_prefixes(text, terms):
    assert search_terms(text) == terms


@pytest.mark.parametrize('text', ['', '   ', '(', '"', '\\', '*?~'])
def test_no_words_no_query(text):
    assert search_terms(text) is None
