from breedgraph.domain.model.controls import ControlledModelLabel
from breedgraph.adapters.neo4j.cypher.query_builders.access import visible as _visible

# Persons as the user may see them (see docs/read-access.md and docs/person.md). A Person the user can read, or is
# linked to ($user_id), is returned in full. One they cannot read is a placeholder where it is asked for by id, as
# contacts and contributors refer to Persons by id, for anonymous users too: its id, lawful basis and whether it was
# erased, with no name (GraphQL's Person.restricted), and the user's own request to be linked, if any, so they can
# withdraw it. Searches leave such Persons out, so a name does not reveal that a hidden Person has it.

PERSON = ControlledModelLabel.PERSON


def _shown(person: str = 'person') -> str:
    """A call setting person_shown to whether the user can read person or is linked to it"""
    return f"""
        {_visible(person, PERSON, 'person_readable')}
        WITH *, person_readable OR EXISTS {{ MATCH (:User {{id: $user_id}})-[:IS_PERSON]->({person}) }} AS person_shown
    """


def _person(person: str = 'person') -> str:
    return f"""CASE WHEN person_shown THEN {person} {{
          .*,
          teams: [({person})-[:IN_TEAM]->(team: Team) | team.id],
          user: head([(user: User)-[:IS_PERSON]->({person}) | user.id]),
          claims: [(claimant: User)-[:CLAIMS]->({person}) | claimant.id]
        }} ELSE {person} {{
          .id, .basis, .informed_attestation, .erased_at,
          teams: [],
          claims: [(claimant: User)-[:CLAIMS]->({person}) WHERE claimant.id = $user_id | claimant.id]
        }} END"""


def read_people():
    """The Persons with ids $person_ids, a placeholder for those the user cannot read"""
    return f"""
        MATCH (person: Person)
        WHERE person.id IN $person_ids
        {_shown()}
        RETURN {_person()} AS person
        ORDER BY person.id
    """


def search_people():
    """The Persons the user can read, or is linked to, whose name matches $name_regex, or all of them when it is null"""
    return f"""
        MATCH (person: Person)
        WHERE $name_regex IS NULL OR person.name =~ $name_regex
        {_shown()}
        WITH person, person_shown WHERE person_shown
        RETURN {_person()} AS person
        ORDER BY person.id
    """
