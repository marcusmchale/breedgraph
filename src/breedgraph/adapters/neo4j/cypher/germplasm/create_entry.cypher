MATCH (writer: User {id: $writer})

MERGE (counter: count {name: 'germplasm'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1

MERGE (writer)-[:CREATED]->(ug:UserGermplasm)
CREATE (ug)-[created:CREATED {time:datetime.transaction()}]->(entry: GermplasmEntry {
  id: counter.count,
  name: $name,
  synonyms: $synonyms,
  description:  $description,
  reproduction: $reproduction
})
WITH entry
// Create controls
CALL {
  WITH entry
  UNWIND $controls AS control
  MATCH (control_team:Team)
    WHERE control_team.id = control['team']
  MERGE (control_team)-[:CONTROLS]->(tp:TeamGermplasm)
  CREATE (tp)-[controls:CONTROLS {release: control['release'], time: datetime.transaction()}]->(entry)
  RETURN
  collect({
    team:    control_team.id,
    release: controls.release,
    time:    controls.time
  }) AS controls
}
// Link method
CALL {
  WITH entry
  MATCH (maintenance: GermplasmMethod {id: $maintenance})
  CREATE (entry)-[uses_method:USES_METHOD {time:datetime.transaction()}]->(maintenance)
  RETURN
    collect(maintenance.id)[0] AS maintenance
}
// Link references
CALL {
  WITH entry
  UNWIND $references AS ref_id
  MATCH (reference: Reference {id: ref_id})
  CREATE (reference)-[ref_for:REFERENCE_FOR {time:datetime.transaction()}]->(entry)
  RETURN
    collect(reference.id) AS references
}
RETURN entry {
       .*,
         maintenance:maintenance,
         references:references,
         controller: {
          controls: controls,
          writes: [
            (germplasm)<-[write:CREATED|UPDATED]-(:UserGermplasm)<-[:CREATED]-(user:User) |
            {user:user.id, time: write.time}
          ]
       }
     }
