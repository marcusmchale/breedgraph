MERGE (counter:Counter {name: 'user'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (user: User {
  id:             counter.count,
  time:           datetime.transaction()
})
SET user += $props
RETURN user {.*}