MATCH (write_user: User {id: $write_user})
MATCH (person: Person {id: $person_id})

// Track and timestamp updates
MERGE (write_user)-[:UPDATED]->(pu:PeopleUpdates)
CREATE (pu)-[:UPDATED {time:datetime.transaction()}]-(person)
SET
  person.name = $name,
  person.fullname = $fullname,
  person.email = $email,
  person.mail = $mail,
  person.phone = $phone,
  person.orcid = $orcid,
  person.description = $description
// Update relationships
CALL {
  WITH person
  MATCH (person)-[at_location:AT_LOCATION]->(location:Location)
  WHERE NOT location.id IN $locations
  DELETE at_location
  WITH DISTINCT person
  UNWIND $locations as location_id
  MATCH (location: Location {id: location_id})
  MERGE (person)-[at_location:AT_LOCATION]->(location)
  ON CREATE SET at_location.time = datetime.transaction()
  RETURN
    collect(location.id) as locations
}
CALL {
  WITH person
  MATCH (person)-[has_role:HAS_ROLE]->(role:PersonRole)
  WHERE NOT role.id IN $roles
  DELETE has_role
  WITH DISTINCT person
  UNWIND $roles as role_id
  MATCH (role: PersonRole {id: role_id})
  MERGE (person)-[has_role:HAS_ROLE]->(role)
  ON CREATE SET has_role.time = datetime.transaction()
  RETURN
    collect(role.id) as roles
}
CALL {
  WITH person
  MATCH (person)-[has_title:HAS_TITLE]->(title:PersonTitle)
  WHERE NOT title.id IN $titles
  DELETE has_title
  WITH DISTINCT person
  UNWIND $titles as title_id
  MATCH (title: PersonTitle {id: title_id})
  MERGE (person)-[has_title:HAS_TITLE]->(title)
  ON CREATE SET has_title.time = datetime.transaction()
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
