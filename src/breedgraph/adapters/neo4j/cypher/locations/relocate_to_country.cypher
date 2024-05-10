MATCH (location: Location {id: location})
OPTIONAL MATCH (location)-[existing_within:WITHIN_LOCATION]->(:Location)
DELETE existing_within
WITH location
MATCH (country: Country {code: country})
CREATE (location)-[:WITHIN_LOCATION]->(country)