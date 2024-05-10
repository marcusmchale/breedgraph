MATCH (location: Location {id: location})
OPTIONAL MATCH (location)-[existing_within:WITHIN_LOCATION]->(:Location)
DELETE existing_within
WITH location
MATCH (parent: Location {id: parent})
CREATE (location)-[:WITHIN_LOCATION]->(parent)