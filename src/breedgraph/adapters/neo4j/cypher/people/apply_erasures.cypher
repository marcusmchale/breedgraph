// Applies logged erasures again, e.g. after restoring a backup taken before them.
// Idempotent: identifying data is cleared whether or not the Person is already marked as erased.
UNWIND $erasures AS erasure
MATCH (person: Person {id: erasure.person_id})
OPTIONAL MATCH (person)-[in_team: IN_TEAM]->(:Team)
DELETE in_team
WITH DISTINCT person, erasure
OPTIONAL MATCH (:User)-[is_person: IS_PERSON]->(person)
DELETE is_person
WITH DISTINCT person, erasure
SET
  person.name = null,
  person.orcid = null,
  person.erased_at = coalesce(person.erased_at, datetime(erasure.erased_at))
RETURN count(DISTINCT person) AS erased
