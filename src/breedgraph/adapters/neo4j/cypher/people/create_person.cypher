MATCH (write_user: User {id: $write_user})

MERGE (counter: count {name: 'person'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1

// The user that created the record and the time of creation are both stored
MERGE (write_user)-[:CREATED]->(pw:PeopleWrites)
CREATE (pw)-[:CREATED {time:datetime.transaction()}]->(person: Person {
  id:          counter.count,
  name:        $name,
  fullname:    $fullname,
  email:       $email,
  mail:        $mail,
  phone:       $phone,
  orcid:       $orcid,
  description: $description
})
WITH person
// During creation we establish access control
CALL {
  WITH person
  UNWIND $control_teams as control_team_id
  MATCH (team:Team {id: control_team_id})
  MERGE (team)-[:CONTROLS]->(pc:PeopleControl)
  CREATE (pc)-[:CONTROLS]->(person)
}
// Update relationships
CALL {
  WITH person
  MATCH (user: User {id: $user})
  CREATE (person)-[is_user:IS_USER {time:datetime.transaction()}]->(user)
  RETURN
    collect(user.id)[0] as user
}
CALL {
  WITH person
  UNWIND $locations as location_id
  MATCH (location: Location {id: location_id})
  CREATE (person)-[at_location:AT_LOCATION {time:datetime.transaction()}]->(location)
  RETURN
    collect(location.id) as locations
}
CALL {
  WITH person
  UNWIND $roles as role_id
  MATCH (role: PersonRole {id: role_id})
  CREATE (person)-[has_role:HAS_ROLE {time:datetime.transaction()}]->(role)
  RETURN
    collect(role.id) as roles
}
CALL {
  WITH person
  UNWIND $titles as location_id
  MATCH (title: Title {id: title_id})
  CREATE (person)-[has_title:HAS_TITLE {time:datetime.transaction()}]->(title)
  RETURN
    collect(title.id) as titles
}
RETURN person {
  .*,
  user: user,
  locations:locations,
  roles:roles,
  titles: titles
}
