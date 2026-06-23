MATCH (person: Person) where person.name =~ $name_regex
RETURN
  person {
  .*,
    teams: [(person)-[:IN_TEAM]->(team:Team)|team.id],
    locations: [(person)-[:AT_LOCATION]->(location:Location)|location.id],
    roles: [(person)-[:HAS_ROLE]->(role:PersonRole)|role.id],
    titles:  [(person)-[:HAS_TITLE]->(title:PersonTitle)|title.id]
  }