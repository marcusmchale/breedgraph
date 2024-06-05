MATCH (person: Person {id: $person_id})
RETURN
    [
      (person)<-[write:CREATED|UPDATED]-(:UserPeople)<-[:CREATED]-(user:User) |
      {user:user.id, time: write.time}
    ] as writes,
    [
      (person)<-[controls:CONTROLS]-(:TeamPeople)<-[:CONTROLS]-(team:Team) |
      {team: team.id, release: controls.release, time: controls.time}
    ] as controls