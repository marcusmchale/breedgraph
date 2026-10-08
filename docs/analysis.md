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
4. **Retention.** A submission expires `ANALYSIS_RETENTION_DAYS` (default 7) after its last status change.
   - `analysisRecentSubmissions` lists the IDs of the user's unexpired submissions, most recently updated first.
     Load each with `analysisSubmission(id)`, e.g. for a "recent analyses" list. Expired submissions drop out of the list.
5. **Edit and resubmit.**
   - The stored configuration is an exact mirror of the submitted input. `name`, `analysisType`, `datasetIds`, `exclusions` and `config` can be loaded back into the form.
   - `config` and `result` are unions selected by `analysisType`, so use fragments (`... on AnovaConfig`).

## 2. Observations: the core mental model

Every analysis operates on **observations**, not on records.

- An observation is identified by:
  - **the unit:** the record's base unit, or its selected parent unit when `grouping.unit` is set, and
  - **the level of every configured dimension:** time bin, germplasm, position, and each record-group dimension, and
  - **the study**, only when a `STUDY` term is used. Otherwise records of a unit from different studies are pooled.
- Each `CONCEPT` term contributes **one value per observation**. Records come from the selected datasets whose concept is the term's concept.
- Aggregation defaults to `NONE`, which is strict. Several values for one observation fail the analysis with `DUPLICATE_OBSERVATION`, listing the `recordIds`. Typical fixes to offer:
  - set an `aggregation` (MEAN, MEDIAN, …), or
  - add a dimension that separates the values, e.g. time bins for repeated measurements, or a record-group dimension for replicates.
- Domain terms (`TIME`, `GERMPLASM`, `POSITION`, `RECORD_GROUP`) need their grouping to be configured. `UNIT` and `STUDY` need no configuration.
- Configuring a dimension changes observation identity even if no term uses it.
- A record that can't be assigned to a configured dimension is dropped. Each dimension reports one `UNASSIGNED_<DIMENSION>` warning with the count and `recordIds`.
- Observations are ordered by dataset (as listed in `datasetIds`), then by record ID.

## 3. Configuring dimensions

- **Time** (`grouping.time`)
  - Bins are defined by `boundaries` (N) and `labels` (N + 1).
  - `boundary: LEFT` puts a value equal to a boundary in the lower bin; `RIGHT` puts it in the upper bin.
  - `START`, `END` and `MIDPOINT` fall back to whichever time the record has. Records with no time are unassigned.
- **Germplasm** (`grouping.germplasm`)
  - Each unit's germplasm is assigned to the closest selected germplasm: itself or its nearest selected ancestor.
  - A germplasm whose selected ancestors lie on separate lineages (e.g. a cross of two selected parents) is unassigned.
- **Unit** (`grouping.unit`): replaces each base unit with its closest selected parent unit. The base units are still reported in results.
- **Position** (`grouping.position`)
  - A unit matches if it has a position at `locationId` (and `layoutId`, if given), at `time` or at any time.
  - The unit's group is:
    1. the matching explicit `positions` entry, if any;
    2. otherwise its values on `axisIndexes`;
    3. otherwise the whole location.
  - A unit that matches more than one group (e.g. it moved, and `time` is null) is unassigned.
- **Record groups** (`grouping.recordGroups`)
  - `name` is unique per analysis. Terms reference the dimension by this name (`recordGroupDimension`), and results use it as the label.
  - Each grouping must belong to the study of a selected dataset. A dimension can use at most one grouping per study, and a grouping can belong to only one dimension.
  - Levels are **nested by default**: equal codes in different groupings or scopes are different levels, keyed `groupingId|scope|code`.
  - `levels` define **shared levels** that merge exactly the members they list. Members of dataset-scoped groupings need a `datasetId`, which selects the scope.
  - A shared member matching no records produces `RECORD_GROUP_LEVEL_UNMATCHED`.
  - Groupings are resolved when the analysis is processed, not when it is submitted.

## 4. Terms: what is valid where

| Option | Rules |
|---|---|
| `representation` | Default comes from the scale: NUMERICAL → CONTINUOUS, ORDINAL → ORDINAL, others → CATEGORICAL; binned terms default to ORDINAL. Only NUMERICAL scales can be CONTINUOUS. Domain terms are never CONTINUOUS. COMPLEX scales can't be analysed. |
| `binning` | Concept terms with NUMERICAL or DATE scales only. A binned term is not CONTINUOUS. |
| `levelOrder` | Orders CATEGORICAL/ORDINAL levels. For CATEGORICAL/ORDINAL concept terms, values not in the list become missing. For ORDINAL scales without a `levelOrder`, the scale's category rank is used. |
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
  - At least one CONCEPT term is required.
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
- Matching is exact: excluding a germplasm doesn't exclude its descendants, and excluding a unit doesn't exclude its children. `unitIds` and `germplasmIds` refer to the record's base unit.
- **Time.** `start` (inclusive) and `end` (exclusive) are compared with the record's start/end interval, which matches if it overlaps. Null means unbounded. A record with no time never matches a time-bounded rule.
- **Positions.** Position criteria use the unit's position history, not the record time.
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
| POSITION | `location\|layout\|coordinates` key; `AnalysisGroup.position` has the structured position |
| RECORD_GROUP | A shared level label, or a `grouping\|scope\|code` key; `AnalysisRecordGroupAssignment` has the parts |
| CONCEPT | Category or bin labels |

Results per analysis:

- **Descriptive**
  - For each CONTINUOUS concept term there is one row with `levels: []` covering all observations, then one row per combination of levels of all CATEGORICAL/ORDINAL terms.
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
| `UNIT_NOT_FOUND` / `GROUPING_NOT_FOUND` | error | Fix the grouping selection at `path` |
| `DUPLICATE_OBSERVATION` | error | Suggest an aggregation or an extra dimension; show `recordIds` |
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
| `MODEL_NOT_CONVERGED` | warning | Show the result with a caveat |
