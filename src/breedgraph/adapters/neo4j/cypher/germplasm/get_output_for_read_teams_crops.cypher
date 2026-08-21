// ============================================================
// Determine visible Germplasm IDs
// ============================================================

MATCH (g:Germplasm)

MATCH (g)<-[:CONTROLS]-(control:Control)
      <-[:CONTROLS]-(tg:TeamGermplasms)
      <-[:CONTROLS]-(team:Team)

WITH
    g,
    team,
    control

ORDER BY
    g.id,
    team.id,
    control.sequence DESC

WITH
    g,
    team,
    collect(control)[0] AS control

WITH
    g,
    collect(team.id) AS team_ids,
    min(control.release) AS effective_release

WITH collect(
    CASE
        WHEN any(team_id IN team_ids WHERE team_id IN $read_teams)
             OR effective_release >= $minimum_release
        THEN g.id
    END
) AS visible_ids

WITH [
    id IN visible_ids
    WHERE id IS NOT NULL
] AS visible_ids


// ============================================================
// Find visible Germplasm roots / crops.
//
// The root test is against the complete graph, not the visible
// graph. A private source therefore still prevents a node from
// being a crop.
// ============================================================

MATCH (g:Germplasm)
WHERE
    g.id IN visible_ids
    AND NOT (g)<-[:SOURCE_FOR]-(:Germplasm)


// ============================================================
// Resolve sinks for each crop.
//
// Direct:
//     crop -> visible sink
//
// Collapsed:
//     crop -> private -> ... -> private -> visible sink
// ============================================================

CALL (g, visible_ids) {

    // --------------------------------------------------------
    // Direct sinks
    // --------------------------------------------------------

    CALL (g, visible_ids) {

        MATCH (g)-[r:SOURCE_FOR]->(sink:Germplasm)
        WHERE sink.id IN visible_ids

        RETURN collect({
            source_id: g.id,
            sink_id: sink.id,
            source_type: r.source_type,
            description: r.description,
            priority: 0
        }) AS direct_sinks
    }


    // --------------------------------------------------------
    // Collapsed sinks
    //
    // Every intermediate node must be private and the final
    // sink must be visible.
    // --------------------------------------------------------

    CALL (g, visible_ids) {

        MATCH p = SHORTEST 1
            (g:Germplasm)
            (
                ()-[:SOURCE_FOR]->
                (
                    middle:Germplasm
                    WHERE NOT middle.id IN visible_ids
                )
            ){1,}
            ()-[:SOURCE_FOR]->
            (
                sink:Germplasm
                WHERE sink.id IN visible_ids
            )

        RETURN collect({
            source_id: g.id,
            sink_id: sink.id,
            source_type: 'UNKNOWN',
            description: null,
            priority: 1
        }) AS collapsed_sinks
    }


    // --------------------------------------------------------
    // Combine direct and collapsed relationships.
    //
    // If both A -> C and A -> private -> C exist, prefer the
    // direct relationship.
    // --------------------------------------------------------

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
        source_id: source_id,
        sink_id: sink_id,
        source_type: relationship.source_type,
        description: relationship.description
    }) AS projected_sinks
}


// ============================================================
// Return the same Germplasm shape as germplasm(entryIds)
// ============================================================

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

        sources: [],
        sinks: projected_sinks
    } AS entry