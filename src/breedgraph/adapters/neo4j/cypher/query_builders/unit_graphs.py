from breedgraph.domain.model.controls import ControlledModelLabel
from breedgraph.adapters.neo4j.cypher.query_builders.access import readable
from breedgraph.adapters.neo4j.cypher.query_builders.times import upper

# Units as the user may see them, without reading whole unit graphs. A unit the user can read is returned in full, its
# parents and children being the nearest readable units along paths through hidden units only, as the repository's
# redaction reconnects them; a unit graph's root is kept even when hidden, so a hidden root can be a unit's parent. A
# hidden root is returned as a placeholder, its id and a REDACTED name, keeping its readable descendants as children,
# when it was asked for directly or holds units the user can read. Any other hidden unit asked for by id is returned
# as a bare placeholder.

UNIT = ControlledModelLabel.UNIT
LOCATION = ControlledModelLabel.LOCATION
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
            derived_from: [({unit})-[derived:DERIVED_FROM]->(source:Unit) | derived {{.source_type, .description, unit_id: source.id}}],
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
    """
    The roots of the unit graphs positioned at locations $location_ids that the user can read a unit in; nothing at a
    location the user cannot read, as for any search from it (docs/read-access.md, rule 5)
    """
    return f"""
        MATCH (unit:Unit)-[:IN_POSITION]->(:Position)-[:AT_LOCATION]->(location:Location)
        WHERE location.id IN $location_ids AND NOT (unit)<-[:{EDGE}]-(:Unit) AND {readable('location', LOCATION)}
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


def read_inherited_germplasm():
    """
    For each readable unit of $unit_ids without germplasm of its own, the nearest units above it with germplasm, one
    on each lineage (walking up through units without germplasm, readable or not, each path stops at the first unit
    with some), each with its germplasm, distance and whether the user can read it: the unit takes their germplasm when
    they are all readable and agree (domain.services.lineages, Unit.inheritedGermplasm)
    """
    return f"""
        UNWIND $unit_ids AS unit_id
        MATCH (unit:Unit {{id: unit_id}})
        WHERE {_readable('unit')} AND NOT EXISTS {{ MATCH (unit)-[:OF_GERMPLASM]->(:Germplasm) }}
        CALL (unit) {{
          MATCH path = (unit)
            (()<-[:{EDGE}]-(between:Unit WHERE NOT EXISTS {{ MATCH (between)-[:OF_GERMPLASM]->(:Germplasm) }})){{0,}}
            ()<-[:{EDGE}]-(source:Unit)-[:OF_GERMPLASM]->(germplasm:Germplasm)
          WITH source, germplasm, min(length(path)) AS distance
          RETURN collect({{
            unit_id: source.id, germplasm_id: germplasm.id, distance: distance, readable: {_readable('source')}
          }}) AS sources
        }}
        RETURN unit.id AS unit_id, sources
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


def read_unit_ancestors():
    """
    For each unit $unit_ids the user can read, the ids of the units above it that they can read, closest first (by
    the shortest path, then id), found through hidden units as parents are, with its unit graph's root even when
    hidden, as the placeholder it is kept as. A hidden unit, a bare placeholder, has none.
    """
    return f"""
        UNWIND $unit_ids AS unit_id
        MATCH (unit:Unit {{id: unit_id}})
        WHERE {_readable('unit')}
        OPTIONAL MATCH path = (ancestor:Unit)-[:{EDGE}*1..]->(unit)
        WHERE {_readable('ancestor')} OR NOT (:Unit)-[:{EDGE}]->(ancestor)
        WITH unit, ancestor, min(length(path)) AS distance
        ORDER BY unit.id, distance, ancestor.id
        RETURN unit.id AS unit_id, collect(ancestor.id) AS ancestor_ids
    """


def read_unit_derivatives():
    """
    For each unit $unit_ids the user can read, the units derived from it that the user can read, by id, each with how
    it was derived: a search from the unit, so hidden units are left out (docs/read-access.md, rule 5)
    """
    return f"""
        UNWIND $unit_ids AS unit_id
        MATCH (unit:Unit {{id: unit_id}})
        WHERE {_readable('unit')}
        MATCH (derivative:Unit)-[derived:DERIVED_FROM]->(unit)
        WHERE {_readable('derivative')}
        WITH unit, derivative, derived
        ORDER BY derivative.id
        RETURN unit.id AS unit_id,
          collect(derived {{.source_type, .description, unit_id: derivative.id}}) AS derivatives
    """


# Arrivals: the units that came to a location together, from elsewhere in their unit graphs (README, Unit graph). A unit
# is where its own position holding at a time puts it, else where its parent is; an arrival at a location from a start
# is the readable units, not roots, with a position there from that start (as entered: value, unit and step) whose
# parents were not there then. Positions have no identity, so an arrival is known by its location and start.

# the order of a start's precision, finest first, for arrivals that start at the same instant
_PRECISION = "CASE {unit} WHEN 'ns' THEN 0 WHEN 'us' THEN 1 WHEN 'ms' THEN 2 WHEN 's' THEN 3 WHEN 'm' THEN 4 " \
             "WHEN 'h' THEN 5 WHEN 'D' THEN 6 WHEN 'W' THEN 7 WHEN 'M' THEN 8 WHEN 'Y' THEN 9 ELSE 10 END"


def _holds(held: str, at: str) -> str:
    """Whether the position held holds at the stored time at, the start of its period; with no time, at any time"""
    return f"""(
          {at} IS NULL
          OR (({held}.start IS NULL OR {held}.start <= {at}) AND ({held}.end IS NULL OR {at} < {upper(held + '.end')}))
        )"""


def _came_from_elsewhere(unit: str = 'unit', location: str = 'location', at: str = 'arrived') -> str:
    """
    Whether no unit above unit was at location at the stored time at: walking up through hidden units other than the
    root and units with no position of their own holding then (they are where their parents are), no unit the user can
    read, nor the root, has a position at location holding then. With no time, none was ever there. The inner variables
    are named apart from the outer ones, which a subquery would otherwise take for the same.
    """
    return f"""NOT EXISTS {{
          MATCH ({unit})
            (()<-[:{EDGE}]-(passed:Unit WHERE
              ((:Unit)-[:{EDGE}]->(passed) AND NOT {_readable('passed')})
              OR NOT EXISTS {{ MATCH (passed)-[:IN_POSITION]->(passed_held:Position) WHERE {_holds('passed_held', at)} }}
            )){{0,}}
            ()<-[:{EDGE}]-(placed:Unit)-[:IN_POSITION]->(placed_held:Position)-[:AT_LOCATION]->({location})
          WHERE ({_readable('placed')} OR NOT (:Unit)-[:{EDGE}]->(placed)) AND {_holds('placed_held', at)}
        }}"""


def _related(unit: str = 'unit') -> str:
    """Whether unit is $unit_id, or below or above it"""
    return f"""(
          EXISTS {{ MATCH (:Unit {{id: $unit_id}})-[:{EDGE}*0..]->({unit}) }}
          OR EXISTS {{ MATCH ({unit})-[:{EDGE}*1..]->(:Unit {{id: $unit_id}}) }}
        )"""


def _arrived(location_match: str, start_match: str, related: bool, carried: str = '') -> str:
    """
    Rows of location, unit, position and arrived (the start of its position there), for the arrivals at the locations
    location_match finds, from the starts start_match allows, carrying the variables carried ("arrival, "): nothing at a
    location the user cannot read
    """
    return f"""
        {location_match}
        WITH {carried}location WHERE {readable('location', LOCATION)}
        MATCH (location)<-[:AT_LOCATION]-(position:Position)<-[:IN_POSITION]-(unit:Unit)
        WHERE {start_match} AND (:Unit)-[:{EDGE}]->(unit) AND {_readable('unit')}{' AND ' + _related() if related else ''}
        WITH {carried}location, unit, position, position.start AS arrived
        WHERE {_came_from_elsewhere()}
    """


def _entered_start(position: str, start: str) -> str:
    """Whether position starts at start as entered: a map of time, unit and step, all null for no start"""
    return f"""(CASE WHEN {start}.time IS NULL THEN {position}.start IS NULL
          ELSE {position}.start = {start}.time AND {position}.start_unit = {start}.unit AND {position}.start_step = {start}.step
        END)"""


def read_unit_arrivals(related: bool = False):
    """
    The arrivals at the locations $location_ids: each location id and start as entered, how many units came, how many
    of them have units derived from them that the user can read, how many are pending (still there, with nothing
    derived from them), and the roots of the unit graphs they came from; newest first, the finer start first at one
    instant, undated last. With related, only the units at, below or above $unit_id
    """
    return f"""
        {_arrived('MATCH (location:Location) WHERE location.id IN $location_ids', 'true', related)}
        WITH location, unit, position, arrived,
          EXISTS {{ MATCH (derivative:Unit)-[:DERIVED_FROM]->(unit) WHERE {_readable('derivative')} }} AS derived
        WITH location, unit, position, arrived, derived,
          NOT derived AND (position.end IS NULL OR localdatetime.transaction() < {upper('position.end')}) AS pending
        WITH location, arrived, position.start_unit AS arrived_unit, position.start_step AS arrived_step,
          collect(DISTINCT unit) AS units,
          collect(DISTINCT CASE WHEN derived THEN unit END) AS derived_units,
          collect(DISTINCT CASE WHEN pending THEN unit END) AS pending_units
        CALL (units) {{
          UNWIND units AS arrived_unit_node
          MATCH (arrived_unit_node)<-[:{EDGE}*1..]-(root:Unit) WHERE NOT (:Unit)-[:{EDGE}]->(root)
          RETURN collect(DISTINCT root.id) AS root_ids
        }}
        RETURN location.id AS location_id, [arrived, arrived_unit, arrived_step] AS start, size(units) AS unit_count,
          size(derived_units) AS derived_unit_count, size(pending_units) AS pending_unit_count, root_ids
        ORDER BY arrived IS NULL, arrived DESC, {_PRECISION.format(unit='arrived_unit')}, location_id
    """


def read_arrival_units(related: bool = False):
    """
    A page of the units of the arrival at $location_id from $start (time, unit and step as entered, all null for
    the undated one), by name then id, from $offset, at most $limit; with related, only those at, below or above $unit_id
    """
    return f"""
        {_arrived('MATCH (location:Location {id: $location_id})', _entered_start('position', '$start'), related)}
        WITH DISTINCT unit
        ORDER BY unit.name, unit.id
        SKIP $offset LIMIT $limit
        {_project()}
        RETURN {_unit()} AS unit
        ORDER BY unit.name, unit.id
    """


def read_arrival_units_by_subject():
    """
    For each arrival in $arrivals ({location_id, start: {time, unit, step}}), its units grouped by subject, as id and
    name, for selecting them all at once
    """
    return f"""
        UNWIND $arrivals AS arrival
        {_arrived(
            'MATCH (location:Location {id: arrival.location_id})', _entered_start('position', 'arrival.start'), False,
            carried='arrival, '
        )}
        WITH DISTINCT arrival, unit
        OPTIONAL MATCH (unit)-[:OF_SUBJECT]->(subject:Subject)
        WITH arrival, subject.id AS subject, unit
        ORDER BY unit.name, unit.id
        RETURN arrival, subject, collect({{id: unit.id, name: unit.name}}) AS units
    """


def read_arrival_unit_ids(related: bool = False):
    """The ids of the units of the arrival at $location_id from $start, as read_arrival_units has them"""
    return f"""
        {_arrived('MATCH (location:Location {id: $location_id})', _entered_start('position', '$start'), related)}
        RETURN collect(DISTINCT unit.id) AS unit_ids
    """
