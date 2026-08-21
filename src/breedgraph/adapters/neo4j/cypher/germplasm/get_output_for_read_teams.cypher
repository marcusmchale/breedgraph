// ------------------------------------------------------------
// Find visible nodes
// ------------------------------------------------------------

MATCH (g:Germplasm)

MATCH (g)<-[:CONTROLS]-(control:Control)
      <-[:CONTROLS]-(tg:TeamGermplasms)
      <-[:CONTROLS]-(team:Team)

WITH g, team, control
ORDER BY g.id, team.id, control.sequence DESC

WITH
    g,
    team,
    collect(control)[0] AS control

WITH
    g,
    collect(team.id) AS team_ids,
    min(control.release) AS effective_release

WHERE
    any(team_id IN team_ids WHERE team_id IN $read_teams)
    OR effective_release >= $minimum_release

WITH collect(g) AS visible_nodes

UNWIND visible_nodes AS g


// ------------------------------------------------------------
// Project SOURCE relationships.
//
// There are two cases:
//
// 1. source -> g directly
//      Preserve source_type and description.
//
// 2. source -> private -> ... -> private -> g
//      Collapse to source -> g with UNKNOWN.
//
// A visible node may never be traversed as an intermediate node.
// ------------------------------------------------------------

CALL (g, visible_nodes) {

    // Direct visible source relationships
    CALL (g, visible_nodes) {
        MATCH (source:Germplasm)-[r:SOURCE_FOR]->(g)
        WHERE source IN visible_nodes

        RETURN collect({
            source_id: source.id,
            sink_id: g.id,
            source_type: r.source_type,
            description: r.description,
            priority: 0
        }) AS direct_sources
    }

    // Collapsed relationships through private nodes
    CALL (g, visible_nodes) {
        MATCH p = SHORTEST 1
            (g:Germplasm)
            (
                ()<-[:SOURCE_FOR]-
                (
                    middle:Germplasm
                    WHERE NOT middle IN visible_nodes
                )
            ){1,}
            ()<-[:SOURCE_FOR]-
            (
                source:Germplasm
                WHERE source IN visible_nodes
            )

        RETURN collect({
            source_id: source.id,
            sink_id: g.id,
            source_type: 'UNKNOWN',
            description: null,
            priority: 1
        }) AS collapsed_sources
    }

    // Direct relationships win if both a direct and collapsed
    // route exist between the same visible nodes.
    UNWIND direct_sources + collapsed_sources AS relationship

    WITH relationship

    ORDER BY
        relationship.source_id,
        relationship.sink_id,
        relationship.priority

    WITH
        relationship.source_id AS source_id,
        relationship.sink_id AS sink_id,
        collect(relationship)[0] AS relationship

    RETURN collect({
        source_id: relationship.source_id,
        sink_id: relationship.sink_id,
        source_type: relationship.source_type,
        description: relationship.description
    }) AS projected_sources
}


// ------------------------------------------------------------
// Project SINK relationships.
//
// Mirror image:
//
// g -> sink directly
// OR
// g -> private -> ... -> private -> sink
// ------------------------------------------------------------

CALL (g, visible_nodes) {

    // Direct visible sink relationships
    CALL (g, visible_nodes) {
        MATCH (g)-[r:SOURCE_FOR]->(sink:Germplasm)
        WHERE sink IN visible_nodes

        RETURN collect({
            source_id: g.id,
            sink_id: sink.id,
            source_type: r.source_type,
            description: r.description,
            priority: 0
        }) AS direct_sinks
    }

    // Collapsed relationships through private nodes
    CALL (g, visible_nodes) {
        MATCH p = SHORTEST 1
            (g:Germplasm)
            (
                ()-[:SOURCE_FOR]->
                (
                    middle:Germplasm
                    WHERE NOT middle IN visible_nodes
                )
            ){1,}
            ()-[:SOURCE_FOR]->
            (
                sink:Germplasm
                WHERE sink IN visible_nodes
            )

        RETURN collect({
            source_id: g.id,
            sink_id: sink.id,
            source_type: 'UNKNOWN',
            description: null,
            priority: 1
        }) AS collapsed_sinks
    }

    // Direct relationships win over collapsed relationships.
    UNWIND direct_sinks + collapsed_sinks AS relationship

    WITH relationship

    ORDER BY
        relationship.source_id,
        relationship.sink_id,
        relationship.priority

    WITH
        relationship.source_id AS source_id,
        relationship.sink_id AS sink_id,
        collect(relationship)[0] AS relationship

    RETURN collect({
        source_id: relationship.source_id,
        sink_id: relationship.sink_id,
        source_type: relationship.source_type,
        description: relationship.description
    }) AS projected_sinks
}


// ------------------------------------------------------------
// Return the resolved node.
// ------------------------------------------------------------

RETURN
    g {
        .*,
        control_methods: [
            (g)-[:USES_CONTROL_METHOD]->(method:ControlMethod)
            | method.id
        ],
        references: [
            (reference:Reference)-[:REFERENCE_FOR]->(g)
            | reference.id
        ],
        sources: projected_sources,
        sinks: projected_sinks
    } AS entry