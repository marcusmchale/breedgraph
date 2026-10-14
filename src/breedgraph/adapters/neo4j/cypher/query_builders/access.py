from breedgraph.domain.model.controls import ControlledModelLabel


def visible(entity: str, label: ControlledModelLabel, alias: str) -> str:
    """
    A call setting alias to whether the user can read entity: with no current controls, when the least of its current
    controls' releases is at least $minimum_release, or when a team in $read_teams controls it
    """
    return f"""
        CALL ({entity}) {{
          OPTIONAL MATCH ({entity})<-[:CONTROLS]-(control:Control)<-[:CONTROLS]-(:Team{label.plural})<-[:CONTROLS]-(team:Team)
          WITH team, control
          ORDER BY team.id, control.sequence DESC
          WITH team, collect(control)[0] AS control
          WITH collect(
            CASE WHEN team IS NOT NULL AND NOT coalesce(control.ended, false) THEN {{team: team.id, release: control.release}} END
          ) AS controls
          RETURN size(controls) = 0
            OR any(c IN controls WHERE c.team IN $read_teams)
            OR reduce(least = 2, c IN controls | CASE WHEN c.release < least THEN c.release ELSE least END) >= $minimum_release
            AS {alias}
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
