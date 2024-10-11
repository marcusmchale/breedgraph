MERGE (counter: Counter {name: 'reference'})
  ON CREATE SET counter.count = 0
SET counter.count = counter.count + 1
CREATE (reference: Reference {
  id: counter.count
})
SET reference += $params

RETURN
  reference {.*}