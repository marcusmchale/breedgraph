

readers: coalesce([(team)<-[:READ {authorisation:"AUTHORISED"}]-(reader:User) | reader.id], []) +
       [(team)-[:CONTRIBUTES_TO*]->(:Team)<-[:READ {authorisation:"AUTHORISED", heritable:true}]-(reader:User) | reader.id],

MATCH (user: User {id: $read_user)-[:READ]->(team:Team)


MATCH (person: Person {id: $person_id})
RETURN person {
  .*,
  locations: [(person)-[:AT_LOCATION]->(location:Location)|location.id],
  roles: [(person)-[:HAS_ROLE]->(role:PersonRole)|role.id],
  titles:  [(person)-[:AT_LOCATION]->(title:PersonTitle)|title.id]
}
