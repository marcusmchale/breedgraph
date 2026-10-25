import re

from breedgraph.domain.model.controls import ControlledModelLabel
from breedgraph.adapters.neo4j.cypher.query_builders.access import visible as _visible, contributions as _contributions

# References as the user may see them (see docs/read-access.md). Each reference is an aggregate of its own, so a
# reference the user cannot read is a placeholder when asked for by id, as other entities refer to references by id:
# its id, its type (GraphQL needs it to choose the reference's type, so the user learns what kind of reference it
# is) and a REDACTED description, nothing more. A search leaves hidden references out.

REFERENCE = ControlledModelLabel.REFERENCE


def _reference(reference: str = 'reference', visible: str = 'reference_visible') -> str:
    return f"""CASE WHEN {visible} THEN {reference} {{ .*,
            contributions: {_contributions(reference)}
          }}
          ELSE {reference} {{ .id, .type, description: 'REDACTED' }} END"""


def read_references():
    """The references with ids $reference_ids, a placeholder for those the user cannot read"""
    return f"""
        MATCH (reference: Reference)
        WHERE reference.id IN $reference_ids
        {_visible('reference', REFERENCE, 'reference_visible')}
        RETURN {_reference()} AS reference
        ORDER BY reference.id
    """


def read_file_reference():
    """The file reference stored as $file_id, a placeholder if the user cannot read it, so its file id is not returned"""
    return f"""
        MATCH (reference: Reference {{file_id: $file_id}})
        {_visible('reference', REFERENCE, 'reference_visible')}
        RETURN {_reference()} AS reference
        LIMIT 1
    """


# Lucene's query syntax: a search's text is split on these characters, its operators, as on spaces
_LUCENE_OPERATORS = re.compile(r'[\s+\-&|!(){}\[\]^"~*?:\\/]+')


def search_terms(text: str) -> str | None:
    """
    The full text query search_references runs for what someone typed: each of its words, as far as it is typed,
    begins a word of the match, so "exampl lic" finds "Example Ontology Licence". None when it has no words. The words
    are lower case, so none is an operator (AND, OR, NOT), and the operators' characters split words, so no text makes
    a query Lucene refuses.
    """
    words = [word.lower() for word in _LUCENE_OPERATORS.split(text) if word]
    return ' AND '.join(f'{word}*' for word in words) or None


def search_references():
    """
    The references the user can read whose description, file name, URL or external id matches $description, a full
    text query (search_terms), best first, of the types $types when given
    """
    return f"""
        CALL db.index.fulltext.queryNodes("referenceDescription", $description) YIELD node AS reference, score
        WHERE $types IS NULL OR reference.type IN $types
        {_visible('reference', REFERENCE, 'reference_visible')}
        WITH reference, reference_visible, score WHERE reference_visible
        RETURN {_reference()} AS reference
        ORDER BY score DESC
    """
