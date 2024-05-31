MATCH (writer: User {id: $writer})-[:WRITE {authorisation:'AUTHORISED'}]->(team:Team)
WITH writer, collect(team) AS controllers

MERGE (counter: count {name: 'person'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1

MERGE (writer)-[:CREATED]->(up:UserPeople)
CREATE (up)-[created:CREATED {time:datetime.transaction()}]->(person: Person {
  id:          counter.count,
  name:        $name,
  fullname:    $fullname,
  email:       $email,
  mail:        $mail,
  phone:       $phone,
  orcid:       $orcid,
  description: $description
})
WITH
  person,
  controllers,
  [{user:writer.id, time:created.time}] as writes
// Establish controls
CALL {
  WITH person, controllers
  UNWIND controllers AS control_team_id
  MATCH (team:Team {id: control_team_id})
  MERGE (team)-[:CONTROLS]->(tp:TeamPeople)
  CREATE (tp)-[controls:CONTROLS {release: $release, time:datetime.transaction()}]->(person)
  RETURN
    collect({
      team: team.id,
      release: controls.release,
      time: controls.time
    }) AS controls
}
// Update relationships
CALL {
  WITH person
  MATCH (user: User {id: $user})
  CREATE (person)-[is_user:IS_USER {time:datetime.transaction()}]->(user)
  RETURN
    collect(user.id)[0] AS user
}
CALL {
  WITH person
  UNWIND $locations AS location_id
  MATCH (location: Location {id: location_id})
  CREATE (person)-[at_location:AT_LOCATION {time:datetime.transaction()}]->(location)
  RETURN
    collect(location.id) AS locations
}
CALL {
  WITH person
  UNWIND $roles AS role_id
  MATCH (role: PersonRole {id: role_id})
  CREATE (person)-[has_role:HAS_ROLE {time:datetime.transaction()}]->(role)
  RETURN
    collect(role.id) AS roles
}
CALL {
  WITH person
  UNWIND $titles AS title_id
  MATCH (title: Title {id: title_id})
  CREATE (person)-[has_title:HAS_TITLE {time:datetime.transaction()}]->(title)
  RETURN
    collect(title.id) AS titles
}
RETURN
  person {
  .*,
    user: user,
    locations:locations,
    roles:roles,
    titles: titles
  },
  {
    writes: writes,
    controls:controls
  } as controller
