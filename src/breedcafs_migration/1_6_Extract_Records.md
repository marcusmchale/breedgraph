## 1.6. Extract Records
Do not include the `person` value in record dumps; attribution is extracted separately in [1.7](1_7_Extract_Persons.md).
Deleted BreedCAFS records have no `RECORD_FOR` relationship (see [1.7.2](1_7_Extract_Persons.md#172-deleted-records)), so queries through `RECORD_FOR` leave them out.


### Replication
BreedCAFS records have a replicate code. In BreedGraph, replicates are a record grouping on the Study,
whose codes are compared only within a scope of Datasets.

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

Replicate codes are not otherwise reserved for real replication (e.g. 0 is often given for a single replicate),
and were only checked within a submission. So they become a dataset-scoped grouping with one scope per submission:
the Datasets of that submission in a Study (README §7.6).




### Extract

[extract_records.cypher](cypher/extract_records.cypher) gives one row per live record, except curves,
leaving out the structural properties and the inputs extracted elsewhere (1.2, 1.4, 1.5).
Each row has the BreedCAFS record id, the submission (time and the submitter's BreedCAFS node id),
the item uid, input, value, time or start and end (with the original text times) and replicate code.
It does not name who recorded the record; the submission links it to the attribution values in submissions.csv.
"Set harvest time" records are kept, to be merged into Harvest.

Saved this as records.csv

Records loaded without a submission have no submission time or submitter.
No record repeats the same submission, input, item, time and replicate code.

[extract_curves.cypher](cypher/extract_curves.cypher) gives the curve records in the same way, with their x and y values.
All curves share the same x values.

Saved this as curves.csv

### Curve
During creation, the curve data file is built from curves.csv: a CSV with Item ID, Time and Replicate,
then a column for each x value, as all curves share the same x values; each row has a curve's y values.

Retain the original `text_time` value as appropriate.
Validate that the time values can be parsed as `numpy.datetime64`.
Create BreedGraph records for each relevant Item referencing the resulting data file.

The CSV should be treated as an immutable migration data artefact.
