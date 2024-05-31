MATCH (person: Person {id: $person_id})
RETURN
  person {
  .*,
    user: [(person)-[:IS_USER]->(user:User)| user.id][0],
    locations: [(person)-[:AT_LOCATION]->(location:Location)|location.id],
    roles: [(person)-[:HAS_ROLE]->(role:PersonRole)|role.id],
    titles:  [(person)-[:AT_LOCATION]->(title:PersonTitle)|title.id]
  },
  controller {
    writes: [
      (person)<-[write:CREATED|UPDATED]-(:UserPeople)<-[:CREATED]-(user:User) |
      {user:user.id, time: write.time}
    ],
    controls: [
      (person)<-[controls:CONTROLS]-(:TeamPeople)<-[:CONTROLS]-(team:Team) |
      {team: team.id, release: controls.release, time: controls.time}
    ]
  }
