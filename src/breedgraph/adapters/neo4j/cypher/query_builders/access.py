from breedgraph.domain.model.controls import ControlledModelLabel

# The query builders compose Cypher text so that read checks like these are written once. The rule that keeps that
# safe and cacheable: interpolate only code constants (variable names, labels from enums, relationship types, field
# names checked against a fixed set) and the output of other builders, never a value from a request. Every value is a
# $parameter. Then each builder gives the same text on every call, Neo4j caches its plan, and nothing a user sends
# can change the query. tests/breedgraph/integration/test_query_builders_compile.py plans every builder's output.


def _current_controls(entity: str, label: ControlledModelLabel) -> str:
    """
    Within a call on entity, controls as the current control of each team controlling it, {team, release}: a team's
    latest control, while it is not ended
    """
    return f"""
          OPTIONAL MATCH ({entity})<-[:CONTROLS]-(control:Control)<-[:CONTROLS]-(:Team{label.plural})<-[:CONTROLS]-(team:Team)
          WITH team, control
          ORDER BY team.id, control.sequence DESC
          WITH team, collect(control)[0] AS control
          WITH collect(
            CASE WHEN team IS NOT NULL AND NOT coalesce(control.ended, false) THEN {{team: team.id, release: control.release}} END
          ) AS controls
    """


_LEAST_RELEASE = "reduce(least = 2, c IN controls | CASE WHEN c.release < least THEN c.release ELSE least END)"


def least_release(entity: str, label: ControlledModelLabel, alias: str) -> str:
    """
    A call setting alias to entity's release as Controller.release gives it and visible() compares it: the least of
    its current controls' releases, PUBLIC when it has none
    """
    return f"""
        CALL ({entity}) {{
          {_current_controls(entity, label)}
          RETURN {_LEAST_RELEASE} AS {alias}
        }}
    """


def visible(entity: str, label: ControlledModelLabel, alias: str) -> str:
    """
    A call setting alias to whether the user can read entity: with no current controls, when the least of its current
    controls' releases is at least $minimum_release, or when a team in $read_teams controls it
    """
    return f"""
        CALL ({entity}) {{
          {_current_controls(entity, label)}
          RETURN size(controls) = 0
            OR any(c IN controls WHERE c.team IN $read_teams)
            OR {_LEAST_RELEASE} >= $minimum_release
            AS {alias}
        }}
    """


def signed_in_only(persons: str) -> str:
    """
    persons, a list of Persons or of references to them (contacts, contributions), for signed-in users only: anonymous
    users ($signed_in false) get an empty list. Persons are released at most to registered users, so anonymous users
    could read none of them, and are not shown placeholders either (docs/read-access.md, rule 2)
    """
    return f"CASE WHEN $signed_in THEN {persons} ELSE [] END"


def contributions(entity: str) -> str:
    """The contributions to entity, each {person, roles}, for signed-in users only (see signed_in_only)"""
    return signed_in_only(
        f"[({entity})<-[contributed:CONTRIBUTED_TO]-(person:Person) | {{person: person.id, roles: coalesce(contributed.roles, [])}}]"
    )


def control_access(entity: str, label: ControlledModelLabel, prefix: str) -> str:
    """
    A call setting, as visible() decides them but apart: {prefix}_teams, the ids of the teams currently controlling
    entity; {prefix}_by_read_team, whether one of them is in $read_teams; and {prefix}_released, whether the least of
    its current controls' releases is at least $minimum_release. Unlike visible(), an entity without current controls
    is not released, for entities whose reads must fail closed (Persons, see query_builders.people)
    """
    return f"""
        CALL ({entity}) {{
          {_current_controls(entity, label)}
          RETURN [c IN controls | c.team] AS {prefix}_teams,
            any(c IN controls WHERE c.team IN $read_teams) AS {prefix}_by_read_team,
            size(controls) > 0 AND {_LEAST_RELEASE} >= $minimum_release AS {prefix}_released
        }}
    """


def visible_members(root: str, label: ControlledModelLabel, edge: str, alias: str) -> str:
    """A call setting alias to the ids of the nodes of root's tree, root included, that the user can read"""
    return f"""
        CALL ({root}) {{
          MATCH ({root})-[:{edge}*0..]->(member:{label.label})
          WITH DISTINCT member
          {visible('member', label, 'member_visible')}
          WITH member WHERE member_visible
          RETURN collect(member.id) AS {alias}
        }}
    """


def tree_links(node: str, root: str, label: ControlledModelLabel, edge: str, visible_ids: str) -> dict[str, str]:
    """
    Expressions for node's place in its tree as the user sees it, hidden nodes skipped as the repository's redaction
    reconnects them: its nearest ancestor the user can read, or the root, which is always kept, and its nearest
    descendants the user can read, along paths through hidden nodes only
    """
    return {
        'parent': f"""reduce(nearest = null, link IN [
              path = ({node})<-[:{edge}*1..]-(ancestor:{label.label})
              WHERE ancestor.id IN {visible_ids} OR ancestor = {root} | [length(path), ancestor.id]
            ] | CASE WHEN nearest IS NULL OR link[0] < nearest[0] THEN link ELSE nearest END)[1]""",
        'children': f"""apoc.coll.toSet([
              path = ({node})-[:{edge}*1..]->(descendant:{label.label})
              WHERE descendant.id IN {visible_ids} AND none(between IN nodes(path)[1..-1] WHERE between.id IN {visible_ids})
              | descendant.id
            ])""",
    }


def readable(entity: str, label: ControlledModelLabel) -> str:
    """
    A predicate for whether the user can read entity, as visible() decides it, written with EXISTS subqueries only so
    it can stand where calls cannot, such as in a quantified path pattern: a team's current control is its latest,
    and the team controls the entity while that control is not ended
    """
    current = (
        f"NOT coalesce(control.ended, false) AND NOT EXISTS {{ "
        f"MATCH ({entity})<-[:CONTROLS]-(newer:Control)<-[:CONTROLS]-(team_node) WHERE newer.sequence > control.sequence }}"
    )
    controls = f"({entity})<-[:CONTROLS]-(control:Control)<-[:CONTROLS]-(team_node:Team{label.plural})"
    return f"""(
          NOT EXISTS {{ MATCH {controls} WHERE {current} }}
          OR EXISTS {{ MATCH {controls}<-[:CONTROLS]-(team:Team) WHERE team.id IN $read_teams AND {current} }}
          OR NOT EXISTS {{ MATCH {controls} WHERE control.release < $minimum_release AND {current} }}
        )"""
