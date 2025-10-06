from typing import List

from src.breedgraph.domain.model.ontology import OntologyEntryStored, OntologyRelationshipLabel, OntologyEntryLabel
from src.breedgraph.domain.model.ontology.enums import LifecyclePhase

def name_in_use(label: OntologyEntryLabel):
    return f"""
    RETURN exists {{ 
        MATCH (entry:{label.value}:OntologyEntry {{name_lower:$name_lower}})
        WHERE $exclude_id IS NULL OR entry.id <> $exclude_id
    }} AS exists
    """

def abbreviation_in_use(label: OntologyEntryLabel):
    return f"""
    RETURN exists {{ 
        MATCH (entry:{label.value}:OntologyEntry {{abbreviation_lower:$abbreviation_lower}})
        WHERE $exclude_id IS NULL OR entry.id <> $exclude_id
    }} AS exists
    """

def create_ontology_entry(label: OntologyEntryLabel):
  query = f"""
    MERGE (c:Counter {{name:'ontology_entry'}})
    ON CREATE SET c.count = 0
    SET c.count = c.count + 1
    CREATE (entry: {label.value}: OntologyEntry {{id: c.count}})
    SET entry += $params
    WITH entry
    // Link contributor
    CALL {{
      WITH entry
      MATCH (user: User {{id: $user_id}})
      MERGE (user)-[c:CONTRIBUTED]->(contributions: UserOntologyContributions)
      CREATE (contributions)-[contributed:CONTRIBUTED {{time:datetime.transaction()}}]->(entry)
    }}
    // Link authors
    CALL {{
      WITH entry
      UNWIND $authors as author_id
      MATCH (author: Person {{id: author_id}})
      CREATE (author)-[authored:AUTHORED {{time:datetime.transaction()}}]->(entry)
      RETURN
        collect(author.id) as authors
    }}
    // Link references 
    CALL {{
      WITH entry
      UNWIND $references as ref_id
      MATCH (reference: Reference {{id: ref_id}})
      CREATE (reference)-[ref_for:REFERENCE_FOR {{time:datetime.transaction()}}]->(entry)
      RETURN
        collect(reference.id) as references
    }}
    RETURN entry {{
      .*,
      label: [label IN labels(entry) WHERE label <> "OntologyEntry"][0],
      authors: authors,
      references: references
    }}
  """
  return query

def create_ontology_relationship(label: OntologyRelationshipLabel):
  try:
    label = OntologyRelationshipLabel(label)
  except KeyError:
    raise ValueError("Only ontology relationship labels can be used")

  query = f"""
    MERGE (c:Counter {{name:'ontology_relationship'}})
    ON CREATE SET c.count = 0
    WITH c
    SET c.count = c.count + 1
    WITH c
    MATCH (source: OntologyEntry {{id:$source_id}}), (target: OntologyEntry {{id:$target_id}})
    CREATE (source)
        -[:HAS_RELATIONSHIP]->(relationship:{label.value}:OntologyRelationship)
        -[:RELATES_TO]->(target)
    SET relationship.id = c.count
    SET relationship += $attributes
    RETURN relationship {{
        relationship_id: relationship.id,
        label: [label IN labels(relationship) WHERE label <> "OntologyRelationship"][0],
        source_id: source.id,
        target_id: target.id
    }}
  """
  return query

def update_ontology_relationship(label: OntologyRelationshipLabel):
  query = f"""
    MATCH (source: OntologyEntry {{id:$source_id}})
        -[:HAS_RELATIONSHIP]->(relationship:{label.value}:OntologyRelationship)
        -[:RELATES_TO]->(target: OntologyEntry {{id:$target_id}})
    SET relationship += $attributes
  """
  return query

def get_relationship_by_label(label: OntologyRelationshipLabel):
    query = f"""
        MATCH (entry: OntologyEntry {{id:$entry_id}})
        MATCH (source: OntologyEntry)
            -[:HAS_RELATIONSHIP|RELATES_TO]->(relationship:{label.value}:OntologyRelationship)
            -[:RELATES_TO]->(target: OntologyEntry)
        WHERE source = entry OR target = entry
        RETURN relationship {{
            relationship_id: relationship.id,
            label: [label IN labels(relationship) WHERE label <> "OntologyRelationship"][0],
            source_id: source.id,
            target_id: target.id
        }}
    """
    return query

def has_path_between_entries(label: OntologyRelationshipLabel):
    query = f"""
        MATCH (source:OntologyEntry {{id: $source_id}})
            (
                (:OntologyEntry)
                -[:HAS_RELATIONSHIP]->(:{label.value}:OntologyRelationship)
                -[:RELATES_TO]->(:OntologyEntry)
            ){{1,}}
            (target:OntologyEntry {{id: $target_id}})
        RETURN count(*) >0 as has_path
        LIMIT 1
    """
    return query


def entries_exist_by_label(labels: List[OntologyEntryLabel] | None = None) -> str:
    """
    Build Cypher query to check if entries exist by ID, optionally filtered by labels.
    Args:
        labels: Optional list of Neo4j labels to filter by
    Returns:
        Cypher query that returns entry_id and exists boolean for each input ID
    Usage:
        Parameters expected:
        - $entry_ids: List of entry IDs to check
    """
    # Build match clause with optional label filtering
    if labels is not None and len(labels) > 0:
        # get values of label enums as string
        labels = [label.value for label in labels]
        if len(labels) == 1:
            match_clause = f"OPTIONAL MATCH (entry:OntologyEntry:{labels[0]} {{id: entry_id}})"
        else:
            # For multiple labels, create a label condition
            label_conditions = " OR ".join([f"entry:{label}" for label in labels])
            match_clause = f"OPTIONAL MATCH (entry:OntologyEntry {{id: entry_id}}) WHERE {label_conditions}"
    else:
        match_clause = "OPTIONAL MATCH (entry:OntologyEntry {id: entry_id})"

    query = f"""
    UNWIND $entry_ids AS entry_id
    {match_clause}
    RETURN entry_id as id, entry IS NOT NULL AS exists
    ORDER BY id
    """

    return query


def get_all_entries(
        phases: List[LifecyclePhase],
        labels: List[OntologyEntryLabel] | None = None,
        names: List[str] | None = None,
        entry_ids: List[int] | None = None,
        with_relationships: bool = False
) -> str:
    """
    Dynamically build Cypher query for fetching ontology entries.

    Args:
        phases: Lifecycle phases to include (evaluated at the given version)
        labels: Neo4j labels (subtypes) to filter by - these go in the MATCH clause
        names: Entry names to filter by - these should be parameterized as a list of lower-case names, $names_lower
        entry_ids: Entry IDs to filter by
        with_relationships: Whether to include ontology relationships in output

    Returns:
        Complete Cypher query string
    """
    # Build MATCH clause with label filtering
    if labels:
        # get values of label enums as string
        labels = [label.value for label in labels]
        match_clause = f"MATCH (entry:OntologyEntry:{labels[0]})-[:HAS_LIFECYCLE]->(lifecycle:OntologyLifecycle)"
    else:
        match_clause = "MATCH (entry:OntologyEntry)-[:HAS_LIFECYCLE]->(lifecycle:OntologyLifecycle)"

    # Build WHERE conditions
    where_conditions = []

    # Phase filtering (applies with version context)
    phase_conditions = []
    if LifecyclePhase.DRAFT in phases:
        phase_conditions.append(
            "(lifecycle.drafted <= $version AND "
            "(lifecycle.activated IS NULL OR lifecycle.activated > $version))"
        )
    if LifecyclePhase.ACTIVE in phases:
        phase_conditions.append(
            "(lifecycle.activated <= $version AND "
            "(lifecycle.deprecated IS NULL OR lifecycle.deprecated > $version))"
        )
    if LifecyclePhase.DEPRECATED in phases:
        phase_conditions.append(
            "(lifecycle.deprecated <= $version AND "
            "(lifecycle.removed IS NULL OR lifecycle.removed > $version))"
        )
    if LifecyclePhase.REMOVED in phases:
        phase_conditions.append("lifecycle.removed <= $version")

    where_conditions.append(f"({' OR '.join(phase_conditions)})")

    # Name filtering (parameterized)
    if names:
        where_conditions.append("entry.name_lower IN $names_lower")

    # Entry ID filtering (parameterized)
    if entry_ids:
        where_conditions.append("entry.id IN $entry_ids")

    # Build WHERE clause
    where_clause = ""
    if where_conditions:
        where_clause = "WHERE " + " AND ".join(where_conditions)

    # Build RETURN clause
    if with_relationships:
        return_clause = """RETURN
  entry {
    .*,
    label: [label IN labels(entry) WHERE label <> "OntologyEntry"][0],
    authors: [(author: Person)-[authored:AUTHORED]->(entry) | author.id ],
    references: [(reference: Reference)-[ref_for:REFERENCE_FOR]->(entry) | reference.id ],
    relationships: [
      (source)-[:HAS_RELATIONSHIP]-(rel: OntologyRelationship)-[:RELATES_TO]->(target:OntologyEntry)
      WHERE source = entry or target = entry |
      {
        relationship_id: rel.id,
        source_id: source.id,
        source_label: [label IN labels(source) WHERE label <> "OntologyEntry"][0],
        target_id: target.id,
        target_label: [label IN labels(target) WHERE label <> "OntologyEntry"][0],
        relationship_type: [label IN labels(rel) WHERE label <> "OntologyRelationship"][0],
        properties: properties(rel)
      }
    ]
  } as entry"""
    else:
        return_clause = """RETURN
  entry {
    .*,
    label: [label IN labels(entry) WHERE label <> "OntologyEntry"][0],
    authors: [(author: Person)-[authored:AUTHORED]->(entry) | author.id ],
    references: [(reference: Reference)-[ref_for:REFERENCE_FOR]->(entry) | reference.id ]
  } as entry"""

    # Handle multiple labels with UNION
    if labels is not None and len(labels) > 1:
        # Build separate queries for each label and combine with UNION
        queries = []
        for label in labels:
            query_parts = [f"MATCH (entry:OntologyEntry:{label})"]
            if where_clause:
                query_parts.append(where_clause)
            query_parts.append(return_clause)
            queries.append("\n".join(query_parts))

        return "\nUNION\n".join(queries)
    else:
        # Single query
        query_parts = [match_clause]
        if where_clause:
            query_parts.append(where_clause)
        query_parts.append(return_clause)

        return "\n".join(query_parts)

def get_all_relationships(
        phases: List[LifecyclePhase],
        labels: List[OntologyRelationshipLabel] | None = None,
        entry_ids: List[int] | None = None,
) -> str:
    """
    Dynamically build Cypher query for fetching ontology relationships.

    Args:
        phases: Lifecycle phases to include (evaluated at the given version)
        labels: Neo4j labels (subtypes) to filter by - these go in the MATCH clause
        entry_ids: Entry IDs to filter by
    Returns:
        Complete Cypher query string
    """
    # Build MATCH clause with label filtering
    if labels:
        # get values of label enums as string
        labels = [label.value for label in labels]
        match_clause = f"MATCH (relationship:OntologyRelationship:{labels[0]})-[:HAS_LIFECYCLE]->(lifecycle:OntologyLifecycle)"
    else:
        match_clause = "MATCH (relationship:OntologyRelationship)-[:HAS_LIFECYCLE]->(lifecycle:OntologyLifecycle)"

    # Entry ID filtering (parameterized)
    if entry_ids:
        match_clause = match_clause + ", (relationship)--(entry:OntologyEntry) where entry.id IN $entry_ids"

    # Phase filtering (applies with version context)
    phase_conditions = []
    if LifecyclePhase.DRAFT in phases:
        phase_conditions.append(
            "(lifecycle.drafted <= $version AND "
            "(lifecycle.activated IS NULL OR lifecycle.activated > $version))"
        )
    if LifecyclePhase.ACTIVE in phases:
        phase_conditions.append(
            "(lifecycle.activated <= $version AND "
            "(lifecycle.deprecated IS NULL OR lifecycle.deprecated > $version))"
        )
    if LifecyclePhase.DEPRECATED in phases:
        phase_conditions.append(
            "(lifecycle.deprecated <= $version AND "
            "(lifecycle.removed IS NULL OR lifecycle.removed > $version))"
        )
    if LifecyclePhase.REMOVED in phases:
        phase_conditions.append("lifecycle.removed <= $version")

    # Build WHERE clause
    where_clause = ""
    if phase_conditions:
        where_clause = "WHERE " + ' OR '.join(phase_conditions)

    return_clause = """RETURN
      relationship {
        relationship_id: relationship.id,
        label: [label IN labels(relationship) WHERE label <> "OntologyRelationship"][0],
        source_id: [(relationship)<-[:HAS_RELATIONSHIP]-(source) | source.id][0],
        target_id: [(relationship)-[:RELATES_TO]->(target) | target.id][0]
      } as relationship """

    # Handle multiple labels with UNION
    if labels is not None and len(labels) > 1:
        # Build separate queries for each label and combine with UNION
        queries = []
        for label in labels:
            query_parts = [f"MATCH (relationship:OntologyRelationship:{label})"]
            if where_clause:
                query_parts.append(where_clause)
            query_parts.append(return_clause)
            queries.append("\n".join(query_parts))

        return "\nUNION\n".join(queries)
    else:
        # Single query
        query_parts = [match_clause]
        if where_clause:
            query_parts.append(where_clause)
        query_parts.append(return_clause)

        return "\n".join(query_parts)