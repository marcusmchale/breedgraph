## 1.4. Inputs

### 1.4.1 Attributes

Inputs have:
  - name
  - description (details)
  - format (numeric, location, categorical, date, text, percent, boolean)
  - optional categories

Formats can be mapped to BreedGraph ScaleType as follows:
  - numeric => NUMERICAL
  - location => NULL (to be defined as positions)
  - categorical => NOMINAL/ORDINAL (to be determined by manual curation)
  - date = DATE
  - text = TEXT
  - percent = numerical with the scale name and description as '%' + 'percentage'
  - boolean = NOMINAL categorical (e.g. present/absent, yes/no)
    
### 1.4.2 Terms

Inputs were also grouped into input groups, for ease of template generation. 
In BreedGraph this will be better encoded by association a term in the ontology.

### 1.4.3 Subjects

Inputs have an "AT_LEVEL" relationship that determines whether they are available for  each item type (samples/trees/blocks/fields)
This would be useful to associate as a subject in BreedGraph.

### 1.4.1 Input Types
BreedCAFS inputs had an associated RecordType (trait/curve/condition/property).
Traits and conditions probably map well onto Variable/Factor in BreedGraph, but individual inputs will need to be validated
as BreedGraph has a more comprehensive definition and supports time periods for all records.

#### 1.4.1.1 Properties
  - properties don't have a time attribute and are designed to set attributes of the item.

Most BreedCAFS Properties are already represented through unit attributes and do not require separate records.

Migrate only the following as factors:

* Elevation => Elevation
* Harvest Time / Harvest Date => Harvested
* Sowing Date => Sown 
* Planting Date => Planted

#### 1.4.1.2 Traits
  - traits support values at a single timepoint

  - To be encoded as BreedGraph variables which support optional datetime ranges.

```cypher
match (i:Input)-[:OF_TYPE]->(t:RecordType {name:"Trait"}) return collect(distinct i.format)
```
  - ["numeric", "boolean", "categorical", "percent", "date"]

#### 1.4.1.3 Conditions
  - conditions support values with optional start and end time

 - To be encoded as BreedGraph factors. Some may need to be adapted.
```cypher
match (i:Input)-[:OF_TYPE]->(t:RecordType {name:"Condition"}) return collect(distinct i.format)
```
  - ["categorical", "numeric", "text", "percent"]

#### 1.4.1.4 Curves
  - curves support arrays of x/y values

Only a single Curve input was used, describing fluorescence data. This will be a Variable in BreedGraph.

### Extract

```cypher
match (i:Input)<-[:FOR_INPUT*]-(ii:ItemInput)<-[:RECORD_FOR]-(r:Record)
WITH distinct i
MATCH 
(i)-[:OF_TYPE]->(t:RecordType)

call { with i 
  match (i)-[:IN_GROUP]->(g:InputGroup) 
  return collect(g.name) as terms
}
call { with i
  match (i)-[:AT_LEVEL]->(l:ItemLevel)
  return collect(l.name) as subjects
}

return
 t.name as type,
 i.name as name,
 i.details as description,
 i.format as format,
 i.categories as categories,
 terms,
 subjects

ORDER BY t.name, i.name
```
saved as input_details.csv

### Transform
Manually curated the exported CSV.
- Removed properties:
```text
    "Assign sample to block(s) by name"
    "Assign sample to sample(s) by ID"
    "Assign sample to tree(s) by ID"
    "Assign tree to block by name"
    "Assign variety name"
    "Set column"
    "Set custom name"
    "Set location"
    "Set row"
    "Set sample unit"
```
and also "Set Harvest Time" as this is to be merged with "Set Harvest Date"

## Location
- Removed the condition for sample locations
  -"Location (text)" (this data is to be recorded as positions)

## Stratum
- Removed the stratum trait (encoded in positions)

## Photosynthesis traits
- Removed the "Photosynthetic Analysis Apparatus" trait and generated a map to later assign
```cypher
MATCH (input:Input {name: "Photosynthetic Analysis Apparatus"})<-[:FOR_INPUT*]-(ii:ItemInput)<-[:RECORD_FOR]-(record:Record)<-[:SUBMITTED]-()<-[:SUBMITTED*]-(user:User)
return distinct user.username as username, record.time as record_time, collect(distinct record.value) as apparatus
```

## Ontology Entry Curation
- Added columns:
- Factor	
- Condition
- ControlMethod	
- ControlMethodType
- ControlMethodDescription
- Variable	
- Trait	
- Trait Description
- ObservationMethod	
- ObservationMethodType	
- ObservationMethodDescription	
- Scale	
- Scale Description	
- ScaleType	categories	
- terms	
- subjects


## Metabolites.
Here we are lacking details on what instrument was used to generate the data.

Start by considering submission batches so we can map these back to input groups:
```cypher
MATCH (i:Input)
MATCH (i)<-[:FOR_INPUT*]-(ii:ItemInput)
      <-[:RECORD_FOR]-(record:Record)
      <-[sub:SUBMITTED]-()<-[:SUBMITTED*]-(user:User)

WITH
    user.username as username,
    sub.time AS submission_time,
    i,
    record

RETURN
    username,
    submission_time,
    count(DISTINCT i) AS input_count,
    count(DISTINCT record) AS record_count,
    collect(DISTINCT i.name) AS inputs
ORDER BY submission_time
```

and
```cypher
MATCH (g:InputGroup)<-[:IN_GROUP]-(gi:Input)

WITH
    g,
    collect(DISTINCT id(gi)) AS group_input_ids

MATCH (i:Input)
MATCH (i)<-[:FOR_INPUT*]-(ii:ItemInput)
      <-[:RECORD_FOR]-(record:Record)
      <-[sub:SUBMITTED]-()<-[:SUBMITTED*]-(user:User)

WITH
    g,
    group_input_ids,
    user.username as username,
    sub.time AS submission_time,
    collect(DISTINCT id(i)) AS submission_input_ids,
    count(DISTINCT record) AS record_count

WITH
    g,
    group_input_ids,
    submission_time,
    username,
    submission_input_ids,
    record_count,

    [x IN group_input_ids
     WHERE x IN submission_input_ids] AS shared,

    [x IN group_input_ids
     WHERE NOT x IN submission_input_ids] AS missing,

    [x IN submission_input_ids
     WHERE NOT x IN group_input_ids] AS extra

RETURN
    g.name AS group,
    submission_time,
    username,
    size(group_input_ids) AS group_inputs,
    size(submission_input_ids) AS submitted_inputs,
    size(shared) AS shared_inputs,
    size(missing) AS missing_inputs,
    size(extra) AS extra_inputs,
    record_count,
    missing,
    extra

ORDER BY
    size(missing) + size(extra),
    submission_time,
    group
```

dumped this to csv then in R

```R
d <- read.csv(sep=',', header=T, file='submissions_batches_to_input_groups.csv')|>
        dplyr::mutate(dplyr::across(dplyr::where(is.character), ~ stringr::str_remove_all(., '"')))

min_missing <- d |>
  dplyr::group_by(submission_time) |>
  dplyr::slice_min(missing_inputs, with_ties = FALSE) |>
  dplyr::ungroup() |>
  dplyr::select(submission_time, group)

nrow(min_missing)
# this gives a reasonable guess as to the corresponding input group used, so we can try to infer the methodology. 

candidate_groups <- d |>
  dplyr::group_by(submission_time) |>
  dplyr::filter(extra_inputs == 0) |>
  dplyr::slice_min(missing_inputs, with_ties = FALSE) |>
  dplyr::ungroup() |>
  dplyr::select(submission_time, group)
nrow(candidate_groups)

# only one submission time is excluded by adding this extra_inputs filter.
# This means it is likely that there is only one case
#   where the template generated was customised rather than relyin on groups
# Find it and investigate further
d |>
        dplyr::filter(submission_time == setdiff(min_missing$submission_time, candidate_groups$submission_time)) |>
        head(n=10)
# Luckily all the data in this submision used unambiguous methodologies.

# So now we can safely inspect the subset relevant to metabolomics data
# to determine the appropriate method to associate with each submission
```

first identify the representative groups
```cypher
match (g:InputGroup) where 
g.name_lower contains 'meta' or
g.name_lower contains 'hplc' or 
g.name_lower contains 'nmr' or
g.name_lower contains 'gcms' 
or g.name_lower contains 'bioch' or
g.name_lower contains 'ird' 
return collect(g.name)

```

add this to the R environment and find submissions
```R
all_meta_groups <- c("Amino acids (GCMS)", "Sugars (GCMS)", "Organic acids (GCMS)", "Phenolics (GCMS)", "Phenolics (NMR)", "Polyamines (GCMS)", "GCMS", "Pigments (NMR)", "NMR", "Metabolomics (IRD)", "Pigments (HPLC)", "Phenolics (HPLC)", "Diterpenes (HPLC)", "Unsaturated fatty acids (HPLC)", "Saturated fatty acids (HPLC)", "Volatiles (HPLC)", "Senso field (IRD Illy)", "Bioch field (VOC Illy)", "Bioch field (IRD)", "Bioch phytotrons (IRD)", "Bioch field", "Metabolomic (IRD-MPI)", "Metabolomic (IRD-MPI)", "Senso field (IRD Illy)", "Bioch field (IRD)", "Bioch field green beans (IRD)")

candidate_groups |>
        dplyr::filter(group %in% all_meta_groups)

```
This looks like all the data is either from "Bioch field green beans (IRD)" or "Bioch field (IRD)".
Only one submission was "Bioch field (IRD)" and this included both leaves and green bean samples.
So I might just create a method called "Metabolite analysis (BreedCAFS IRD)" for all of the existing metabolite data.
This is appropriate as there is no evidence that it was done using different methodologies within the project
We can then update this ontology description when I get more details in discussion with the partners.

This is much simpler then, we don't need to separate hplc/gcms/nmr etc as we never actually got that data registered.
