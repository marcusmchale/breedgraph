from breedgraph.domain.model.controls import ControlledModelLabel
from breedgraph.adapters.neo4j.cypher.query_builders.access import visible_members, tree_links

# Layouts as the user may see them, each as the repository's output map gives it (arrangement, parent and children
# ids, and the position within its parent), with the hidden layouts of an arrangement skipped: a parent is the
# nearest readable ancestor or the arrangement's root, and children are the nearest readable descendants. A layout
# linked to its parent past a hidden one has no position, as the repository's redaction leaves it. A layout the user
# can read is returned in full. A hidden arrangement root is returned as a placeholder, its id, a REDACTED name and
# its location, keeping its readable descendants as children, when it was asked for directly or holds layouts the user
# can read. Any other hidden layout asked for by id is returned as a bare placeholder; otherwise hidden layouts are
# left out.

LAYOUT = ControlledModelLabel.LAYOUT
EDGE = 'INCLUDES_LAYOUT'


def _with_root(layout: str = 'layout') -> str:
    """Group layouts by the root of their arrangement, with the ids in it the user can read, as root and visible_ids"""
    return f"""
        MATCH (root:Layout)-[:{EDGE}*0..]->({layout})
        WHERE NOT (:Layout)-[:{EDGE}]->(root)
        WITH root, collect(DISTINCT {layout}) AS layouts
        {visible_members('root', LAYOUT, EDGE, 'visible_ids')}
        UNWIND layouts AS {layout}
    """


def _layout(layout: str = 'layout') -> str:
    links = tree_links(layout, 'root', LAYOUT, EDGE, 'visible_ids')
    location = f"[({layout})-[:AT_LOCATION]->(location:Location) | location.id][0]"
    return f"""CASE
          WHEN {layout}.id IN visible_ids THEN {layout} {{
            .*,
            type: [({layout})-[:OF_LAYOUT_TYPE]->(type:LayoutType) | type.id][0],
            location: {location},
            arrangement: root.id,
            parent: parent,
            position: [(parent_layout:Layout {{id: parent}})-[edge:{EDGE}]->({layout}) | edge.position][0],
            children: {links['children']}
          }}
          WHEN {layout} = root THEN {layout} {{
            .id, name: 'REDACTED', location: {location}, arrangement: root.id, children: {links['children']}
          }}
          ELSE {layout} {{ .id, name: 'REDACTED' }}
        END"""


def _with_parent(layout: str = 'layout') -> str:
    return f"WITH root, visible_ids, {layout}, {tree_links(layout, 'root', LAYOUT, EDGE, 'visible_ids')['parent']} AS parent"


def read_layouts():
    """The layouts with ids $layout_ids, a placeholder for those the user cannot read"""
    return f"""
        MATCH (layout:Layout) WHERE layout.id IN $layout_ids
        {_with_root()}
        {_with_parent()}
        RETURN {_layout()} AS layout
    """


def read_arrangements():
    """The root of every arrangement at location $location_id that the user can read a layout in"""
    return f"""
        MATCH (layout:Layout)-[:AT_LOCATION]->(:Location {{id: $location_id}})
        WHERE NOT (:Layout)-[:{EDGE}]->(layout)
        {_with_root()}
        WITH root, visible_ids, layout WHERE size(visible_ids) > 0
        {_with_parent()}
        RETURN {_layout()} AS layout
        ORDER BY layout.id
    """
