MATCH (person: Person {orcid: $orcid})
WHERE person.id <> $person_id
RETURN count(person) > 0 AS in_use
