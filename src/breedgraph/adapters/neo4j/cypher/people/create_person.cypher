MERGE (counter: Counter {name: 'person'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (person: Person {
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
  person
CALL {
  WITH person
  MATCH (user: User {id: $user})
  CREATE (person)-[is_user:IS_USER {time:datetime.transaction()}]->(user)
  RETURN
    collect(user.id)[0] AS user
}
CALL {
  WITH person
  MATCH (team: Team) WHERE team.id IN $teams
  CREATE (person)-[in_team:IN_TEAM {time:datetime.transaction()}]->(team)
  RETURN
    collect(team.id) AS teams
}
CALL {
  WITH person
  MATCH (location: Location) WHERE location.id IN $locations
  CREATE (person)-[at_location:AT_LOCATION {time:datetime.transaction()}]->(location)
  RETURN
    collect(location.id) AS locations
}
CALL {
  WITH person
  MATCH (role: PersonRole) WHERE role.id IN $roles
  CREATE (person)-[has_role:HAS_ROLE {time:datetime.transaction()}]->(role)
  RETURN
    collect(role.id) AS roles
}
CALL {
  WITH person
  MATCH (title: Title) WHERE title.id IN $titles
  CREATE (person)-[has_title:HAS_TITLE {time:datetime.transaction()}]->(title)
  RETURN
    collect(title.id) AS titles
}
RETURN
  person {
    .*,
    user: user,
    teams: teams,
    locations: locations,
    roles: roles,
    titles: titles
  }