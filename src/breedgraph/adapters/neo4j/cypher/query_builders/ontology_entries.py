from src.breedgraph.domain.model.ontology import OntologyEntry

def create_ontology_entry(label):

  if not label in [e.label for e in OntologyEntry.__subclasses__()]:
    raise ValueError("Only ontology entry labels can be used")

  query = f"""
    MATCH (v:OntologyVersion {{id: $version_id}})
    MERGE (c:Counter {{name:'ontology_entry'}})
    ON CREATE SET c.count = 0
    SET c.count = c.count + 1
    CREATE (entry: {label}: OntologyEntry {{
      id: c.count,
      name: $name,
      abbreviation: $abbreviation,
      synonyms: $synonyms,
      description: $description,
      type: $type
    }})-[:IN_VERSION]->(v)
    WITH entry
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
      labels: labels(entry),
      authors: authors,
      references: references
    }}
  """
  return query


def update_ontology_entry(label):
  if not label in [e.label for e in OntologyEntry.__subclasses__()]:
    raise ValueError("Only ontology entry labels can be used")

  query = f"""
    MATCH (entry: OntologyEntry {{id: $entry_id}})
    SET
      entry.name = $name,
      entry.abbreviation = $abbreviation,
      entry.synonyms = $synonyms,
      entry.description = $description,
      entry.type = $type
    WITH entry
    // Link authors
    CALL {{
      WITH entry
      OPTIONAL MATCH (author: Person)-[authored:AUTHORED]->(entry)
      WHERE NOT author.id in $authors
      DELETE authored
      WITH DISTINCT entry
      UNWIND $authors as author_id
      MATCH (author: Person {{id: author_id}})
      MERGE (author)-[authored:AUTHORED]->(entry)
      ON CREATE SET authored.time = datetime.transaction()
      RETURN
        collect(author.id) as authors
    }}
    // Link References
    CALL {{
      WITH entry
      OPTIONAL MATCH (reference: Reference)-[ref_for:REFERENCE_FOR]->(entry)
      WHERE NOT reference.id in $references
      DELETE ref_for
      WITH DISTINCT entry
      UNWIND $references as ref_id
      MATCH (reference: Reference {{id: ref_id}})
      MERGE (reference)-[ref_for:REFERENCE_FOR]->(entry)
      ON CREATE SET ref_for.time = datetime.transaction()      
      RETURN
        collect(reference.id) as references
    }}   
    RETURN entry {{
      .*,
      labels: labels(entry),
      authors: authors,
      references: references
    }}       
  """
  return query