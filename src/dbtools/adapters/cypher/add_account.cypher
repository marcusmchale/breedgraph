MATCH (team: Team {name: $team_name})
MATCH (counter: Counter {name: 'user'})
MERGE (user: User {
    username_lower: $username_lower
})
ON CREATE SET
    counter.count = counter.count + 1,
    user.id = counter.count,
    user.username = $username,
    user.password_hash = $password_hash,
    user.email = $email,
    user.fullname = $fullname,
    user.time = datetime.transaction(),
    user.confirmed = False
MERGE (user)-[affiliation: AFFILIATED]->(team)
ON CREATE SET
    affiliation.level = 0,
    affiliation.time = datetime.transaction()
MERGE (user)-[:SUBMITTED]->(: Submissions)-[:SUBMITTED]->(e: Emails {allowed:[]})
RETURN user.id
