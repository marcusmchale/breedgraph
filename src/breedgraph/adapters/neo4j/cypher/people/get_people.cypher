MATCH (person: Person)
RETURN
  person {
  .*,
    user: [(person)-[:IS_USER]->(user:User)| user.id][0],
    teams: [(team)-[:IN_TEAM]->(team:Team)|team.id],
    locations: [(person)-[:AT_LOCATION]->(location:Location)|location.id],
    roles: [(person)-[:HAS_ROLE]->(role:PersonRole)|role.id],
    titles:  [(person)-[:AT_LOCATION]->(title:PersonTitle)|title.id],
    controller: {
      controls: [
        (person)<-[controls:CONTROLS]-(:TeamPeople)<-[:CONTROLS]-(team:Team) |
        {team: team.id, release: controls.release, time: controls.time}
      ],
      writes: [
        (person)<-[write:CREATED|UPDATED]-(:UserPeople)<-[:CREATED]-(user:User) |
        {user:user.id, time: write.time}
      ]
    }
  }
