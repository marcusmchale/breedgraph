## 1.2. Layouts

## 1.2.1 Layout types and instances
In BreedCAFS, layouts were effectively encoded (minimally) in the Block "Item" concept 
and in the Country/Region/Farm/Field/Block hierarchy.

To represent these as layouts, we need to first determine 
whether any of the tree row/column coordinates are unique to a block, 
or if they are specific to a field as we might expect.

```cypher
MATCH (field:Field)<-[:IS_IN*2]-(block:Block)<-[:IS_IN]-(:BlockTrees)<-[:IS_IN]-(tree:Tree)
WHERE tree.row IS NOT NULL AND tree.column IS NOT NULL
WITH field, tree.row AS row, tree.column AS column, count(*) AS coordinate_count
WHERE coordinate_count > 1
RETURN field.uid, row, column, coordinate_count
ORDER BY field.uid, row, column
```


We do have some coordinates that are duplicated within fields. 
Let's confirm that coordinates are always at least unique within a block.

```cypher
MATCH (field:Field)<-[:IS_IN*2]-(block:Block)<-[:IS_IN]-(:BlockTrees)<-[:IS_IN]-(tree:Tree)
WHERE tree.row IS NOT NULL AND tree.column IS NOT NULL
WITH field, block, tree.row AS row, tree.column AS column, collect(tree.id) as trees
WHERE size(trees) > 1
RETURN field.uid, block.uid, row, column, trees
ORDER BY field.uid, block.uid, row, column
```

We have a small number of cases (3 coordinate positions in one block) where this is not the case.
These paired duplicate coordinate trees were all created at the same time, 
and all inputs are the same, including the name, variety, sowing date etc.
The record values were also all submitted at the same time.
```cypher
MATCH (t:Tree) where t.uid in ["REDACTED"]
MATCH (t)<-[:FOR_ITEM]-(ii:ItemInput)<-[:RECORD_FOR]-(record:Record), (ii)-[:FOR_INPUT*]->(input:Input)
RETURN collect(t.id), record.value, input.name
```

It seems the most prudent strategy is to keep the units in and later resolve in discussion
with the project partner ([private notes](private_notes.md#layouts)). Likely to remove te duplicates.
But we won't worry about a custom layout as it is more likely to be an error in data entry. 

Consider whether the same thing happened at the field level to create the other duplications, 
or whether we really do have duplicated coordinates within fields.
Check all the input values and see if there are any differing values (at the same time/replicate)

```cypher
MATCH (field:Field)<-[:IS_IN*2]-(tree:Tree)
WHERE tree.row IS NOT NULL AND tree.column IS NOT NULL
OPTIONAL MATCH (tree)-[:IS_IN*2]->(block:Block)

MATCH (tree)<-[:FOR_ITEM]-(ii:ItemInput)
      <-[:RECORD_FOR]-(record:Record),
      (ii)-[:FOR_INPUT*]->(input:Input)
with field, tree, block, record, input
ORDER BY field.uid, tree.id, tree.row, tree.column
WITH
    field.uid as field,
    collect(block.id) as blocks,
    tree.row AS row,
    tree.column AS column,
    input.name AS input_name,
    record.time AS time,
    record.replicate as replicate,
    collect(distinct record.value) AS values,
    collect([tree.id, record.value]) AS tree_values
WHERE size(values)>1
RETURN field, blocks, row, column, input_name, time, replicate, tree_values
```

There are two fields where we have distinct value. 
One field (29) this appears to be a true case of distinct coordinates per block.

Another field (5) appears to be using a different coordinate system entirely,
We will need to discuss this with the project partner ([private notes](private_notes.md#layouts)).
But for now we will need to create a unique layout definition in the ontology describing the abstract concept.
This might be a grid or similar.

We also need to consider where we recorded Stratum data, 
as these fields will require this additional layout for defining branch positions.

```cypher
MATCH (f:Field)<-[:IS_IN|FROM*]-(item:Item)<-[:FOR_ITEM]-(ii:ItemInput)-[:FOR_INPUT*..5]->(:Input {name: "Stratum"}),
      (ii)<-[:RECORD_FOR]-(record:Record) 
RETURN collect(distinct f.uid)
```

So we need to create three layout types in the [ontology](_Create_Ontology.md), "Row and Tree", "Row, Tree and Stratum", and "Grid".

And we need to summarise which layout type is required for any location with either trees with row and column data or stratum records.
```cypher
MATCH (f:Field)<-[:IS_IN|FROM*]-(item:Item) where item.row is not null or item.column is not null
RETURN collect(DISTINCT f.uid)
```

```cypher
MATCH (f:Field)

OPTIONAL MATCH (f)<-[:IS_IN|FROM*]-(item:Item)
WHERE item.row IS NOT NULL OR item.column IS NOT NULL
WITH f, count(DISTINCT item) > 0 AS row_and_tree

OPTIONAL MATCH (f)<-[:IS_IN|FROM*]-(item:Item)
              <-[:FOR_ITEM]-(ii:ItemInput)
              -[:FOR_INPUT*..5]->(:Input {name: "Stratum"}),
              (ii)<-[:RECORD_FOR]-(record:Record)
WITH f, row_and_tree, count(DISTINCT ii) > 0 AS stratum

RETURN f.uid as field_uid, row_and_tree, f.uid = 29 as row_and_tree_per_block, stratum as row_tree_and_stratum
```

Saved this table as 'field_layout_types.csv'

### 1.2.2 Positions

Since we have defined the semantics of layouts, we can extract positions mapped to unit UID here.
Don't try to associate times to positions I think.
We can leave these as sowing date and harvest date variables.

```cypher
MATCH (field:Field)<-[:IS_IN|FROM*]-(item:Item)
WHERE item.row IS NOT NULL OR item.column IS NOT NULL
OPTIONAL MATCH (item)-[:IS_IN*2]->(block:Block)
OPTIONAL MATCH (item)<-[:FOR_ITEM]-(ii:ItemInput)
              -[:FOR_INPUT*..5]->(:Input {name: "Stratum"}),
              (ii)<-[:RECORD_FOR]-(stratum_record:Record)
WITH DISTINCT field, block, item, stratum_record 

RETURN
field.uid as field_uid,
item.uid as item_uid,
CASE WHEN stratum_record IS NULL THEN "row_and_tree" ELSE "row_tree_and_stratum" END as layout_type,
CASE WHEN field.uid = 29 THEN "block" ELSE "field" END as layout_level,
CASE WHEN field.uid = 29 THEN block.name ELSE field.name END as layout_name,
item.row as row,
item.column as column,
stratum_record.value as stratum
```

saved this as unit_positions.csv

There was also an input that specified locations for samples (Location (text)).
Only one location was ever used, will need to create this one.

```cypher
match (s)-[sub:SUBMITTED]->(r:Record)-[:RECORD_FOR]->(ii:ItemInput)-[:FOR_INPUT*]->(input:Input {name: "Location (text)"}),
      (ii)-[:FOR_ITEM]->(item:Item)
return item.uid as item_uid, r.value as location, date(datetime({epochMillis: r.start})) as date
```
These should also be set as positions and have been saved as sample_positions.csv
