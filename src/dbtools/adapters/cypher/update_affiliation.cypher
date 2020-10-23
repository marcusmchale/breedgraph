MATCH (user: User {username_lower: $username_lower})
        -[affiliation: AFFILIATED]->(team: Team {name: $team_name})
SET affiliation.level = $level