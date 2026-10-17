from breedgraph.domain.model.controls import ControlledModelLabel
from breedgraph.adapters.neo4j.cypher.query_builders.access import readable

# Units as the user may see them, without reading whole unit graphs. A unit the user can read is returned in full, its
# parents and children being the nearest readable units along paths through hidden units only, as the repository's
# redaction reconnects them; a unit graph's root is kept even when hidden, so a hidden root can be a unit's parent. A
# hidden root is returned as a placeholder, its id and a REDACTED name, keeping its readable descendants as children,
# when it was asked for directly or holds units the user can read. Any other hidden unit asked for by id is returned
# as a bare placeholder.

UNIT = ControlledModelLabel.UNIT
EDGE = 'INCLUDES_UNIT'


def _readable(unit: str) -> str:
    return readable(unit, UNIT)


def _children(unit: str = 'unit') -> str:
    """A call collecting the nearest readable units below unit, as children"""
    return f"""
        CALL ({unit}) {{
          OPTIONAL MATCH ({unit}) (()-[:{EDGE}]->(hidden:Unit WHERE NOT {_readable('hidden')})){{0,}} ()-[:{EDGE}]->(child:Unit)
          WHERE {_readable('child')}
          RETURN collect(DISTINCT child.id) AS children
        }}
    """


def _parents(unit: str = 'unit') -> str:
    """A call collecting the nearest readable units above unit, or the root of its unit graph, as parents"""
    return f"""
        CALL ({unit}) {{
          OPTIONAL MATCH ({unit})
            (()<-[:{EDGE}]-(hidden:Unit WHERE (:Unit)-[:{EDGE}]->(hidden) AND NOT {_readable('hidden')})){{0,}}
            ()<-[:{EDGE}]-(parent:Unit)
          WHERE NOT (:Unit)-[:{EDGE}]->(parent) OR {_readable('parent')}
          RETURN collect(DISTINCT parent.id) AS parents
        }}
    """


def _positions(unit: str = 'unit') -> str:
    return f"""
        CALL ({unit}) {{
          OPTIONAL MATCH ({unit})-[:IN_POSITION]->(position:Position)-[:AT_LOCATION]->(location:Location)
          WITH
            position,
            location,
            coalesce(position.start, localdatetime('0001-01-01T00:00:00')) AS effectiveStart,
            coalesce(position.end, localdatetime('9999-12-31T23:59:59')) AS effectiveEnd
          ORDER BY effectiveStart ASC, effectiveEnd ASC
          RETURN collect(
            position {{
              .*,
              location_id: location.id,
              layout_id: [(position)-[:IN_LAYOUT]->(layout:Layout) | layout.id][0]
            }}
          ) AS positions
        }}
    """


def _unit(unit: str = 'unit') -> str:
    """unit as the user sees it, given unit_readable, is_root, parents, children and positions in scope"""
    return f"""CASE
          WHEN unit_readable THEN {unit} {{
            .*,
            subject: [({unit})-[:OF_SUBJECT]->(subject:Subject) | subject.id][0],
            germplasm: [({unit})-[:OF_GERMPLASM]->(germplasm:Germplasm) | germplasm.id][0],
            positions: positions,
            parents: parents,
            children: children
          }}
          WHEN is_root THEN {unit} {{ .id, name: 'REDACTED', children: children }}
          ELSE {unit} {{ .id, name: 'REDACTED' }}
        END"""


def _project(unit: str = 'unit') -> str:
    """The calls that put what _unit needs in scope, reading links and positions only where they are shown"""
    return f"""
        WITH {unit}, {_readable(unit)} AS unit_readable, NOT (:Unit)-[:{EDGE}]->({unit}) AS is_root
        OPTIONAL CALL ({unit}, unit_readable, is_root) {{
          WITH {unit} WHERE unit_readable OR is_root
          {_children(unit)}
          RETURN children
        }}
        OPTIONAL CALL ({unit}, unit_readable) {{
          WITH {unit} WHERE unit_readable
          {_parents(unit)}
          {_positions(unit)}
          RETURN parents, positions
        }}
        WITH {unit}, unit_readable, is_root,
          coalesce(children, []) AS children, coalesce(parents, []) AS parents, coalesce(positions, []) AS positions
    """


def read_units():
    """The units with ids $unit_ids, a placeholder for those the user cannot read"""
    return f"""
        UNWIND $unit_ids AS unit_id
        MATCH (unit:Unit {{id: unit_id}})
        {_project()}
        RETURN {_unit()} AS unit
    """


def read_unit_graph_roots():
    """The roots of the unit graphs positioned at locations $location_ids that the user can read a unit in"""
    return f"""
        MATCH (unit:Unit)-[:IN_POSITION]->(:Position)-[:AT_LOCATION]->(location:Location)
        WHERE location.id IN $location_ids AND NOT (unit)<-[:{EDGE}]-(:Unit)
        WITH DISTINCT unit
        {_project()}
        WITH unit, unit_readable, is_root, parents, children, positions WHERE unit_readable OR size(children) > 0
        RETURN {_unit()} AS unit
        ORDER BY unit.id
    """


def read_unit_names():
    """
    The lightest read of units: id, name and germplasm, for crediting records to units, where positions and
    structure are not shown; units the user cannot read as placeholders
    """
    return f"""
        UNWIND $unit_ids AS unit_id
        MATCH (unit:Unit {{id: unit_id}})
        RETURN CASE WHEN {_readable('unit')}
          THEN {{ id: unit.id, name: unit.name, germplasm: [(unit)-[:OF_GERMPLASM]->(germplasm:Germplasm) | germplasm.id][0] }}
          ELSE {{ id: unit.id, name: 'REDACTED' }}
        END AS unit
    """


def read_descendants_by_subject():
    """
    Every unit below the units $unit_ids that the user can read, found through hidden units, grouped by subject, as id
    and name only: for selecting all the units of a subject at once, e.g. every tree of a field. A unit to start from
    must be readable, or a unit graph's root, whose placeholder holds the readable units below it; below another hidden
    unit nothing is found, as the units view gives such a unit no children.
    """
    return f"""
        MATCH (start:Unit) WHERE start.id IN $unit_ids AND ({_readable('start')} OR NOT (:Unit)-[:{EDGE}]->(start))
        MATCH (start)-[:{EDGE}*1..]->(unit:Unit)
        WITH DISTINCT unit
        WHERE {_readable('unit')}
        OPTIONAL MATCH (unit)-[:OF_SUBJECT]->(subject:Subject)
        WITH subject.id AS subject, unit
        ORDER BY unit.name, unit.id
        RETURN subject, collect({{id: unit.id, name: unit.name}}) AS units
    """
