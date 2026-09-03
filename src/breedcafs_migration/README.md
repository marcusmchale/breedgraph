# BreedCAFS → BreedGraph Migration Plan

## Guiding Principles

1. **Migration is performed by a dedicated BreedCAFS Migration User**, belonging to a dedicated **BreedCAFS Migration Organisation/Team**.

   * The migration identity is not a human account and does not need login capability.
   * Migration commands and events therefore go through the normal BreedGraph application/domain machinery.
   * The personal account of the migration administrator remains separate from the historical provenance of migrated data.

2. **The migration team temporarily controls all migrated data.**

   * Migrated records are initially `PRIVATE`.
   * The migration team provides the required read/write/curation authority during migration.
   * Control is subsequently transferred to the appropriate BreedGraph Organisation/team.

3. **Do not migrate BreedCAFS submission identity.**

   * `submitted_by` and `submitted_at` are not carried over as BreedGraph authorship/provenance.
   * BreedCAFS users are not migrated into BreedGraph Persons.
   * Personal data is not imported unless there is an explicit requirement and appropriate GDPR basis for doing so.

4. Each migration stage follows:

   **extract → map → validate → commit**

5. Each stage produces a CSV mapping from BreedCAFS identifiers to BreedGraph identifiers where subsequent stages require those mappings.

---

# 1. Migration Bootstrap

3. Create the **BreedCAFS Migration User**.
1. Create the **BreedCAFS Migration Organisation**.
2. Create the **BreedCAFS Migration Team**.

4. Establish the required affiliations/permissions for the migration user.
5. Use the migration user as the actor for all migration commands.

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
* Green Beans

`Trees` is specifically used to represent an **unknown number of trees** of a particular germplasm within a field.

## 2.2 Location Types

Create:

* Region
* Farm
* Field

## 2.3 Layout Types

Initially create:

* Block, one nominal axis
* Row and Tree, two ordinal or coordinate axes

`Block` is a migration-era representation and may subsequently be deprecated 
once the semantic meaning of the relevant layouts has been assessed.

---

# 3. Locations

Extract:

* Countries
* Regions
* Farms
* Fields

Create them in BreedGraph with the appropriate hierarchy.

For each location created store:
```text
BreedCAFS location ID, BreedGraph Location ID
BreedGraph Location ID → BreedCAFS Partner
```

---

# 4. Layouts

Extract BreedCAFS Blocks and create BreedGraph layouts for the corresponding Field location.

Store:

```text
BreedCAFS Block ID → BreedGraph Layout ID
BreedGraph Layout ID → BreedCAFS Partner
```

---

# 5. Germplasm

Only migrate BreedCAFS varieties that participate in:

* `OF_VARIETY`, or
* `CONTAINS_VARIETY`

relationships.

This avoids importing unused BreedCAFS variety definitions.

## 5.1 BreedCAFS Varieties Node

Create a **BreedCAFS Varieties** node/group in the BreedGraph germplasm.

## 5.2 Variety Matching

For each relevant BreedCAFS variety:

1. Normalise the variety name for matching, including lowercase matching.
2. If an existing BreedGraph germplasm node has a matching name, use that node.
3. Otherwise, create a new BreedGraph germplasm node sourced from BreedCAFS.

BreedCAFS variety names are known to be unique, so exact case-insensitive name matching is considered sufficient for the mechanical migration.

Store:

```text
BreedCAFS Variety ID → BreedGraph Germplasm ID
BreedGraph Germplasm ID -> BreedCAFS Partner
```

Any subsequent curation and Release can be handled by the Germplasm curation team
and following discussions with Partner organisations.

---

# 6. Units

## 6.1 Ordinary Units

For each Item:

* Copy the `name` field.
* Set the Subject based on the BreedCAFS Item `unit` value.
* Establish the appropriate hierarchy.
* Set the `Varieties`/Germplasm field where a single variety is known.
* Set positions within Block layouts using Item Row and Column data.
* Assign the appropriate Location.

## 6.2 Fields with Multiple Germplasm

Some BreedCAFS Fields contain multiple varieties without recording the number of trees belonging to each variety.

Represent the known information explicitly using the `Trees` Subject:

```text
Field
├── Trees [Variety A]
├── Trees [Variety B]
└── Trees [Variety C]
```

Each `Trees` unit represents:

> An unknown number of trees of this germplasm within the Field.

This preserves the distinction between:

* a known individual Tree;
* a known collection of Trees;
* and a Field that is known to contain a particular germplasm but for which the number of trees is unknown.

This also allows samples from such a Field to be interpreted as representative of the mixed germplasm population
without implying that the source data identified individual trees or their quantities.

Store:
```text
BreedCAFS UID → BreedGraph Unit ID
BreedGraph Unit ID -> BreedCAFS Partner
```

## 6.3 Location Aggregation

Where locations (coordinates) assigned to units are identical, aggregate them to a single BreedGraph Location.

Assign these coordinates to the highest aggregation level where appropriate, e.g. the Field.
Assign the corresponding location as a position for each unit.

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

For branch "Stratum". This is better encoded as a layout.
  1. Create a "Stratum" LayoutType in the ontology, as a child of "Row and Tree"
  2. For Fields with stratum data, create an arrangement for the Field with Row and Tree, then nested stratum.
     This highlights an issue, Should a layout definition require a layout for each coordinate in the parent?
     We would be better to have a single layout, with 3 dimensions; row, tree, and stratum 
     to be used for defining branch positions.
               
     This does lose the fact that the stratum layout is a child of the row and tree layout.
     However, the alternative is a lot of redundant layouts. To consider this!
   
Consider other traits that may also have better encodings in BreedGraph.

For each remaining:

1. Create the corresponding BreedGraph Variable.
2. Create the associated Records.

Unused BreedCAFS Trait definitions do not need to be migrated.

---

## 7.4 Conditions

Collect BreedCAFS Conditions that have associated data.

For each:

1. Create the corresponding BreedGraph Factor.
2. Create the associated Records.

Unused BreedCAFS Condition definitions do not need to be migrated.

---

# 8. Validation and Reconciliation

Before transferring control from the migration team, validate:

* Source/target entity counts.
* Every expected BreedCAFS ID has a corresponding mapping.
* All cross-references resolve.
* Unit hierarchies are valid.
* Location hierarchies are valid.
* Layout references resolve.
* Germplasm references resolve.
* Variable and Factor references resolve.
* Curve data has the expected structure.
* Time values parse correctly.
* No unintended Person/personal data has been imported.
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

1. Deprecate the `Blocks` LayoutType.
2. Update corresponding layouts with more appropriate terminology depending on their actual meaning.
3. Where appropriate, replace structural representations with semantic Conditions.

For example, shade-level blocks in a greenhouse may be better represented as a Condition rather than as a Layout. 
The true block structure may not exist or be undefined in BreedCAFS db.

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
