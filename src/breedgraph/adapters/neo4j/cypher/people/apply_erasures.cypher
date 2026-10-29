// Applies logged erasures again, e.g. after restoring a backup taken before them.
// Idempotent: identifying data is cleared whether or not the Person is already marked as erased.
// Where the creation time is logged, only the Person created then is erased, never another given its id
// after a restore rolled the id counter back (to the millisecond, the precision both sides keep).
UNWIND $erasures AS erasure
MATCH (person: Person {id: erasure.person_id})
WHERE erasure.created_at IS NULL OR person.recorded_at.epochMillis = datetime(erasure.created_at).epochMillis
OPTIONAL MATCH (person)-[in_team: IN_TEAM]->(:Team)
DELETE in_team
WITH DISTINCT person, erasure
OPTIONAL MATCH (:User)-[is_person: IS_PERSON]->(person)
DELETE is_person
WITH DISTINCT person, erasure
OPTIONAL MATCH (:User)-[claims: CLAIMS]->(person)
DELETE claims
WITH DISTINCT person, erasure
SET
  person.name = null,
  person.institution = null,
  person.orcid = null,
  person.ontology_credit = null,
  person.erased_at = coalesce(person.erased_at, datetime(erasure.erased_at))
RETURN count(DISTINCT person) AS erased
