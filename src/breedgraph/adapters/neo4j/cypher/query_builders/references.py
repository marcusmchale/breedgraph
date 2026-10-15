from breedgraph.domain.model.controls import ControlledModelLabel
from breedgraph.adapters.neo4j.cypher.query_builders.access import visible as _visible

# References as the user may see them (see docs/read-access.md). Each reference is an aggregate of its own, so a
# reference the user cannot read is a placeholder when asked for by id, as other entities refer to references by id:
# its id, its type (GraphQL needs it to choose the reference's type, so the user learns what kind of reference it
# is) and a REDACTED description, nothing more. A search leaves hidden references out.

REFERENCE = ControlledModelLabel.REFERENCE


def _reference(reference: str = 'reference', visible: str = 'reference_visible') -> str:
    return f"""CASE WHEN {visible} THEN {reference} {{ .* }}
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


def search_references():
    """
    The references the user can read whose description matches $description in the full text index, best first,
    of the types $types when given
    """
    return f"""
        CALL db.index.fulltext.queryNodes("referenceDescription", $description) YIELD node AS reference, score
        WHERE $types IS NULL OR reference.type IN $types
        {_visible('reference', REFERENCE, 'reference_visible')}
        WITH reference, reference_visible, score WHERE reference_visible
        RETURN {_reference()} AS reference
        ORDER BY score DESC
    """
