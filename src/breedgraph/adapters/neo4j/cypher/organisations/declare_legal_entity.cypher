// Each declaration is kept; the latest is marked current
MATCH (team: Team {id: $team})
OPTIONAL MATCH (team)-[previous:DECLARED {current: true}]->(:LegalEntityDeclaration)
SET previous.current = false
WITH DISTINCT team
CREATE (team)-[:DECLARED {current: true}]->(declaration: LegalEntityDeclaration {
  legal_name: $legal_name,
  privacy_contact: $privacy_contact,
  terms_version: $terms_version,
  declared_by: $declared_by,
  declared_at: datetime.transaction()
})
RETURN declaration {.*} AS declaration
