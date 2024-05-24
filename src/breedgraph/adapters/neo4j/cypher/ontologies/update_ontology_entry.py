from src.breedgraph.domain.model.ontologies import OntologyEntry

def update_ontology_entry(label):
  if not label in [i.__name__ for i in OntologyEntry.__subclasses__()]:
    raise ValueError("Only ontology entry labels can be used")

  query = f"""
    MATCH (entry: OntologyEntry {{id: $entry_id}})
    SET
      entry.name = $name,
      entry.abbreviation = $abbreviation,
      entry.synonyms = $synonyms,
      entry.description = $description,
      entry.type = $type,
      entry.trait = $trait,
      entry.method = $method,
      entry.scale = $scale
    WITH entry
    // Link parents
    CALL {{
      WITH entry
      MATCH (parent: OntologyEntry)<-[child_of:CHILD_OF]-(entry)
      WHERE NOT parent.id in $parents
      DELETE child_of
      WITH DISTINCT entry
      UNWIND $parents as parent_id
      MATCH (parent: OntologyEntry {{id: parent_id}})
      MERGE (parent)<-[child_of:CHILD_OF]-(entry)
      ON CREATE SET child_of.time = datetime.transaction()
      RETURN
        collect(parent.id) as parents
    }}
    // Link authors
    CALL {{
      WITH entry
      MATCH (author: Person)-[authored:AUTHORED]->(entry)
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
      MATCH (reference: Reference)-[ref_for:REFERENCE_FOR]->(entry)
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
    // Link subjects
    CALL {{
      WITH entry
      MATCH (subject: Subject)<-[for_subject:FOR_SUBJECT]-(entry)
      WHERE NOT subject.id in $subjects
      DELETE for_subject
      WITH DISTINCT entry        
      UNWIND $subjects as subject_id
      MATCH (subject: OntologyEntry {{id: subject_id}})
      MERGE (subject)<-[for_subject:FOR_SUBJECT]-(entry)
      ON CREATE SET for_subject.time = datetime.transaction() 
      RETURN
        collect(subject.id) as subjects
    }}
    // Link trait
    CALL {{
      WITH entry
      MATCH (trait: Trait)<-[described_by:DESCRIBED_BY]-(entry)
      WHERE NOT trait.id = $trait
      DELETE described_by
      WITH DISTINCT entry        
      MATCH (trait: Trait {{id: $trait}})
      MERGE (trait)<-[described_by:DESCRIBED_BY]-(entry)
      ON CREATE SET described_by.time = datetime.transaction() 
      RETURN
        collect(trait.id)[0] as trait
    }}    
    // Link condition
    CALL {{
      WITH entry
      MATCH (condition: Condition)<-[described_by:DESCRIBED_BY]-(entry)
      WHERE NOT condition.id = $condition
      DELETE described_by
      WITH DISTINCT entry        
      MATCH (condition: Condition {{id: $condition}})
      MERGE (condition)<-[described_by:DESCRIBED_BY]-(entry)
      ON CREATE SET described_by.time = datetime.transaction() 
      RETURN
        collect(condition.id)[0] as condition
    }}
    // Link exposure
    CALL {{
      WITH entry
      MATCH (exposure: Exposure)<-[described_by:DESCRIBED_BY]-(entry)
      WHERE NOT exposure.id = $exposure
      DELETE described_by
      WITH DISTINCT entry        
      MATCH (exposure: Exposure {{id: $exposure}})
      MERGE (exposure)<-[described_by:DESCRIBED_BY]-(entry)
      ON CREATE SET described_by.time = datetime.transaction() 
      RETURN
        collect(exposure.id)[0] as exposure
    }}
    // Link method
    CALL {{
      WITH entry
      MATCH (method: Method)-[method_of:METHOD_OF]->(entry)
      WHERE NOT method.id = $method
      DELETE method_of
      WITH DISTINCT entry        
      MATCH (method: Method {{id: $method}})
      MERGE (method)<-[method_of:METHOD_OF]-(entry)
      ON CREATE SET method_of.time = datetime.transaction() 
      RETURN
        collect(method.id)[0] as method
    }}
    // Link scale
    CALL {{
      WITH entry
      MATCH (scale: Scale)-[scale_of:SCALE_OF]->(entry)
      WHERE NOT scale.id = $scale
      DELETE scale_of
      WITH DISTINCT entry        
      MATCH (scale: Scale {{id: $scale}})
      MERGE (scale)<-[scale_of:SCALE_OF]-(entry)
      ON CREATE SET scale_of.time = datetime.transaction() 
      RETURN
        collect(scale.id)[0] as scale
    }}
    // Link categories
    CALL {{
      WITH entry
      MATCH (category: Category)-[category_of:CATEGORY_OF]->(entry)
      WHERE NOT category.id in $categories
      DELETE category_of
      WITH DISTINCT entry        
      UNWIND $categories as category_id
      MATCH (category: Category {{id: category_id}})
      MERGE (category)-[category_of:CATEGORY_OF]->(entry)
      ON CREATE SET category_of.time = datetime.transaction() 
      RETURN
        collect(category.id) as categories
    }}
    RETURN entry {{
      .*,
      labels: labels(entry),
      parents: parents,
      children: [(entry)<-[:CHILD_OF]-(e:OntologyEntry) | e.id],
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