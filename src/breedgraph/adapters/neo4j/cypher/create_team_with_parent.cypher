MERGE (counter:Counter {name: 'team'})
  ON CREATE SET counter.count = 0
WITH counter
MATCH (parent: Team {id: $parent})
SET counter.count = counter.count + 1
CREATE (team: Team {
  id: counter.count,
  name: $name,
  name_lower: $name_lower,
  fullname: $fullname
})-[:CONTRIBUTES_TO]->(parent)
RETURN team {
  .*,
  parent: parent.id,
  children: [],
  readers: coalesce([(team)-[:CONTRIBUTES_TO*]->(:Team)<-[:READ {authorisation:"AUTHORISED", heritable:true}]-(reader:User) | reader.id], []),
  writers: [],
  admins: coalesce([(team)-[:CONTRIBUTES_TO*]->(:Team)<-[:ADMIN {authorisation:"AUTHORISED", heritable:true}]-(admin:User) | admin.id], []),
  requests: []
}