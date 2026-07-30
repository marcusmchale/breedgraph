from typing import List

from breedgraph.domain.model.ontology import OntologyEntryStored, OntologyRelationshipLabel, OntologyEntryLabel
from breedgraph.domain.model.ontology.enums import LifecyclePhase

def name_in_use(label: OntologyEntryLabel):
    return f"""
    RETURN exists {{ 
        MATCH (entry:{label.value}:OntologyEntry {{name_lower:$name_lower}})-[:HAS_LIFECYCLE]->(lifecycle:OntologyLifecycle)
        WHERE lifecycle.removed is NULL
        AND ($exclude_id IS NULL OR entry.id <> $exclude_id)
    }} AS exists
    """

def abbreviation_in_use(label: OntologyEntryLabel):
    return f"""
    RETURN exists {{ 
        MATCH (entry:{label.value}:OntologyEntry {{abbreviation_lower:$abbreviation_lower}})-[:HAS_LIFECYCLE]->(lifecycle:OntologyLifecycle)
        WHERE lifecycle.removed is NULL
        AND ($exclude_id IS NULL OR entry.id <> $exclude_id)
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
    CALL (entry) {{
      MATCH (user: User {{id: $user_id}})
      MERGE (user)-[c:CONTRIBUTED]->(contributions: UserOntologyContributions)
      CREATE (contributions)-[contributed:CONTRIBUTED {{time:datetime.transaction()}}]->(entry)
    }}
    // Link authors
    CALL (entry) {{
      UNWIND $authors as author_id
      MATCH (author: Person {{id: author_id}})
      CREATE (author)-[authored:AUTHORED {{
            time:datetime.transaction(),
            added: $version
        }}]->(entry)
      RETURN
        collect(author.id) as authors
    }}
    // Link references 
    CALL (entry) {{
      UNWIND $references as ref_id
      MATCH (reference: Reference {{id: ref_id}})
      CREATE (reference)-[ref_for:REFERENCE_FOR {{
            time:datetime.transaction(),
            added: $version
        }}]->(entry)
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

def patch_ontology_entry(label: OntologyEntryLabel):
  query = f"""
    MATCH (entry: {label.value}: OntologyEntry {{id: $entry_id}})
    CREATE (patch: OntologyEntryPatch)-[:FOR_ENTRY {{version: $version, time:  datetime.transaction()}}]->(entry)
    SET patch += $params
    WITH entry, patch
    // Link user as contributor
    CALL (patch) {{
      MATCH (user: User {{id: $user_id}})
      MERGE (user)-[c:CONTRIBUTED]->(contributions: UserOntologyContributions)
      CREATE (contributions)-[contributed:CONTRIBUTED {{time:datetime.transaction()}}]->(patch)
    }}
    // Update authors
    CALL (entry) {{
      MATCH (author: Person)
      WHERE author.id IN $authors_added
      CREATE (author)-[:AUTHORED {{added: $version}}]->(entry)
    }}
    CALL (entry) {{
      MATCH (author: Person)-[authored:AUTHORED]->(entry)
      WHERE author.id IN $authors_removed
      SET authored.removed = $version
    }}
    // Update references
    CALL (entry) {{
      MATCH (reference: Reference)
      WHERE reference.id IN $references_added
      CREATE (reference)-[:REFERENCE_FOR {{added: $version}}]->(entry)
    }}
    CALL (entry) {{
      MATCH (reference: Reference)-[ref_for:REFERENCE_FOR]->(entry)
      WHERE reference.id IN $references_removed
      SET ref_for.removed = $version
    }}
  """
  return query


def create_ontology_relationship(
        label: OntologyRelationshipLabel,
        source_label: OntologyEntryLabel,
        target_label: OntologyEntryLabel
):
  try:
    label = OntologyRelationshipLabel(label)
  except KeyError:
    raise ValueError("Only ontology relationship labels can be used")
  try:
      source_label = OntologyEntryLabel(source_label)
  except KeyError:
    raise ValueError("Only ontology entry labels can be used for source")
  try:
      target_label = OntologyEntryLabel(target_label)
  except KeyError:
    raise ValueError("Only ontology entry labels can be used for target")

  query = f"""
    MERGE (c:Counter {{name:'ontology_relationship'}})
    ON CREATE SET c.count = 0
    WITH c
    SET c.count = c.count + 1
    WITH c
    MATCH (source:  {source_label.value} : OntologyEntry {{id:$source_id}}) 
    MATCH (target:  {target_label.value} : OntologyEntry {{id:$target_id}})
    CREATE (source)
        -[:HAS_RELATIONSHIP]->(relationship:{label.value}:OntologyRelationship)
        -[:RELATES_TO]->(target)
    SET relationship.id = c.count
    SET relationship += $attributes
    WITH relationship, source, target
    // Link contributor
    CALL (relationship) {{
      MATCH (user: User {{id: $user_id}})
      MERGE (user)-[c:CONTRIBUTED]->(contributions: UserOntologyContributions)
      CREATE (contributions)-[contributed:CONTRIBUTED {{time:datetime.transaction()}}]->(relationship)
    }}    
    RETURN relationship {{
        .*,
        label: [label IN labels(relationship) WHERE label <> "OntologyRelationship"][0],
        source_id: source.id,
        target_id: target.id,
        source_label: [label IN labels(source) WHERE label <> "OntologyEntry"][0],
        target_label: [label IN labels(target) WHERE label <> "OntologyEntry"][0]
    }}
  """
  return query

def has_path_between_entries(label: OntologyRelationshipLabel):
    query = f"""
        RETURN EXISTS {{
          MATCH
            (source:OntologyEntry {{id: $source_id}})
            (
              (:OntologyEntry)
              -[:HAS_RELATIONSHIP]->(rel:OntologyRelationship)
              -[:RELATES_TO]->(:OntologyEntry)
            ){{1,}}
            (target:OntologyEntry {{id: $target_id}})
          WHERE NONE(r IN rel WHERE EXISTS {{
              MATCH (r)-[:HAS_LIFECYCLE]->(l:OntologyLifecycle)
              WHERE l.removed IS NOT NULL
          }})
        }} AS has_path
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
            match_clause = f"OPTIONAL MATCH (entry:OntologyEntry:{labels[0]} {{id: entry_id}})-[:HAS_LIFECYCLE]->(lifecycle:OntologyLifecycle) WHERE lifecycle.removed IS NULL"
        else:
            # For multiple labels, create a label condition
            label_conditions = " OR ".join([f"entry:{label}" for label in labels])
            match_clause = f"OPTIONAL MATCH (entry:OntologyEntry {{id: entry_id}})-[:HAS_LIFECYCLE]->(lifecycle:OntologyLifecycle) WHERE lifecycle.removed IS NULL AND ({label_conditions})"
    else:
        match_clause = "OPTIONAL MATCH (entry:OntologyEntry {id: entry_id})-[:HAS_LIFECYCLE]->(lifecycle:OntologyLifecycle) WHERE lifecycle.removed IS NULL"

    query = f"""
    UNWIND $entry_ids AS entry_id
    {match_clause}
    RETURN entry_id as id, entry IS NOT NULL AS exists
    ORDER BY id
    """

    return query


def get_entries(
        phases: List[LifecyclePhase] | None = None,
        labels: List[OntologyEntryLabel] | None = None,
        names: List[str] | None = None,
        entry_ids: List[int] | None = None
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
    if not phases:
        phases = list(LifecyclePhase)
    # Build MATCH clause with label filtering
    if labels:
        # get values of label enums as string
        labels = [label.value for label in labels]
        match_clause = f"MATCH (entry:{"|".join(labels)})-[:HAS_LIFECYCLE]->(lifecycle:OntologyLifecycle)"
    else:
        match_clause = "MATCH (entry:OntologyEntry)-[:HAS_LIFECYCLE]->(lifecycle:OntologyLifecycle)"

    # Build WHERE conditions
    where_conditions = []

    # Phase filtering (applies with version context)
    phase_conditions = []
    if LifecyclePhase.DRAFT in phases:
        phase_conditions.append(
            "(lifecycle.drafted <= $version AND "
            "(lifecycle.activated IS NULL OR lifecycle.activated > $version) AND "
            "(lifecycle.deprecated IS NULL OR lifecycle.deprecated > $version)) "
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

    return_clause = """
        OPTIONAL MATCH (patch: OntologyEntryPatch)-[for_entry:FOR_ENTRY]->(entry)
        WHERE for_entry.version <= $version
        WITH entry, patch, for_entry
        ORDER BY for_entry.time 
        WITH entry, collect(patch {.*}) as patches
        RETURN
        entry {
            .*,
            label: [label IN labels(entry) WHERE label <> "OntologyEntry"][0],
            authors: [
                (author: Person)-[authored:AUTHORED]->(entry)
                WHERE
                    authored.added <= $version
                AND 
                    (authored.removed IS NULL OR authored.removed > $version)
                | author.id
            ],
            references: [
                (reference: Reference)-[ref_for:REFERENCE_FOR]->(entry)
                WHERE
                    ref_for.added <= $version
                AND 
                    (ref_for.removed IS NULL or ref_for.removed > $version)
                | reference.id 
            ]
        } as entry,
        patches
        
    """

    query_parts = [match_clause]
    if where_clause:
        query_parts.append(where_clause)
    query_parts.append(return_clause)

    return "\n".join(query_parts)

def get_relationships(
        phases: List[LifecyclePhase],
        labels: List[OntologyRelationshipLabel] | None = None,
        entry_ids: List[int] | None = None,
        source_ids: List[int] | None = None,
        target_ids: List[int] | None = None
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
        match_clause = f"MATCH (relationship:{"|".join(labels)})-[:HAS_LIFECYCLE]->(lifecycle:OntologyLifecycle)"
    else:
        match_clause = "MATCH (relationship:OntologyRelationship)-[:HAS_LIFECYCLE]->(lifecycle:OntologyLifecycle)"

    # Entry ID filtering (parameterized)
    if entry_ids:
        match_clause = match_clause + ", (relationship)--(entry:OntologyEntry) "
    if source_ids:
        if entry_ids:
            raise ValueError("Cannot filter by both entry_ids and source_ids")
        match_clause = match_clause + ", (relationship)<-[:HAS_RELATIONSHIP]-(source:OntologyEntry) "
    if target_ids:
        if entry_ids:
            raise ValueError("Cannot filter by both entry_ids and target_ids")
        match_clause = match_clause + ", (relationship)-[:RELATES_TO]->(target:OntologyEntry) "

    # Phase filtering (applies with version context)
    phase_conditions = []
    if LifecyclePhase.DRAFT in phases:
        phase_conditions.append(
            "(lifecycle.drafted <= $version AND "
            "(lifecycle.activated IS NULL OR lifecycle.activated > $version) AND "
            "(lifecycle.deprecated IS NULL OR lifecycle.deprecated > $version)) "

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
    if entry_ids:
        where_clause = "WHERE entry.id IN $entry_ids "
    if source_ids:
        where_clause = "WHERE source.id in $source_ids "
    if target_ids:
        if where_clause:
            where_clause = where_clause + " AND target.id in $target_ids "
        else:
            where_clause = "WHERE target.id in $target_ids "

    if phase_conditions:
        if where_clause:
            where_clause = where_clause + " AND ( " + " OR ".join(phase_conditions) + " )"
        else:
            where_clause = "WHERE " + " OR ".join(phase_conditions)

    return_clause = """
        WITH relationship
        OPTIONAL MATCH (patch: OntologyRelationshipPatch)-[for_rel:FOR_RELATIONSHIP]->(relationship)
        WHERE for_rel.version <= $version
        WITH relationship, patch, for_rel
        ORDER BY for_rel.time 
        WITH relationship, collect(patch {.*}) as patches            
        MATCH (source: OntologyEntry)-[:HAS_RELATIONSHIP]->(relationship)-[:RELATES_TO]->(target: OntologyEntry)
        RETURN
            relationship {
                .*,
                label: [label IN labels(relationship) WHERE label <> "OntologyRelationship"][0],
                source_id: source.id,
                target_id: target.id,
                source_label: [label IN labels(source) WHERE label <> "OntologyEntry"][0],
                target_label: [label IN labels(target) WHERE label <> "OntologyEntry"][0]
            } as relationship,
            patches
    """
    query_parts = [match_clause]
    if where_clause:
        query_parts.append(where_clause)
    query_parts.append(return_clause)

    return "\n".join(query_parts)
