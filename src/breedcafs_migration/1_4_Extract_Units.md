## 1.4. Extract Units

In BreedCAFS, the unit of study was termed an "Item". 
To encode this in BreedGraph we need to determine for each item:
  - The name - to be copied to breedgraph name
  - The Subject
    - The "subject" is determined firstly by label (Field/Block/Tree)
    - When the labels included "sample", the Item has another attribute the "unit" which indicates the subject.
  - Parent/child Item UIDs

Other details stored on these nodes can be ignored as it was extracted in other phases:
  - Varieties were extracted while extracting germplasm. 
  - Positions were extracted along with layouts.
   

```cypher
MATCH (item:Item)

OPTIONAL MATCH (item)-[:IS_IN|FROM]->(source:Item)

WITH item, collect(DISTINCT source.uid) AS direct_sources

OPTIONAL MATCH (item)-[:IS_IN|FROM]->(middle)-[:IS_IN|FROM]->(source2:Item)
WHERE NOT middle:Item

WITH item,
     direct_sources + collect(DISTINCT source2.uid) AS source_items

OPTIONAL MATCH (item)<-[:IS_IN|FROM]-(sink:Item)

WITH item, source_items, collect(DISTINCT sink.uid) AS direct_sinks

OPTIONAL MATCH (item)<-[:IS_IN|FROM]-(middle)-[:IS_IN|FROM]-(sink2:Item)
WHERE NOT middle:Item

WITH item,
     source_items,
     direct_sinks + collect(DISTINCT sink2.uid) AS sink_items

RETURN
    item.uid as item_uid, 
    CASE 
        WHEN "Sample" in labels(item) 
        THEN item.unit 
        ELSE [l in labels(item) where l <> "Item"][0]
        END
    as subject, 
    [x IN source_items WHERE x IS NOT NULL] AS source_items,
    [x IN sink_items WHERE x IS NOT NULL] AS sink_items
```

saved this as item_name_subject_sources_sinks.csv
