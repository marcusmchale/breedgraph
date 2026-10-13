# BreedCAFS → BreedGraph Migration Plan

## Guiding Principles

**Migration is performed by a dedicated BreedCAFS Migration User**, affiliated with a dedicated **BreedCAFS Migration Team** under the **University of Galway** organisation.

   * The migration identity is not a human account and does not need login capability.
   * Migration commands and events therefore go through the normal BreedGraph application/domain machinery.
   * The personal account of the migration administrator remains separate from the historical provenance of migrated data.
   * The University of Galway root team declares the legal entity, so the university is the data controller
     of Persons created by the migration until they are handed over (see docs/person.md §2).

**The migration team temporarily controls all migrated data.**

   * Migrated records are initially `PRIVATE`.
   * The migration team provides the required read/write/curation authority during migration.
   * Control is subsequently transferred to the appropriate BreedGraph Organisation/team.

**Attribute data to the people who recorded it.**

   * Each BreedCAFS Record has a free-text `person` field naming who recorded it.
     These values are curated into BreedGraph Persons and set as `contributors` of the datasets their records fall into.
     The BreedCAFS user who submitted a record is used only where `person` is empty.
   * A Person stores only a name and an institution, the full name of the BreedCAFS Partner,
     with no team affiliation, email or username. Names can be refined later, but must be unique per Person.
   * Persons are created `PRIVATE` with the migration team as write team, and stay `PRIVATE` until handover;
     the responsible organisation then decides on release.
   * The migration administrator gives the informed attestation for each Person.
   * `submitted_at` is not carried over, as BreedGraph sets the submission time when records are created.
   * Person data (extracted values, the curated mapping, and the BreedCAFS → Person id mapping)
     is kept only in the untracked `src/data/breedcafs_migration/` directory, never in git.

Broadly we will follow the follow phases:
  
1. Extract and dump all data required for the migration to csv.
2. Create the migration user account and context
2. Prepare ontology entries
3. Create germplasm
4. Create locations
5. Create layouts
6. Create units
7. Create the program, trials and studies
8. Create datasets
9. Create Persons and set dataset contributors
 


---
# 1. Extract

To get an overview of the schema, a useful command is:
```cypher
CALL db.schema.nodeTypeProperties()
```

## [1.1 Extract Locations](1_1_Extract_Locations.md)

## [1.2 Extract Layouts](1_2_Extract_Layouts.md)

## [1.3 Extract Germplasm](1_3_Extract_Germplasm.md)

## [1.4 Extract Units](1_4_Extract_Units.md)

## [1.5 Extract Inputs](1_5_Extract_Inputs.md)

## [1.6 Extract Records](1_6_Extract_Records.md)

## [1.7 Extract Persons](1_7_Extract_Persons.md)


# 1. Migration Bootstrap

1. Create the **BreedCAFS Migration User**.
2. Create the **BreedCAFS Migration Team** as a child of the University of Galway root team
   (the University of Galway organisation, with its declared legal entity, already exists in production).
3. Establish the required affiliations/permissions for the migration user on the migration team.
4. Use the migration user as the actor for all migration commands.

The migration team provides temporary control rather than final ownership.

---

# 2. Ontology

## 2.1 Subjects

Create Subjects:

* Field
* Trees
* Tree
* Branch
* Leaves
* Leaf
* Cherries
* Cherry
* Green Beans

`Trees` represents a group of trees within a field whose individual trees are not identified,
e.g. a block (6.4), or the trees of one germplasm in a field (6.2).

The ontology preparation (ontology.py) also creates the variables and factors of the curated inputs (1.5),
and the treatment factors for blocks named after a treatment (6.4).

## 2.2 Location Types

Create:

* Region
* Farm
* Field
* Research Center, for where samples were analysed (IRD Montpellier)

## 2.3 Layout Types

Create, with ordinal axes (1.2):

* Row and Tree

Blocks are units (6.4), not layouts.

## 2.4 Record Group Types

* Replicate, for replicate codes (7.6)

---

# 3. Locations

From field_farm_region_country.csv (1.1.1), create the Regions, Farms and Fields (locations.py):

* Each BreedCAFS country is the root of a BreedGraph region, found by its ISO 3166-1 alpha-3 code,
  or created and released `PUBLIC`, as countries are. BreedCAFS "Vietnam" is "Viet Nam" (VNM).
  Countries are shared roots, so a country created by the migration is not transferred at handover.
* Regions, Farms and Fields are matched by name and type under their parent, or created `PRIVATE`,
  controlled by the migration team. Field names repeat across farms (e.g. "IRAD Station" in Cameroon).
* Each Field is given its coordinates from field_lat_long.csv (1.1.2) when created.

Countries are cached in the API's state store, which is only loaded at startup:
after the migration creates a country, run scripts/load_state_store.py so the API sees it as stored.

The one location given by the "Location (text)" input, "Montpellier/ IRD", is the position of the samples in sample_positions.csv (1.2.2).
It is created as "IRD Montpellier", a Research Center under France (`SAMPLE_LOCATIONS` in locations.py),
and saved in sample_location_ids.csv.

Saved location_ids.csv: each BreedCAFS field and its location.

---

# 4. Layouts

From field_layout_types.csv (1.2.1), create the layouts at each Field's location:

* `row_and_tree`: a "Row and Tree" layout for the Field, or one for each Block where rows and trees are numbered per block (field 29).
* Field 5 (ED5, Vietnam) has two plantings, each with a "Row and Tree" layout:
  * 368 trees in Block 1 and Block 2, planted on 26 June 2018, with a variety, one tree to each position (rows 1–23, columns 1–16).
  * 1,178 trees planted on 15 July 2018 in rows and columns of their own (rows 1–12, columns 1–7),
    the "ED5 July 2018 planting: Row and Tree" layout. They have no variety, and are named with a code citing another
    Vietnam field (ED2–ED12), e.g. "7-ED6-1D2", probably the field they were collected from.
    Many share a position (73 positions, 2 to 38 trees each). Their positions are migrated as recorded,
    and the duplicate positions are to be resolved with the partner (§11).
  Trees are assigned to the plantings by name (`PLANTINGS` and `tree_group` in layouts.py).
Tree positions are recorded in the Row and Tree layouts, from unit_positions.csv (1.2.2).
Branch strata are not positions: each branch gets a record of the Stratum factor (6.1), as the stratum was set by the sampling design.
In fields 18–24 (Nicaragua) the branches were taken from tree samples taken from a block or the field,
with no row or tree recorded, so a stratum layout could not have placed them anyway.

Each layout is the root of its own arrangement (layouts.py).
Layouts are named after their Field (and Block or planting), e.g. "ED1: Row and Tree", with axes Row and Tree.
They are matched by name and type at the Field's location, or created `PRIVATE`, controlled by the migration team.

Saved layout_ids.csv: each Field (and Block or planting) and BreedCAFS layout type, and its layout.

---

# 5. Germplasm

From varieties.csv (1.3.1), only migrate BreedCAFS varieties that participate in:

* `OF_VARIETY`, or
* `CONTAINS_VARIETY`

relationships.

This avoids importing unused BreedCAFS variety definitions.

## 5.1 BreedCAFS Varieties Node

Create a **BreedCAFS Varieties** germplasm entry, the source of the varieties created from BreedCAFS,
whose sources are to be curated.

## 5.2 Variety Matching

For each relevant BreedCAFS variety (germplasm.py):

1. Normalise the variety name for matching: case-insensitive, with whitespace collapsed.
2. If a germplasm entry the migration user can read has a matching name or synonym, use that entry.
3. If the name is used by an entry the migration user cannot read, stop and report it:
   the migration team needs read access to that entry, or it needs to be released, before running again.
4. Otherwise, create a germplasm entry, `PRIVATE` and controlled by the migration team,
   with the BreedCAFS Varieties entry as its source, unless it is a cross or a graft (below).

BreedCAFS variety names are known to be unique, so exact case-insensitive name matching is considered sufficient for the mechanical migration.

47 names are crosses, named "maternal x paternal" (all from Nicaragua), e.g. "T5296 x Rume Sudan".
Each is its own germplasm entry, with MATERNAL and PATERNAL source relationships from its parents.
Parents are matched ignoring case and spaces, as some are written without the space of the variety,
e.g. "ET26A1" for "ET26 A1". The 8 parents that are not BreedCAFS varieties or existing entries
(ET1, ET1A1, ET2A1, ET25bcA2, ET27A6, ET40, ET52, ET57) are created under the BreedCAFS Varieties entry, for curation:
some may be the same lines as varieties written more fully (e.g. ET40 and ET40 A5).

Three names are grafts, named "scion / rootstock": "H3 / Nemaya", "Nemaya / Villa Sarchi" and "Starmaya / Nemaya",
used by the trees named "Grafted". Each is its own germplasm entry, with TISSUE source relationships
from its scion and its rootstock, described as "Scion" and "Rootstock", rather than the BreedCAFS Varieties entry.
The nomenclature is trusted, so Nemaya is the scion in "Nemaya / Villa Sarchi".
The four parts are varieties in their own right, so exist as entries.

Units are given their germplasm from item_variety.csv (1.3.2).

Saved germplasm_ids.csv: each variety, its germplasm entry, and whether it matched an existing entry or was created from BreedCAFS.

Any subsequent curation and Release can be handled by the Germplasm curation team
and following discussions with Partner organisations.

---

# 6. Units

## 6.1 Ordinary Units

Each Field is a block, rooted at a Field unit positioned at the Field's location (units.py).
For each other Item, a unit in its Field's block, `PRIVATE` and controlled by the migration team:

* Its name is the Item `name`, or its uid where it has none, and its description "BreedCAFS item <uid>",
  by which a second run finds the units created before.
* Its Subject is the Item type, or the sample `unit` for samples (blocks are `Trees`, 6.4).
* Its parents are the Items it is in or was taken from, or else its Field.
* Its germplasm is set where a single variety is known (item_variety.csv, 5). No sample has more than one variety.
  A sample pooled from parents of different varieties (only 42_S161, 1.3.2) is left without germplasm,
  its parents saying what it contains.
* Trees are positioned in their layout (unit_positions.csv, 4). Coordinates are stored as strings, as the API gives them.
* Branches get a record of the Stratum factor (condition Canopy Position, an ordinal scale Lower, Middle, Upper)
  from branch_strata.csv, as the stratum was set by the sampling design. They have no positions of their own.
* Samples analysed at IRD Montpellier are positioned there, from the date given (sample_positions.csv).

Factor records for units, the block treatments (6.4) and the strata of branches,
are saved in factor_records.csv for the datasets phase. Saved unit_ids.csv: each Item and its unit.

## 6.2 Fields with Multiple Germplasm

Some BreedCAFS Fields contain multiple varieties, and samples were taken from the Field (or a block) as a whole,
e.g. 2,310 tree samples in fields 18–24 and about 150 green bean samples.
These samples stay under their Field (or block), with their variety as their germplasm:
no `Trees` unit per variety is created, as the variety already says which population a sample represents.

## 6.3 Location Aggregation

Where locations (coordinates) assigned to units are identical, aggregate them to a single BreedGraph Location.

Assign these coordinates to the highest aggregation level where appropriate, e.g. the Field.
Assign the corresponding location   as a position for each unit.

## 6.4 Blocks

BreedCAFS Blocks group the trees of a Field, and have no data of their own.

* Blocks named as numbered blocks ("Block 1", "Block A", and the "Bulk" block of field 22) become `Trees` units under their Field,
  named as the block is in BreedCAFS (block names are only unique within a Field).
  Their trees are their children, and samples taken from the block (about 12,750 with data, e.g. most cherry and green bean samples)
  keep the block as their parent.
* Blocks named after a treatment are not units. Their trees are placed directly under the Field,
  and each tree gets a record of the treatment, with the block name as the category:
  * "Full Sun" and "Shade" in fields 25–27 (La Hilda, Costa Rica): the "Shade Treatment" factor (shade cloth).
  * "Shade Level 1" to "Shade Level 5" and "2 Years Low Light Acclimation" in field 35 (Copenhagen greenhouse):
    the "Shade Level Treatment" factor (shade cloth).

  Both describe the Light Availability condition, as the curated "Shade level" factor (a percentage) does,
  and differ only in their scale, keeping the labels of each experiment together.

  These factors, and the Stratum factor, are created with the ontology (`DESIGN_FACTORS` in ontology.py).

## 6.5 Skipped Items

[extract_skipped_items.cypher](cypher/extract_skipped_items.cypher) lists the items that are not migrated,
as they have no data and no other item depends on them:

* 4,037 samples whose sample unit (subject) was never set, registered but never used.
* 2 blocks without trees or samples (blocks "1" and "3" of field 35).

Saved this as skipped_items.csv. No record in records.csv or curves.csv belongs to these items.

---

# 7. Inputs, Variables, Factors and Records

## 7.1 Curve — Fluorescence ~ Time

BreedCAFS contains one Curve input:

**Fluorescence ~ Time**

recorded at the La Tomatera field.

Create a BreedGraph Variable:

**Fluorescence ~ Time**

with:

* Trait: **Chlorophyll Fluorescence**
* Method: **Pocket PEA** — confirm during validation
* Scale:

  * Type: `Complex`
  * Name: `Relative Intensity`
* JSON describing the data format, including item index column.

### Curve data

Collate the curve values into a CSV file.

The data should include:

* Item ID
* Time
* Replicate
* Curve Y values

Do not include Person information.

Retain the original `text_time` value as appropriate.
Validate that the time values can be parsed as `numpy.datetime64`.
Create BreedGraph records for each relevant Item referencing the resulting data file.

The CSV should be treated as an immutable migration data artefact.

---

## 7.2 Properties

Most BreedCAFS Properties are already represented through migrated unit attributes and do not require separate records.

Migrate only:

* Elevation
* Harvest Time / Harvest Date
* Sowing Date
* Planting Date

Create Variables:

* **Elevation**
* **Harvest**
* **Sowing**
* **Planting**

Merge Harvest Time and Harvest Date into the single **Harvest** Variable.

Create records for each from values in the corresponding Records.

---

## 7.3 Traits

Collect BreedCAFS Traits that have associated data.

match (:RecordType {name:'Trait'})<-[:OF_TYPE]-(i:Input)<-[:FOR_INPUT*..2]-()<-[:RECORD_FOR]-(:Record) return distinct i

For branch "Stratum": recorded as the Stratum factor on each branch (6.1), not as a trait.
   
For each remaining:

1. Create the corresponding BreedGraph Variable.
2. Create the associated Records.

Unused BreedCAFS Trait definitions do not need to be migrated.

---

## 7.4 Conditions

Collect BreedCAFS Conditions that have associated data.

match (:RecordType {name:'Condition'})<-[:OF_TYPE]-(i:Input)<-[:FOR_INPUT*..2]-()<-[:RECORD_FOR]-(:Record) return count(distinct i)

For each:

1. Create the corresponding BreedGraph Factor.
2. Create the associated Records.

Unused BreedCAFS Condition definitions do not need to be migrated.

## 7.5 Program, Trials and Studies

All migrated data belongs to one **BreedCAFS** Program, with Trials and Studies by the kind of data and where it was recorded:

| Trial | Studies |
|---|---|
| Field trials | One per country: Cameroon, Costa Rica, French Guiana, Nicaragua, Vietnam |
| Controlled environment | Denmark (greenhouse rooms in Copenhagen) |
| Sample analyses | Metabolomics (IRD), across Costa Rica, Nicaragua and Vietnam; Mineral analysis (Costa Rica) |

Each record is assigned a Study, not each submission: some submissions mix sample analyses with field data,
and one covers fields in two countries.

  * Records of inputs with the `Metabolites` term go to Metabolomics, and those with the `Elements` term to Mineral analysis.
  * Other records go by the country of their item's field, with Denmark to the controlled environment Study.

The Program ("BreedCAFS", Breeding Coffee for Agroforestry Systems), Trials and Studies are created `PRIVATE`,
controlled by the migration team, or matched by name (programs.py, with `study_for` for the rule above).
Each Study has a dataset-scoped Replicate grouping, of the Replicate record group type in the ontology,
scoped in the datasets phase (7.6). Saved study_ids.csv: each Study, its id and its Replicate grouping.
Each Study's start and end are the first and last times of its records: record times, and condition starts and ends
where given (BreedCAFS stores False for most). French Guiana has no timed records, so no dates.

## 7.6 Datasets

A Dataset holds the records of one input, from one submission, in one Study.
A Study can hold several Datasets for the same variable or factor.

  * Replicate codes become a dataset-scoped record grouping on each Study,
    with one scope per submission: the Datasets of that submission in the Study.
    Replicate codes are then only compared within the records submitted together.
  * Contributors are the Persons of the submission's attribution values for that input
    (submissions.csv, attribution_persons.csv and persons.csv, see [1.7](1_7_Extract_Persons.md)).
  * Records loaded without a submission (the photosynthesis data) are grouped as one submission per input.

---

# 8. Validation and Reconciliation

Before transferring control from the migration team, validate:

* Source/target entity counts, accounting for the items in skipped_items.csv.
* Every expected BreedCAFS ID has a corresponding mapping.
* All cross-references resolve.
* Unit hierarchies are valid.
* Location hierarchies are valid.
* Layout references resolve.
* Germplasm references resolve.
* Variable and Factor references resolve.
* Curve data has the expected structure.
* Time values parse correctly.
* Only the curated Persons have been imported, each with a name only, and every `person` value maps to at least one Person.
* Every dataset's contributors match the `person` values of its records.
* All migrated data remains controlled by the migration team.
* All migrated data has the expected initial release state.

Resolve any migration errors before proceeding to handover.

---

# 9. Partner → Organisation Handover

For each BreedCAFS Partner:

1. Determine whether the Partner wishes to be represented on BreedGraph.
2. Identify the corresponding BreedGraph Organisation.
3. Transfer control from the BreedCAFS Migration Team to the appropriate Organisation/team.
4. Establish the appropriate read/write/curation affiliations.

The migration team should remain the controlling team until the responsible Organisation has been identified.

---

# 10. Release State

After control has been transferred:

* Allow Organisations to release appropriate Locations, Layouts and Units independently where required.
* Discuss the release state of other migrated data with the controlling Organisations.
* Keep data `PRIVATE` where ownership or release intent has not been established.
* Promote data to `REGISTERED` or `PUBLIC` only as agreed with the responsible Organisation.

The mechanical migration itself should not make uncertain publication decisions.

---

# 11. Ontology and Layout Cleanup

Once migrated data has been reviewed:

1. Resolve the duplicate positions in field 5's July 2018 planting with the partner: whether each position is a plot of several trees,
   and what the tree codes (e.g. "7-ED6-1D2") mean beyond the field they cite. Review the per-block layouts of field 29 too.
2. Review the blocks migrated as `Trees` units: some may be replicate blocks of a design, better described by a Design.

Blocks named after a treatment are already migrated as factor records (6.4).

---

# 12. Germplasm Resolution

Resolve remaining germplasm questions with the relevant submitting Organisations.

The mechanical migration uses case-insensitive exact name matching.

More detailed biological/curatorial reconciliation is a post-migration activity rather than a prerequisite for importing the data.

---

# 13. Migration Artefacts

Each migration stage should retain its mapping information in CSV form, for example:

```text
BreedCAFS ID → BreedGraph ID
```

These mappings provide the identifiers required by subsequent migration stages and provide a persistent record of the migration.

The migration artefacts should be retained after migration for audit, troubleshooting and provenance purposes.

The BreedCAFS Migration Team should likewise not be removed immediately after migration;
it can remain as historical provenance for data that was initially migrated under its control.
