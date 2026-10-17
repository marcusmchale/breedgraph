from breedgraph.domain.model.controls import ControlledModelLabel
from breedgraph.adapters.neo4j.cypher.query_builders.access import control_access as _control_access

# Persons as the user may see them (see docs/read-access.md and docs/person.md §3), in one of three views:
# - FULL, the record, to read affiliates of a controlling team ($read_teams) and to the linked user ($user_id);
# - ATTRIBUTION, what attribution needs (name, institution, ORCID iD), to those reading it by release only;
# - RESTRICTED, its id only, to anyone else where it is asked for by id, as contacts and contributors refer to
#   Persons by id, anonymous users included (who can't look Persons up by id themselves: the people queries need an
#   account); with the user's own request to be linked, if any, so they can withdraw it.
# Every view names the Person's data controller, so anyone can tell who holds a record about them. Searches leave
# restricted Persons out, so a name does not reveal that a hidden Person has it. A Person without current controls
# is not released to anyone (access.control_access), so it fails closed. The view is returned as a field of the
# record, describing what was built; Python never redacts by it.

PERSON = ControlledModelLabel.PERSON


def _shown(person: str = 'person') -> str:
    """
    Calls setting person_view to how the user sees person, and person_data_controller to the legal entity holding it
    """
    return f"""
        {_control_access(person, PERSON, 'person')}
        WITH *, CASE
          WHEN person_by_read_team OR EXISTS {{ MATCH (:User {{id: $user_id}})-[:IS_PERSON]->({person}) }} THEN 'FULL'
          WHEN person_released THEN 'ATTRIBUTION'
          ELSE 'RESTRICTED'
        END AS person_view
        {_data_controller()}
    """


def _data_controller() -> str:
    """
    A call setting person_data_controller to the legal entity holding the Person controlled by person_teams
    (docs/person.md §2): the current declaration of the root of their team tree, the latest if there are several, or
    null when they are not all in one team tree or its root has declared none
    """
    return """
        CALL (person_teams) {
          OPTIONAL MATCH (team: Team)<-[:INCLUDES_TEAM*0..]-(root: Team)
          WHERE team.id IN person_teams AND NOT (root)<-[:INCLUDES_TEAM]-(:Team)
          WITH collect(DISTINCT root) AS roots
          WITH CASE WHEN size(roots) = 1 THEN roots[0] END AS root
          OPTIONAL MATCH (root)-[:DECLARED {current: true}]->(declaration: LegalEntityDeclaration)
          WITH declaration ORDER BY declaration.declared_at DESC
          RETURN head(collect(declaration {.legal_name, .privacy_contact})) AS person_data_controller
        }
    """


def _person(person: str = 'person') -> str:
    """person in its view, each listing its fields, as old nodes may still hold properties since removed"""
    return f"""CASE person_view
        WHEN 'FULL' THEN {person} {{
          .id, .name, .institution, .orcid, .basis, .informed_attestation, .recorded_by, .recorded_at, .erased_at,
          view: person_view,
          erased: {person}.erased_at IS NOT NULL,
          teams: [({person})-[:IN_TEAM]->(team: Team) | team.id],
          user: head([(user: User)-[:IS_PERSON]->({person}) | user.id]),
          linked: EXISTS {{ MATCH (:User)-[:IS_PERSON]->({person}) }},
          claims: [(claimant: User)-[:CLAIMS]->({person}) | claimant.id],
          data_controller: person_data_controller
        }}
        WHEN 'ATTRIBUTION' THEN {person} {{
          .id, .name, .institution, .orcid,
          view: person_view,
          erased: {person}.erased_at IS NOT NULL,
          teams: [],
          claims: [(claimant: User)-[:CLAIMS]->({person}) WHERE claimant.id = $user_id | claimant.id],
          data_controller: person_data_controller
        }}
        ELSE {person} {{
          .id,
          view: person_view,
          erased: false,
          teams: [],
          claims: [(claimant: User)-[:CLAIMS]->({person}) WHERE claimant.id = $user_id | claimant.id],
          data_controller: person_data_controller
        }}
    END"""


def read_people():
    """The Persons with ids $person_ids, in the view the user has of each"""
    return f"""
        MATCH (person: Person)
        WHERE person.id IN $person_ids
        {_shown()}
        RETURN {_person()} AS person
        ORDER BY person.id
    """


def search_people():
    """
    The Persons the user can see in full or by attribution whose name matches $name_regex, or all of them when it is
    null; restricted Persons are left out
    """
    return f"""
        MATCH (person: Person)
        WHERE $name_regex IS NULL OR person.name =~ $name_regex
        {_shown()}
        WITH person, person_view, person_data_controller WHERE person_view <> 'RESTRICTED'
        RETURN {_person()} AS person
        ORDER BY person.id
    """


def read_people_by_user():
    """
    The Persons linked to the accounts with ids $user_ids, as user_id and person, in the view the user has of each:
    for attributing what accounts did (write stamps, ontology commits) to their Persons, as accounts themselves are
    shown only to their owner and admins of their teams. Accounts without a Person are left out.
    """
    return f"""
        MATCH (account: User)-[:IS_PERSON]->(person: Person)
        WHERE account.id IN $user_ids
        {_shown()}
        RETURN account.id AS user_id, {_person()} AS person
    """
