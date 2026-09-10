## 1.6. Extract Records
Do not include Person information.


### Replication
Replication in BreedGraph is to be defined with units in block structures rather than embedded in records.


Extract the replicate code here and during registration create replicates.

First consider how many cases this was used in (where more than one replicate is given).

Before that consider if it is always used properly, i.e. only ever 1 record per unit per time * replicate code

```cypher
MATCH (r:Record) WHERE r.replicate IS NOT NULL
WITH r
MATCH (r)-[:RECORD_FOR]->(ii:ItemInput)-[:FOR_ITEM]->(item:Item), (ii)-[:FOR_INPUT*]->(input: Input)

WITH input, item, r.time as record_time, r.replicate as record_replicate, count(r) as record_count 
RETURN distinct record_count
 
```
Result is a single row of 1, so it has been enforced properly.

Now check how often it is used, i.e. the replicate code is the same for multiple records
on the same item, for the same input at the same time. 
I imagine there are many cases where e.g. 0 was entered for a single replicate rather than being reserved for cases
where replication was actually performed.

```cypher
MATCH (r:Record) WHERE r.replicate IS NOT NULL
WITH r
MATCH (r)-[:RECORD_FOR]->(ii:ItemInput)-[:FOR_ITEM]->(item:Item), (ii)-[:FOR_INPUT*]->(input: Input)

WITH input, item, r.time as record_time, count(r) as record_count 
RETURN count(distinct input), count(distinct item), count(distinct record_time), record_count ORDER BY record_count
```

A few inputs have many replicates, but as expected, most have just 1.

Let's start by investigating the inputs that these correspond to.

```cypher
MATCH (r:Record) WHERE r.replicate IS NOT NULL
WITH r
MATCH (r)-[:RECORD_FOR]->(ii:ItemInput)-[:FOR_ITEM]->(item:Item), (ii)-[:FOR_INPUT*]->(input: Input)

WITH input, item, r.time as record_time, count(r) as record_count, collect(r) as records
WHERE record_count > 1
RETURN distinct(input.name)
```

So just the metabolite and photosynthesis data. This makes sense. 




### Curve
Collate the curve values into a CSV file with Item ID, Time, Replicate then all X-values as header.

The data rows should include values for ID, timem replicate and y-values.

Retain the original `text_time` value as appropriate.
Validate that the time values can be parsed as `numpy.datetime64`.
Create BreedGraph records for each relevant Item referencing the resulting data file.

The CSV should be treated as an immutable migration data artefact.
