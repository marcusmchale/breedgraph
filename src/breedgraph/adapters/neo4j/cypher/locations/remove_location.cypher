MATCH (location: Location {id: $location})-[:WITHIN_LOCATION]->(parent)
OPTIONAL MATCH (location)<-[:WITHIN_LOCATION]-(nested_location:Location)
CREATE (nested_location)-[:WITHIN_LOCATION]->(parent)
DETACH DELETE location