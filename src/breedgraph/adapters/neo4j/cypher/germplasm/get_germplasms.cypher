MATCH (root: GermplasmEntry) WHERE NOT (root)<-[:SOURCE_FOR]-(:GermplasmEntry)
OPTIONAL MATCH (root)-[:SOURCE_FOR*]->(child:GermplasmEntry)
WITH root, coalesce(collect(child), []) AS children
WITH root + children AS germplasm
RETURN [entry IN germplasm |
  entry {
  . *,
    maintenance:[(entry)-[:USES_METHOD]->(maintenance:GermplasmMethod) | maintenance.id][0],
    references:[(entry)<-[:REFERENCE_FOR]->(reference:Reference) | reference.id],
    controller: {
      controls:[
         (entry)<-[controls:CONTROLS]-(:TeamGermplasm)<-[:CONTROLS]-(team:Team) |
         {team:team.id, release:controls.release, time:controls.time}
      ],
      writes:[
         (entry)< - [write:CREATED|UPDATED] -(:UserGermplasm)< - [:CREATED] -(user:User) |
         {user:user.id, time: write.time}
      ]
    },
    sources: [(source:GermplasmEntry)- [source_for:SOURCE_FOR] - >(entry) | [source.id, entry.id, {label:source_for.type}]]
  }
] AS germplasm