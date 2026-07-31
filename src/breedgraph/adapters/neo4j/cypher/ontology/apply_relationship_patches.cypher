UNWIND $patches AS item
MATCH (relationship:OntologyRelationship {id: item.relationship_id})
SET relationship += item.patch

