// The declaration is kept as history, marked withdrawn
MATCH (:Team {id: $team})-[declared: DECLARED {current: true}]->(declaration: LegalEntityDeclaration)
SET
  declared.current = false,
  declaration.withdrawn_at = datetime.transaction(),
  declaration.withdrawn_by = $user_id
