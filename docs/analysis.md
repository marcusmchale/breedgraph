# Analysis workflow: notes for front-end design

The GraphQL schema describes the shape of analysis inputs and results.
This document describes the behaviour behind it that a front end should design around.
Field names are given as in GraphQL (camelCase).

## 1. Lifecycle

1. **Submit.** `analysisSubmit(analysis)` validates the configuration before anything is stored.
   - An invalid configuration returns `status: ERROR` and `result: null`, with one `errors[]` entry per problem:
     `{ name: "CONFIG_INVALID", message, path }`.
   - `path` is the input path, with list indexes as strings, e.g.
     `["anova", "terms", "2", "reference", "type"]`. Use it to attach errors to form fields.
   - All configuration errors are reported together, not only the first.
2. **Poll** `analysisSubmission(id)`. The status moves through:

   | Status | Meaning |
   |---|---|
   | `PENDING` | Stored, waiting to be prepared |
   | `PROCESSING` | Server is loading data and building observations, or later the worker is running the analysis |
   | `QUEUED` | Observations are prepared; waiting for the analysis worker |
   | `COMPLETED` | `result` is available |
   | `FAILED` | See `errors` |

   - Preparation usually takes seconds. A queued job waits for a free worker, so poll with backoff.
   - If a worker stops without reporting, its job is re-queued when the lease expires (default 1 h).
3. **Messages are written once, at the end.**
   - `errors` and `warnings` are empty until the analysis completes or fails. Don't show partial warnings.
   - Warnings from preparation are reported together with those from the worker.
   - A message names what it is about: a concept by its name (`concept 'Tree Height'`), a dataset by its concept's
     name and its ID (`dataset 'Tree Height' (#4)`), a grouping or a term by its name, and an exclusion rule by its
     place from 1. A dataset that is not found or not readable is named by its ID alone. `path` locates the field.
4. **Retention.** A submission expires `ANALYSIS_RETENTION_DAYS` (default 7) after its last status change.
   - `analysisRecentSubmissions` lists the IDs of the user's unexpired submissions, most recently updated first.
     Load each with `analysisSubmission(id)`, e.g. for a "recent analyses" list. Expired submissions drop out of the list.
5. **Edit and resubmit.**
   - The stored configuration is an exact mirror of the submitted input. `name`, `analysisType`, `datasetIds`, `exclusions` and `config` can be loaded back into the form.
   - `config` and `result` are unions selected by `analysisType`, so use fragments (`... on AnovaConfig`).

## 2. Observations: the core mental model

Every analysis operates on **observations**, not on records.

- An observation is identified by:
  - **the observation unit:** the record's base unit, or with `grouping.unit`, its nearest unit of one of the chosen
    subjects, e.g. a tree's plot (§3), and
  - **the level of every configured dimension:** time bin, germplasm, the position dimensions (location and layout
    axes), and each record-group dimension, and
  - **the study**, only when a `STUDY` term is used. Otherwise records of a unit from different studies are pooled.
- **What each setting does to observations.** An observation is a unit at one level of each configured dimension, and
  a concept's values are taken once per observation.
  - Germplasm and units of a subject as levels give each unit one level, so units of the same germplasm stay separate
    observations: its replicates.
  - Time bins, record group codes and a unit's moves (position) can split a unit's records into several observations,
    even when no term uses them. Position gives a unit that stayed put one level; a record group dimension's codes may
    split a unit's records (replicate codes always do) where its units of a subject don't.
  - The observation unit is not a dimension: it has no levels and no term. It merges units instead, rolling each up
    into the unit of a chosen subject above it.
- Each `CONCEPT` term contributes **one value per observation**. Records come from the selected datasets whose concept is the term's concept.
- **Factors describe the observations of variables.** When an analysis has a term for a variable concept,
  only variable records form observations. Each factor record is added to the observations it describes:
  - **unit:** observations of its own unit, or of the observation unit it rolls up into; otherwise those of the
    unit's descendants, where the nearest unit with a record of that factor applies (a tree takes its design block's treatment
    unless it has its own). Each path up a unit's parents stops at its first unit with a record, so on separate
    lineages (a sample pooled from two trees) the nearest records must agree: where they differ none applies, and
    `FACTOR_LINEAGES_DIFFER` lists them;
  - **time:** its time bin, or **every** time bin when it has no start or end (a design factor holds throughout);
  - **record groups:** its level, or every level when it has none in the dimension (no code, or no unit of the
    dimension's subjects, e.g. a factor on the field above the plots);
  - germplasm and the position dimensions come from the observed unit (its germplasm may be inherited, and it may be
    placed by the units above it, see section 3), so they don't constrain it.
  - A factor record that describes no observation is unused, and can leave its dataset `DATASET_FULLY_EXCLUDED`.
  - Several factor records of the same unit and level are duplicates as for any term: aggregate them, e.g. `MODE`.
  - An observation's exclusion rule (`OutlierResult.exclusion`) is built from its own records' units, not from the
    units of the factor records describing it.
  - Analyses whose concept terms are all factors are unchanged: factor records form the observations.
- Aggregation defaults to `NONE`, which is strict. Several values for one observation fail the analysis with `DUPLICATE_OBSERVATION`, listing the `recordIds`. Typical fixes to offer:
  - set an `aggregation` (MEAN, MEDIAN, …), or
  - add a dimension that separates the values, e.g. time bins for repeated measurements, or a record-group dimension for replicates.
- **Replicates.** Record groupings have an `extent`, set on each grouping of a study (its type may give a default).
  - `SHARED` codes name a group of many units, e.g. a batch or plate.
  - `WITHIN_GRAPH` codes name a group of the units of one unit graph, e.g. the design blocks of a field.
  - `WITHIN_UNIT` codes only distinguish readings of one unit at one time, e.g. replicate or subsample numbers.
  - `replicateAggregation: { aggregation, window }` combines the replicates of each reading into one value, before `aggregation`.
    `aggregation` is MEAN, MEDIAN, MIN, MAX or MODE.
  - A reading is the records of one base unit with codes of the same WITHIN_UNIT grouping and scope, and:
    - without a `window`, the same start and end;
    - with a `window` (an ISO 8601 duration, e.g. `PT5M`, `P1D`), a time within the window of the reading's first record
      (start, or end without a start). The next record outside the window starts a new reading, so readings don't chain.
      Records without a time are one reading.
    - Readings never span observations: time bins (`grouping.time`) split them.
    `aggregation` then combines readings, e.g. the units rolled up into one observation unit (`grouping.unit`) or
    times within a bin,
    so each unit and time counts once whatever its number of replicates.
  - Without `replicateAggregation`, replicates in one observation are duplicates.
    - Under `NONE`, `DUPLICATE_OBSERVATION` has the path `replicateAggregation` when the duplicates are only replicates.
    - Under another aggregation, they are pooled with the other values, and `REPLICATES_POOLED` warns where that changes the
      weighting (not for MIN, MAX or COUNT).
  - To analyse each replicate instead (descriptive statistics, outlier detection, correlation, MDS),
    configure a record-group dimension of the WITHIN_UNIT groupings (§3). `window` doesn't apply there.
  - A replicate followed over time, such as a tagged branch measured on dates further apart than any window, is better recorded as a child unit.
- Domain terms (`TIME`, `GERMPLASM`, `LOCATION`, `LAYOUT_AXIS`, `RECORD_GROUP`) need their grouping to be configured. `UNIT` and `STUDY` need no configuration.
- Configuring a dimension changes observation identity even if no term uses it.
- A record that can't be assigned to a configured dimension is dropped. Each dimension reports one `UNASSIGNED_<DIMENSION>` warning with the count and `recordIds`.
- Observations are ordered by dataset (as listed in `datasetIds`), then by record ID.

## 3. Configuring dimensions

- **Time** (`grouping.time`)
  - Bins are defined by `boundaries` (N) and `labels` (N + 1).
  - `boundary: LEFT` puts a value equal to a boundary in the lower bin; `RIGHT` puts it in the upper bin.
  - A record's period runs from the start of the period of its start to the end of the period of its end, either standing in
    for a missing other. `START` takes the start of that period, `END` its last moment and `MIDPOINT` its middle: a record
    ending `2021-05-03` is assigned by the end of that day, and a record dated `2021` by early July. Records with no time are unassigned.
- **Germplasm** (`grouping.germplasm`)
  - A unit's germplasm is its own, or else inherited from the units above it as the Units pages show it
    (`Unit.inheritedGermplasm`): the nearest unit with germplasm on each path up its parents, which must agree; a
    sample pooled from trees of two varieties has none. A unit the user cannot read stops the path where it has
    germplasm, so the units below it have none (unassigned), rather than taking a germplasm from further up.
  - Each unit's germplasm is assigned to the closest selected germplasm: itself or its nearest selected ancestor.
  - A germplasm whose selected ancestors lie on separate lineages (e.g. a cross of two selected parents) is unassigned.
  - With none selected (`germplasmIds` empty), each unit's germplasm is a level of its own. A unit with none is
    unassigned.
- **Observation unit** (`grouping.unit`, `subjectIds`): rolls each record's base unit up into its nearest unit of one
  of the subjects, the unit itself or an ancestor, e.g. trees into their plots. The rule is that of units of a subject
  as levels (record groups, below), shared as `lineages.nearest_unit_of_subjects`:
  - a base unit with no unit of the subjects at or above it is unassigned (`UNASSIGNED_UNIT`), as is one whose nearest
    such units lie on separate lineages (a sample taken from trees of two plots);
  - only units the user can read count, so a hidden unit is never an observation unit;
  - the subjects must be subjects of the ontology (`CONFIG_INVALID` otherwise).
  The base units are still reported in results. It is not a dimension: it sets what the dimensions apply to.
- **Position** (`grouping.position`): where the units of records were. It gives a `LOCATION` term and a
  `LAYOUT_AXIS` term (`layoutAxis`) for each of `axes`.
  - A position **counts** when two things hold:
    - its location is, or is below, a location of one of `locationTypeIds`;
    - with `axes`, it is in a layout that has a value on each axis. The value comes from the position's own
      layout, or from a layout above it in the layout tree, through the child layouts' positions. Axis names are unique
      along a branch.
  - A record is **placed** by the nearest unit with a position that counts: its own unit, or else the nearest units
    above it, one on each lineage. Their places must agree. So a sample measured in a lab is placed by its tree,
    unless the lab is of one of the types.
  - With `subjectIds`, a unit below a unit of one of the subjects is placed where that unit was, skipping the units in
    between.
    - Example: by Country and Tree, a sample analysed in a lab abroad is placed in its tree's country, not the lab's.
    - Units of the subjects, and units with none of them above (a field above its trees), are placed as without
      subjects.
  - **Positions count at any time.**
    - A unit may have several positions that count, because it moved between fields or was rotated between benches.
      The one holding at the record's time places the record. After a move, that is the later-starting one, as the
      Units pages show it.
    - A record without a time, or at a time when none of them holds, is placed only if they all give the same levels.
    - `time`, when given, stands in for every record's time.
  - Levels:
    - LOCATION: the nearest location of one of the types, at or above the position's location, by id.
    - LAYOUT_AXIS: the value on the axis, nested in the layout that has the axis (`layoutId|value`). Row 3 of one field
      isn't row 3 of another, and rows numbered per block stay apart. Combine axes with interactions. The levels are in
      numeric order where the values are numbers.
  - Read access (read-access.md, rule 3): some things the user can't see stop a placement, rather than letting it take
    a place from further up, which could be wrong:
    - a hidden unit with positions;
    - a position at a location or in a layout the user can't read.

    A hidden location's type isn't seen, so it isn't matched. A hidden layout's axes aren't seen either, so an axis
    above a hidden layout is unknown. A record on a hidden unit is never placed.
  - A record that can't be placed is unassigned. One `UNASSIGNED_POSITION` warning covers all the position terms.
  - For the editor, `datasetsPlaces(datasetIds, locationTypeIds)` lists where the selected datasets' records could be
    placed: the locations of the types, with unit counts, the layouts of the positions there and the axis names those
    give. It leaves out which unit places a record, and when, so it lists every place an analysis could use.
- **Record groups** (`grouping.recordGroups`)
  - `name` is unique per analysis. Terms reference the dimension by this name (`recordGroupDimension`), and results use it as the label.
  - Each grouping must belong to the study of a selected dataset. A dimension can use at most one grouping per study, and a grouping can belong to only one dimension.
  - Levels are **nested by default**: equal codes in different groupings or scopes are different levels, keyed `groupingId|scope|code`.
  - `levels` define **shared levels** that merge exactly the members they list. Members of dataset-scoped groupings need a `datasetId`, which selects the scope.
  - A shared member matching no records produces `RECORD_GROUP_LEVEL_UNMATCHED`.
  - **WITHIN_GRAPH groupings**:
    - Their codes are also nested in the root of the base unit's unit graph, keyed `groupingId|scope|rootId|code`,
      so "Block 1" of one field is a different level from "Block 1" of another.
    - The root is the unit graph's root whether or not the user can read it, so the levels don't depend on access;
      only its id is given, as for any hidden root.
    - Otherwise they are as SHARED groupings: a dimension of them can be a term and be used in ANOVA, and their codes
      can be members of shared `levels`, which merge a code across unit graphs (a member names the code in every unit graph).
  - **WITHIN_UNIT groupings** (§2, replicates):
    - Their codes are also nested in the record's base unit, keyed `groupingId|scope|unitId|code`,
      so under an observation unit each base unit's replicates stay apart.
    - Their codes can't be members of shared `levels`.
    - A dimension with WITHIN_UNIT groupings keeps each replicate as an observation. It can't be used as a term,
      and can't be used in ANOVA, where the replicates would be counted as independent observations.
      Use `replicateAggregation` instead (`CONFIG_INVALID` otherwise).
    - Scope still applies. It sets which datasets' codes refer to the same reading, e.g. the variables of one instrument reading,
      each in its own dataset of one submission.
    - Time is not part of the key, as observations already have a time bin. Analysing the replicates of a study-wide
      WITHIN_UNIT grouping across dates needs a `grouping.time`.
  - **Units of a subject as levels** (`subjectIds`): blocks that are already units (e.g. the plots of a field, holding its trees)
    need no grouping. The dimension lists their subjects instead of, or as well as, groupings.
    - Each study has one source of levels. Records of a study with one of the dimension's groupings take its codes, as
      above. Records of other studies take the nearest unit of one of the subjects: their base unit or an ancestor.
    - A dimension needs at least one grouping or subject, and a subject can belong to only one dimension.
    - The level is that unit, keyed `unit|<unitId>`. It comes from the record's base unit, as codes are on records,
      so under `grouping.unit` rolled up above these units, observations split by them as they would by codes.
    - A base unit with no such unit (e.g. the field above the plots) is unassigned. So is one whose nearest such units
      lie on separate lineages (e.g. a sample taken from trees in two plots).
    - Only units the user can read count, so a hidden unit is never a level.
    - Units can't be members of shared `levels`.
    - Otherwise they are as SHARED codes: a dimension of them can be a term, fixed or random in ANOVA.
  - Groupings are resolved when the analysis is processed, not when it is submitted.

## 4. Terms: what is valid where

| Option | Rules |
|---|---|
| `representation` | Default comes from the scale: NUMERICAL → CONTINUOUS, ORDINAL → ORDINAL, others → CATEGORICAL; binned terms default to ORDINAL. Only NUMERICAL scales can be CONTINUOUS. Domain terms are never CONTINUOUS. COMPLEX scales can't be analysed. |
| `binning` | Concept terms with NUMERICAL or DATE scales only. A binned term is not CONTINUOUS. |
| `levelOrder` | Orders CATEGORICAL/ORDINAL levels. For CATEGORICAL/ORDINAL concept terms, values not in the list become missing. For ORDINAL scales without a `levelOrder`, the order of the scale's categories is used. A NUMERICAL scale's levels are numbers written as recorded (120, not 120.0), in numeric order by default. |
| `replicateAggregation` | Concept terms only. `aggregation` is MEAN, MEDIAN, MIN, MAX or MODE (NONE, SUM and COUNT are refused), with the scale rules of `aggregation`. `window` is an optional ISO 8601 duration longer than zero. Not with a COUNT `aggregation`. See §2, replicates. |
| `aggregation` | Concept terms only. MEAN, MEDIAN and SUM need a NUMERICAL scale. MIN and MAX need numbers, dates or ordinal values. MODE breaks ties by the lowest value. COUNT always gives a CONTINUOUS count. |
| `transformations` | Applied in order, to CONTINUOUS concept terms only, after aggregation. LOG needs values > 0, LOG1P > −1, SQRT ≥ 0, RECIPROCAL ≠ 0; otherwise the analysis fails with `INVALID_TRANSFORMATION` and `recordIds`. STANDARDIZE needs at least two distinct values. |
| `effect`, `randomSlopeTerms` | ANOVA only. Random slopes are only allowed on RANDOM terms. |

Requirements by analysis:

- **ANOVA**
  - `response` must be one of the terms: a CONCEPT term, CONTINUOUS, with no effect and no binning.
  - At least one other term is required. Terms with no `effect` are FIXED.
  - RANDOM terms must be categorical and can't appear in `interactions`. For nested random effects, use a unit or record-group dimension instead.
  - `estimatedMeans` terms and `by` terms must be FIXED categorical model terms.
  - `TRT_VS_CTRL` needs exactly one term and a `control` level.
- **Descriptive statistics**
  - At least one CONCEPT term is required, and at least one must be CONTINUOUS or ORDINAL as its scale resolves it, or
    the analysis fails with `INCOMPATIBLE_SCALE`: CATEGORICAL terms only group the others.
  - Interactions and estimated-means terms must be categorical terms.
- **Correlation:** at least two CONCEPT terms, each CONTINUOUS or ORDINAL. ORDINAL terms are ranked by level order.
- **MDS and outlier detection**
  - CONCEPT terms must be CONTINUOUS.
  - MDS clustering needs `clusters`.
- Domain terms can be added to any analysis. In MDS, correlation and outlier detection they don't change the analysis itself: identity comes from the grouping, and STUDY becomes part of identity.

## 5. Exclusions

`exclusions` is a list of rules:

- A record is excluded if it matches **any** rule.
- Within a rule, **all** given criteria must match. Within a list criterion, **any** element may match.
- Matching is exact: excluding a germplasm doesn't exclude its descendants, and excluding a unit doesn't exclude its children. `unitIds` and `germplasmIds` refer to the record's base unit, and its germplasm may be inherited (section 3).
- **Time.** `start` (inclusive) and `end` (exclusive) are compared with the record's start/end interval, which matches if it overlaps. Null means unbounded. A record with no time never matches a time-bounded rule.
- **Positions.** Position criteria use the unit's own position history, not the record time. Unlike position
  grouping, they match a location and layout exactly, with axes by index.
  - A position interval matching the criterion must overlap the rule's `[start, end]`.
  - If a rule has only position criteria and time bounds, record time isn't checked.
- **Feedback.** Each rule reports an `EXCLUDED_BY_CONFIG` warning with its match count. Show it next to the rule; zero matches usually means a mistake.
- `DATASET_FULLY_EXCLUDED` means no records of a dataset reached an observation, through exclusions or unassignment.

Building exclusions from results:

- `UNASSIGNED_*` warnings and `DUPLICATE_OBSERVATION` errors carry `recordIds`, which can be turned into a `recordIds` rule.
- `OutlierResult.exclusion` is a ready-to-use rule built from the observation's base units, time bin and record-group codes.
- That outlier rule is approximate:
  - it matches any record overlapping the time bin, even one assigned to a neighbouring bin;
  - with several record-group dimensions, it matches any of the observation's codes.

## 6. Reading results

Term levels (`AnalysisTermLevel.level`) are strings:

| Term | Level value |
|---|---|
| GERMPLASM, UNIT, STUDY | IDs; resolve the names in the UI |
| TIME | Bin labels |
| LOCATION | IDs (`AnalysisGroup.locationId`); resolve the names in the UI |
| LAYOUT_AXIS | `layoutId\|value`, the value nested in the layout that has the axis; `AnalysisGroup.layoutAxes` has the parts |
| RECORD_GROUP | A shared level label, a `grouping\|scope\|code` key (`grouping\|scope\|unit\|code` for WITHIN_UNIT groupings, `grouping\|scope\|root\|code` for WITHIN_GRAPH), or `unit\|<unitId>` for a unit level, whose `unitId` is set and `groupingId` null; `AnalysisRecordGroupAssignment` has the parts |
| CONCEPT | Category or bin labels |

Results per analysis:

- **Descriptive**
  - For each CONTINUOUS or ORDINAL concept term, in the order given, there is one row with `levels: []` covering all observations, then one row per combination of levels of the CATEGORICAL/ORDINAL terms, an ORDINAL term's own left out of its rows.
  - A CONTINUOUS term's rows have the mean, standard deviation and error, and the quantiles. An ORDINAL term's have `ordinal` instead: the count in each category, in its order, with its share, and the minimum, quartiles, median and maximum as categories (the first whose cumulative share reaches each quantile), but no mean, which would take the steps between categories as equal.
  - `group` is set only when every level belongs to a domain term.
  - `estimatedMeans` come from a linear model of each CONTINUOUS term on the categorical terms (plus interactions). `response` identifies the term.
- **Correlation:** uses pairwise complete observations. A value is null when fewer than 3 observations pair up.
- **Outliers**
  - Thresholds are fixed: Z_SCORE |z| > 3; IQR outside Q1 − 1.5·IQR or Q3 + 1.5·IQR (`score` is the distance in IQR units); MAHALANOBIS squared distance with χ² p < 0.001.
  - MAHALANOBIS uses complete observations, and its `term` and `value` are null.
  - Results are sorted by `score`, highest first.
- **MDS**
  - Uses CONTINUOUS terms, standardised, on complete observations; incomplete observations are omitted. Constant terms are dropped.
  - MINKOWSKI distance uses p = 3.
  - Clusters are computed on the standardised data, not the MDS coordinates.
- **ANOVA**
  - **Fixed effects only:** a linear model. Tables include `residual` and no `denominatorDegreesOfFreedom`.
  - **Any RANDOM term:** a mixed model (lmerTest). Tables include `denominatorDegreesOfFreedom` (Satterthwaite or Kenward-Roger), `randomEffects` (variance components; `slope` is null for intercepts), and `residual: null`.
  - `TYPE_III` uses sum-to-zero contrasts.
  - Rows are complete observations of the model terms.
  - In estimated means, `levelsA`/`levelsB` give the compared means explicitly, so don't parse `label`. Labels follow emmeans, e.g. `"a1 - a2"`.
  - `significant` uses the analysis `alpha`.
  - `MODEL_NOT_CONVERGED` is a warning: show the result with a caveat.

## 7. Message codes

| Code | Kind | Suggested UI action |
|---|---|---|
| `CONFIG_INVALID` | error | Highlight the field at `path` |
| `DATASET_NOT_FOUND` / `DATASET_NOT_READABLE` | error | Remove the dataset, or request access |
| `CONCEPT_NOT_IN_DATASETS` | error | Add a dataset for the concept, or remove the term |
| `INCOMPATIBLE_SCALE` | error | Change the representation, aggregation or binning at `path` |
| `GROUPING_NOT_FOUND` | error | Fix the grouping selection at `path` |
| `DUPLICATE_OBSERVATION` | error | Suggest an aggregation or an extra dimension; show `recordIds`. With the path `replicateAggregation`, the duplicates are replicates: suggest a replicate aggregation |
| `INVALID_TRANSFORMATION` | error | Remove the transformation, or exclude `recordIds` |
| `INSUFFICIENT_DATA` | error | Too few observations: relax exclusions or dimensions |
| `SINGLE_LEVEL_TERM` | error (model terms) / warning (descriptive) | The term has one level in the analysed data; remove it |
| `MODEL_FAILED` | error | Show the R message; simplify the model |
| `INTERNAL_ERROR` | error | Generic failure; retry or report |
| `EMPTY_DATASET`, `UNUSED_DATASET` | warning | The dataset contributed nothing |
| `EXCLUDED_BY_CONFIG` | warning | Match count per rule (`path` = `["exclusions", i]`) |
| `UNASSIGNED_TIME` / `_GERMPLASM` / `_UNIT` / `_POSITION` / `_RECORD_GROUP` | warning | Offer to exclude `recordIds`, or adjust the dimension |
| `MISSING_VALUES` | warning | Some observations lack a value for the term |
| `DATASET_FULLY_EXCLUDED` | warning | The dataset contributed no observations |
| `RECORD_GROUP_LEVEL_UNMATCHED` | warning | A shared level member matched no records |
| `REPLICATES_POOLED` | warning | Replicates were pooled by the term's aggregation; suggest a `replicateAggregation` |
| `FACTOR_LINEAGES_DIFFER` | warning | Factor records on separate lineages above some units differ (a sample pooled from trees given different treatments), so none describes them; show `recordIds`, suggest recording the factor on those units |
| `MODEL_NOT_CONVERGED` | warning | Show the result with a caveat |
