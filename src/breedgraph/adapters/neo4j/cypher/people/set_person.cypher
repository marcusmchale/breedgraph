MATCH
  (person: Person {id: $id})
SET
  person.name = $name,
  person.fullname = $fullname,
  person.email = $email,
  person.mail = $mail,
  person.phone = $phone,
  person.orcid = $orcid,
  person.description = $description
// Update user
WITH person
CALL {
  WITH person
  MATCH (person)-[is_user:IS_USER]->(user:User)
    WHERE NOT user.id = $user
  DELETE is_user
}
CALL {
  WITH person
  MATCH (user: User {id: $user})
  MERGE (person)-[is_user:IS_USER]->(user)
  ON CREATE SET is_user.time = datetime.transaction()
}
//Update teams
CALL {
  WITH person
  MATCH (person)-[in_team:IN_TEAM]->(team:Team)
    WHERE NOT team.id IN $teams
  DELETE in_team
}
CALL {
  WITH person
  MATCH (team: Team) WHERE team.id IN $teams
  MERGE (person)-[in_team:IN_TEAM]->(team)
  ON CREATE SET in_team.time = datetime.transaction()
}
//Update roles
CALL {
  WITH person
  MATCH (person)-[has_role:HAS_ROLE]->(role:PersonRole)
    WHERE NOT role.id IN $roles
  DELETE has_role
}
CALL {
  WITH person
  MATCH (role: PersonRole) WHERE role.id IN $roles
  MERGE (person)-[has_role:HAS_ROLE]->(role)
  ON CREATE SET has_role.time = datetime.transaction()
}
//Update titles
CALL {
  WITH person
  MATCH (person)-[has_title:HAS_TITLE]->(title:PersonTitle)
    WHERE NOT title.id IN $titles
  DELETE has_title
}
CALL {
  WITH person
  MATCH (title: PersonTitle) WHERE title.id IN $titles
  MERGE (person)-[has_title:HAS_TITLE]->(title)
  ON CREATE SET has_title.time = datetime.transaction()
}
// Update locations
CALL {
  WITH person
  MATCH (person)-[at_location:AT_LOCATION]->(location:Location)
    WHERE NOT location.id IN $locations
  DELETE at_location
}
CALL {
  WITH person
  MATCH (location: Location) WHERE location.id IN $locations
  MERGE (person)-[at_location:AT_LOCATION]->(location)
  ON CREATE SET at_location.time = datetime.transaction()
}
RETURN NULL