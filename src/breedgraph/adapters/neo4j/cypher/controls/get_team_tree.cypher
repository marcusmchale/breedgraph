MATCH (team: Team {id: $team_id})<-[:INCLUDES_TEAM*0..]-(root: Team)
WHERE NOT (root)<-[:INCLUDES_TEAM]-(:Team)
RETURN
  root.id AS root_id,
  EXISTS { (root)-[:DECLARED {current: true}]->(:LegalEntityDeclaration) } AS legal_entity_declared
