

MATCH (person: Person)
RETURN person {
  .*,
  locations: [(person)-[:AT_LOCATION]->(location:Location)|location.id],
  roles: [(person)-[:HAS_ROLE]->(role:PersonRole)|role.id],
  titles:  [(person)-[:AT_LOCATION]->(title:PersonTitle)|title.id]
}
