MATCH
  (person: Person {id: $person_id})
OPTIONAL MATCH
  (person)<-[writes:CREATED|UPDATED]-(),
  (person)<-[controls:CONTROLS]-(),
  (person)-[is_user:IS_USER]->(),
  (person)-[at_location:AT_LOCATION]->(),
  (person)-[has_role:HAS_ROLE]->(),
  (person)-[has_role:HAS_TITLE]->()
DELETE person, writes, controls, is_user, at_location, has_role, has_title