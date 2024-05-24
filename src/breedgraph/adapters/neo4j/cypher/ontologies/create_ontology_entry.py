from src.breedgraph.domain.model.ontologies import OntologyEntry

def create_ontology_entry(label):
  if not label in [i.__name__ for i in OntologyEntry.__subclasses__()]:
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
    // Link parents
    CALL {{
      WITH entry
      UNWIND $parents as parent_id
      MATCH (parent: OntologyEntry {{id: parent_id}})
      CREATE (parent)<-[:CHILD_OF {{time:datetime.transaction()}}]-(entry)
      RETURN
        collect(parent.id) as parents
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
    // Link subjects
    CALL {{
        WITH entry
        UNWIND $subjects as subject_id
        MATCH (subject: Subject {{id: subject_id}})
        CREATE (subject)<-[:OF_SUBJECT {{time:datetime.transaction()}}]-(entry)
        RETURN
          collect(subject.id) as subjects
    }}
    // Link trait
    CALL {{
        WITH entry
        MATCH (trait: Trait {{id: $trait}})
        CREATE (trait)-[:DESCRIBED_BY {{time:datetime.transaction()}}]->(entry)
        RETURN
          collect(trait.id)[0] as trait
    }}  
    // Link condition
    CALL {{
        WITH entry
        MATCH (condition: Condition {{id: condition}})
        CREATE (condition)-[:DESCRIBED_BY {{time:datetime.transaction()}}]->(entry)
        RETURN
          collect(condition.id)[0] as condition
    }}
    // Link exposure
    CALL {{
        WITH entry
        MATCH (exposure: Exposure {{id: exposure}})
        CREATE (exposure)-[:DESCRIBED_BY {{time:datetime.transaction()}}]->(entry)
        RETURN
          collect(exposure.id)[0] as exposure
    }}
    // Link method
    CALL {{
        WITH entry
        MATCH (method: OntologyEntry {{id: $method}})
        CREATE (method)-[:METHOD_OF {{time:datetime.transaction()}}]->(entry)
        RETURN
          collect(method.id)[0] as method
    }}
    // Link scale
    CALL {{
        WITH entry
        MATCH (scale: OntologyEntry {{id: $scale}})
        CREATE (scale)-[:SCALE_OF {{time:datetime.transaction()}}]->(entry)
        RETURN
          collect(scale.id)[0] as scale
    }}
    // Link categories
    CALL {{
        WITH entry
        UNWIND $categories as category_id
        MATCH (category: Category {{id: category_id}})
        CREATE (category)-[:CATEGORY_OF {{time:datetime.transaction()}}]->(entry)
        RETURN
          collect(category.id) as categories
    }}
    
    RETURN entry {{
      .*,
      labels: labels(entry),
      parents: parents,
      children: [],
      authors: authors,
      references: references,
      subjects: subjects,
      trait: trait,
      condition: condition,
      exposure: exposure,
      method: method,
      scale: scale,
      categories: categories
    }}
  """
  return query
