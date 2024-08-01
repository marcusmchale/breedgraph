MATCH
  (captured: GermplasmEntry {id: $entry})
OPTIONAL MATCH (captured)-[:SOURCE_FOR*]-(entry:GermplasmEntry)
WITH captured, coalesce(collect(entry), []) AS germplasm
WITH captured + germplasm AS germplasm
UNWIND germplasm AS entry

RETURN entry {
       . *,
         maintenance:[(entry)-[:USES_METHOD]->(maintenance:GermplasmMethod) | maintenance.id][0],
         references: [(entry)<-[:REFERENCE_FOR]->(reference:Reference) | reference.id],
         controller: {
         controls: [
           (entry)<-[controls:CONTROLS]-(:TeamGermplasm)<-[:CONTROLS]-(team:Team) |
           {team: team.id, release: controls.release, time: controls.time}
          ],
         writes: [
             (entry)<-[write:CREATED|UPDATED]-(:UserGermplasm)<-[:CREATED]-(user:User) |
             {user:user.id, time: write.time}
         ]
       }
     },
 [(source:GermplasmEntry)-[source_for:SOURCE_FOR]->(entry) | [source.id, entry.id, {label: source_for.type}]] AS sources
