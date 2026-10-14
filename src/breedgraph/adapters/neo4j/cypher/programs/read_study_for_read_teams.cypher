// One study as the programs repository reads it within its program, without the rest of the program, and whether
// the user can read it: a study is readable with no current controls, when the least of its current controls'
// releases is at least $minimum_release, or when a team in $read_teams controls it.
MATCH (study: Study {id: $study_id})
OPTIONAL MATCH (study)<-[:CONTROLS]-(control: Control)<-[:CONTROLS]-(:TeamStudies)<-[:CONTROLS]-(team: Team)
WITH study, team, control
ORDER BY team.id, control.sequence DESC
WITH study, team, collect(control)[0] AS control
WITH study, collect(CASE WHEN team IS NOT NULL AND NOT coalesce(control.ended, false) THEN {team: team.id, release: control.release} END) AS controls
RETURN
  study {
    .*,
    reference_ids: [(reference:Reference)-[:REFERENCE_FOR]->(study)|reference.id],
    design_id: [(study)-[:USES_DESIGN]->(design:Design)|design.id][0],
    licence_id: [(study)-[:USES_LICENCE]->(licence:Reference)|licence.id][0],
    groupings: [(study)-[:USES_GROUPING]->(grouping: RecordGrouping)-[:OF_TYPE]->(type:RecordGroupType) | {
        id: grouping.id,
        type: type.id,
        name: grouping.name,
        scope: grouping.scope,
        scopes: [
          (grouping)-[:HAS_SCOPE]->(scope:GroupingScope) | {
            dataset_ids: [(scope)<-[:IN_SCOPE]-(dataset:Dataset) | dataset.id]
          }
        ]
    }]
  } AS study,
  size(controls) = 0
    OR any(c IN controls WHERE c.team IN $read_teams)
    OR reduce(least = 2, c IN controls | CASE WHEN c.release < least THEN c.release ELSE least END) >= $minimum_release
    AS readable
