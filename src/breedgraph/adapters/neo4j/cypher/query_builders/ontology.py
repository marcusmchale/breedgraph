from typing import List

from src.breedgraph.domain.model.ontology import OntologyEntryStored, OntologyRelationshipLabel
from src.breedgraph.domain.model.ontology.enums import LifecyclePhase

def name_in_use(label):
    return f"""
    RETURN exists {{ 
        MATCH (entry:{label}:OntologyEntry {{name_lower:$name_lower}})
        WHERE $exclude_id IS NULL OR entry.id <> $exclude_id
    }} AS exists
    """

def abbreviation_in_use(label):
    return f"""
    RETURN exists {{ 
        MATCH (entry:{label}:OntologyEntry {{abbreviation_lower:$abbreviation_lower}})
        WHERE $exclude_id IS NULL OR entry.id <> $exclude_id
    }} AS exists
    """

def create_ontology_entry(label):
  if not label in [e.label for e in OntologyEntryStored.__subclasses__()]:
    raise ValueError("Only ontology entry labels can be used")

  query = f"""
    MERGE (c:Counter {{name:'ontology_entry'}})
    ON CREATE SET c.count = 0
    SET c.count = c.count + 1
    CREATE (entry: {label}: OntologyEntry {{id: c.count}})
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

def update_ontology_entry(label):
  if not label in [e.label for e in OntologyEntryStored.__subclasses__()]:
    raise ValueError("Only ontology entry labels can be used")

  query = f"""
    MATCH (entry: OntologyEntry {{id: $entry_id}})
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
      OPTIONAL MATCH (author: Person)-[authored:AUTHORED]->(entry)
      WHERE NOT author.id in $authors
      DELETE authored
    }}
    CALL {{ 
      WITH entry
      UNWIND $authors as author_id
      MATCH (author: Person {{id: author_id}})
      MERGE (author)-[authored:AUTHORED]->(entry)
      ON CREATE SET authored.time = datetime.transaction()
    }}
    // Link References
    CALL {{
      WITH entry
      OPTIONAL MATCH (reference: Reference)-[ref_for:REFERENCE_FOR]->(entry)
      WHERE NOT reference.id in $references
      DELETE ref_for
    }}
    CALL {{
      WITH entry
      UNWIND $references as ref_id
      MATCH (reference: Reference {{id: ref_id}})
      MERGE (reference)-[ref_for:REFERENCE_FOR]->(entry)
      ON CREATE SET ref_for.time = datetime.transaction()      
    }}   
    RETURN NULL 
  """
  return query

def create_ontology_relationship(label: OntologyRelationshipLabel):
  try:
    label = OntologyRelationshipLabel(label)
  except KeyError:
    raise ValueError("Only ontology relationship labels can be used")

  query = f"""
    MATCH (source: OntologyEntry {{id:$source_id}})
    MATCH (target: OntologyEntry {{id:$target_id}})
    CREATE (source)
        -[:HAS_RELATIONSHIP]->(rel:{label.value}:OntologyRelationship)
        -[:RELATES_TO]->(target)
    SET rel += $attributes
  """
  return query

def update_ontology_relationship(label: OntologyRelationshipLabel):
  try:
    label = OntologyRelationshipLabel(label)
  except KeyError:
    raise ValueError("Only ontology relationship labels can be used")

  query = f"""
    MATCH (source: OntologyEntry {{id:$source_id}})
        -[:HAS_RELATIONSHIP]->(rel:{label.value}:OntologyRelationship)
        -[:RELATES_TO]->(target: OntologyEntry {{id:$target_id}})
    SET rel += $attributes
  """
  return query

def get_relationship_by_label(label: OntologyRelationshipLabel):
    try:
        label = OntologyRelationshipLabel(label)
    except KeyError:
        raise ValueError("Only ontology relationship labels can be used")

    query = f"""
        MATCH (entry: OntologyEntry {{id:$entry_id}})
        MATCH (source: OntologyEntry)
            -[:HAS_RELATIONSHIP|RELATES_TO]->(rel:{label.value}:OntologyRelationship)
            -[:RELATES_TO]->(target: OntologyEntry)
        WHERE source = entry OR target = entry
        RETURN 
            source.id as source_id, 
            target.id as target_id, 
            [label IN labels(rel) WHERE label <> "OntologyRelationship"][0] as label
    """
    return query

def has_path_between_entries(label: OntologyRelationshipLabel):
    try:
        label = OntologyRelationshipLabel(label)
    except KeyError:
        raise ValueError("Only ontology relationship labels can be used")
    query = f"""
        MATCH (source:OntologyEntry {{id:$source_id}})
            (
                (:OntologyEntry)
                -[:HAS_RELATIONSHIP]->(:{label.value}:OntologyRelationship)
                -[:RELATES_TO]->(:OntologyEntry)
            ){{1,}}
            (target:OntologyEntry {{id:$target_id}})
        RETURN count(*) >0 as has_path
        LIMIT 1
    """
    return query


def entries_exist_by_label(labels: List[str] | None = None) -> str:
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
        labels: List[str] | None = None,
        names: List[str] | None = None,
        entry_ids: List[int] | None = None,
        with_relationships: bool = False
) -> str:
    """
    Dynamically build Cypher query for fetching ontology entries.

    Args:
        version: Point-in-time version to evaluate phases against
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
        match_clause = f"MATCH (entry:OntologyEntry:{labels[0]})-[:HAS_LIFECYCLE]->(entry_lifecycle:OntologyEntryLifecycle)"
    else:
        match_clause = "MATCH (entry:OntologyEntry)-[:HAS_LIFECYCLE]->(entry_lifecycle:OntologyEntryLifecycle)"

    # Build WHERE conditions
    where_conditions = []

    # Phase filtering (applies with version context)
    phase_conditions = []
    if LifecyclePhase.DRAFT in phases:
        phase_conditions.append(
            "(entry_lifecycle.drafted <= $version AND "
            "(entry_lifecycle.activated IS NULL OR entry_lifecycle.activated > $version))"
        )
    if LifecyclePhase.ACTIVE in phases:
        phase_conditions.append(
            "(entry_lifecycle.activated <= $version AND "
            "(entry_lifecycle.deprecated IS NULL OR entry_lifecycle.deprecated > $version))"
        )
    if LifecyclePhase.DEPRECATED in phases:
        phase_conditions.append(
            "(entry_lifecycle.deprecated <= $version AND "
            "(entry_lifecycle.removed IS NULL OR entry_lifecycle.removed > $version))"
        )
    if LifecyclePhase.REMOVED in phases:
        phase_conditions.append("entry_lifecycle.removed <= $version")

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