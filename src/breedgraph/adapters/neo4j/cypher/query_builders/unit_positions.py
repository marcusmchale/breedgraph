# Positions written outside the unit graph aggregate (service_layer.application.unit_positions). A write first takes
# the write lock of each unit it reads the positions of, in id order, so that writes to the same units, by this service
# or the unit graph repository, follow one another: each reads the positions as the one before left them. The positions
# are then written by the keys of their nodes, as read in the same transaction.

EDGE = 'INCLUDES_UNIT'

# a position's place and times, as stored
_PROPERTIES = """
    coordinates: row.coordinates,
    start: row.start, start_unit: row.start_unit, start_step: row.start_step,
    end: row.end, end_unit: row.end_unit, end_step: row.end_step
"""


def read_positions_locked():
    """
    The units of $unit_ids with their own positions, each with the key of its node, once their write locks are taken
    (writing a property and removing it takes the lock, held to the end of the transaction)
    """
    return f"""
        MATCH (unit:Unit) WHERE unit.id IN $unit_ids
        WITH unit ORDER BY unit.id
        SET unit._lock = true
        REMOVE unit._lock
        WITH unit
        CALL (unit) {{
          OPTIONAL MATCH (unit)-[:IN_POSITION]->(position:Position)-[:AT_LOCATION]->(location:Location)
          RETURN collect(position {{
            .*,
            key: elementId(position),
            location_id: location.id,
            layout_id: [(position)-[:IN_LAYOUT]->(layout:Layout) | layout.id][0]
          }}) AS positions
        }}
        RETURN
          unit.id AS unit_id,
          unit.name AS name,
          NOT EXISTS {{ MATCH (unit)<-[:{EDGE}]-(:Unit) }} AS root,
          positions
    """


def create_positions():
    """Positions of the units, from $rows of unit_id, location_id, layout_id and the stored properties"""
    return f"""
        UNWIND $rows AS row
        MATCH (unit:Unit {{id: row.unit_id}})
        MATCH (location:Location {{id: row.location_id}})
        OPTIONAL MATCH (layout:Layout {{id: row.layout_id}})
        CREATE (unit)-[:IN_POSITION]->(position:Position {{ {_PROPERTIES} }})-[:AT_LOCATION]->(location)
        FOREACH (i IN CASE WHEN layout IS NOT NULL THEN [1] ELSE [] END |
          MERGE (position)-[:IN_LAYOUT]->(layout)
        )
        RETURN count(position) AS written
    """


def change_positions():
    """The positions with the keys of $rows, each given the place and times of its row"""
    return f"""
        UNWIND $rows AS row
        MATCH (position:Position) WHERE elementId(position) = row.key
        SET position += {{ {_PROPERTIES} }}
        WITH position, row
        CALL (position, row) {{
          MATCH (position)-[at:AT_LOCATION]->(location:Location) WHERE location.id <> row.location_id
          DELETE at
        }}
        CALL (position, row) {{
          MATCH (location:Location {{id: row.location_id}})
          MERGE (position)-[:AT_LOCATION]->(location)
        }}
        CALL (position, row) {{
          MATCH (position)-[in_layout:IN_LAYOUT]->(layout:Layout)
            WHERE row.layout_id IS NULL OR layout.id <> row.layout_id
          DELETE in_layout
        }}
        CALL (position, row) {{
          MATCH (layout:Layout {{id: row.layout_id}})
          MERGE (position)-[:IN_LAYOUT]->(layout)
        }}
        RETURN count(position) AS written
    """


def delete_positions():
    """The positions with the keys $keys"""
    return """
        UNWIND $keys AS key
        MATCH (position:Position) WHERE elementId(position) = key
        DETACH DELETE position
        RETURN count(*) AS written
    """
