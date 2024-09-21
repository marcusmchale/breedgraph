from src.breedgraph.domain.model.ontology import OntologyEntry, OntologyRelationshipLabel

def create_ontology_entry(label):

  if not label in [e.label for e in OntologyEntry.__subclasses__()]:
    raise ValueError("Only ontology entry labels can be used")

  query = f"""
    MATCH (v:OntologyVersion {{id: $version_id}})
    MERGE (c:Counter {{name:'ontology_entry'}})
    ON CREATE SET c.count = 0
    SET c.count = c.count + 1
    CREATE (entry: {label}: OntologyEntry {{id: c.count}})-[:IN_VERSION]->(v)
    SET entry += $params
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
    SET entry += $params
    WITH entry
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

def create_ontology_edge(label):
  if not label in OntologyRelationshipLabel:
    raise ValueError("Only ontology relationship labels can be used")

  query = f"""
    MATCH (source: OntologyEntry {{id:$source_id}})
    MATCH (sink: OntologyEntry {{id:$sink_id}})
    CREATE (source)-[:{label.name} {{rank: $rank}}]->(sink)
  """
  return query

def delete_ontology_edge(label):
  if not label in OntologyRelationshipLabel:
    raise ValueError("Only ontology relationship labels can be used")
  query = f"""
    MATCH (source: OntologyEntry {{id:$source_id}})-[relationship :{label.name}]->(sink: OntologyEntry {{id:$sink_id}})
    DELETE relationship
  """
  return query