MATCH (admin: User {id: $admin})
MERGE (counter:Counter {name: 'team'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (admin)-[affiliation: ADMIN {authorisation:'AUTHORISED', heritable:$heritable}]-> (team: Team {
  id: counter.count,
  name: $name,
  name_lower: $name_lower,
  fullname: $fullname
})
RETURN team {
  . *,
  affiliations: {
    ADMIN : [affiliation {.*, id: admin.id}]
  }
}