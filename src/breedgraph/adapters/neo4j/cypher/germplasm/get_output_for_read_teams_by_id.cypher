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
// Fetch requested nodes.
//
// Private nodes are deliberately retained for referential
// lookup and will be returned as REDACTED.
// ============================================================

MATCH (g:Germplasm)
WHERE g.id IN $entry_ids


// ============================================================
// Resolve sources and sinks.
//
// The subquery always returns one row.
// Private nodes simply get empty relationship collections.
// ============================================================

CALL (g, visible_ids) {

    // ========================================================
    // SOURCES
    // ========================================================

    CALL (g, visible_ids) {

        // ----------------------------------------------------
        // Direct visible sources
        // ----------------------------------------------------

        MATCH (source:Germplasm)-[r:SOURCE_FOR]->(g)
        WHERE
            g.id IN visible_ids
            AND source.id IN visible_ids

        WITH collect({
            source_id: source.id,
            sink_id: g.id,
            source_type: r.source_type,
            description: r.description,
            priority: 0
        }) AS direct_sources

        // ----------------------------------------------------
        // Collapsed sources
        // ----------------------------------------------------

        CALL (g, visible_ids) {

            WITH g, visible_ids

            MATCH p = SHORTEST 1
                (g:Germplasm)
                (
                    ()<-[:SOURCE_FOR]-
                    (
                        middle:Germplasm
                        WHERE NOT middle.id IN visible_ids
                    )
                ){1,}
                ()<-[:SOURCE_FOR]-
                (
                    source:Germplasm
                    WHERE source.id IN visible_ids
                )

            WHERE g.id IN visible_ids

            RETURN collect({
                source_id: source.id,
                sink_id: g.id,
                source_type: 'UNKNOWN',
                description: null,
                priority: 1
            }) AS collapsed_sources
        }

        // ----------------------------------------------------
        // Prefer direct over collapsed for the same pair
        // ----------------------------------------------------

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
            source_id: source_id,
            sink_id: sink_id,
            source_type: relationship.source_type,
            description: relationship.description
        }) AS projected_sources
    }


    // ========================================================
    // SINKS
    // ========================================================

    CALL (g, visible_ids) {

        // ----------------------------------------------------
        // Direct visible sinks
        // ----------------------------------------------------

        MATCH (g)-[r:SOURCE_FOR]->(sink:Germplasm)
        WHERE
            g.id IN visible_ids
            AND sink.id IN visible_ids

        WITH collect({
            source_id: g.id,
            sink_id: sink.id,
            source_type: r.source_type,
            description: r.description,
            priority: 0
        }) AS direct_sinks

        // ----------------------------------------------------
        // Collapsed sinks
        // ----------------------------------------------------

        CALL (g, visible_ids) {

            WITH g, visible_ids

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

            WHERE g.id IN visible_ids

            RETURN collect({
                source_id: g.id,
                sink_id: sink.id,
                source_type: 'UNKNOWN',
                description: null,
                priority: 1
            }) AS collapsed_sinks
        }

        // ----------------------------------------------------
        // Prefer direct over collapsed for the same pair
        // ----------------------------------------------------

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


    RETURN
        projected_sources,
        projected_sinks
}


// ============================================================
// Final node projection
// ============================================================

RETURN
    CASE

        // ----------------------------------------------------
        // Visible node
        // ----------------------------------------------------

        WHEN g.id IN visible_ids

        THEN g {
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
        }

        // ----------------------------------------------------
        // Private node
        //
        // Referentially resolvable, but deliberately contains
        // no graph topology.
        // ----------------------------------------------------

        ELSE

            g {
                .id,
                name: 'REDACTED',
                sources: [],
                sinks: []
            }

    END AS entry