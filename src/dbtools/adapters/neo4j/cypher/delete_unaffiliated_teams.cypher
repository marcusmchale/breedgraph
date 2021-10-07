MATCH (team: Team) WHERE NOT (team)<-[:AFFILIATED]-()
DELETE team