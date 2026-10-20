# Front-end changes

The API changes the front end (`breedview`) has yet to make, with what breaks and the work each needs. Field names are
given as in GraphQL (camelCase). A section is removed once breedview implements it; the earlier ones (Persons,
invitations, transfers, record group extents, the renamed areas, contributions, times, bulk control, Person views and
maps) are in this file's history, last in full at `021f830` (`git show 021f830:docs/front-end-changes.md`). Where they
describe the API rather than the work, the schema's descriptions, README.md and the design notes in `docs/` have it.

## Where the front end is

breedview's master (`4069acf`) implements every API change up to 2026-10-19. Not yet: removing optional links with
null and units as record group levels (both 2026-10-20, below).

**For the next API change:** add a section for it, with what breaks and the work it needs; then, in breedview,
regenerate the schema files with the API running (`node scripts/fetchGraphqlSchema.js` writes `schema.graphql`,
`possibleTypes.json` and `unionTypes.json`) and run the check script below.

## Checking the front end against the API

```bash
set -a; . instance/breedgraph.env; . instance/private.breedgraph.env; set +a
.venv/bin/python scripts/check_front_end_queries.py ../breedview/src
```

It builds the API's schema and validates every operation in the front end's `.graphql` files, with the fragments each uses, and exits with 1 if any fails.
It does not check variables, so input fields built in JavaScript (as `roleIds` was) need a search.
Rerun it after changing the front end, and after any API change, before releasing either.

## Removing optional links with null

An update can now remove an optional link: omitted, it is unchanged, and `null` removes it. Until now null meant
unchanged, so these links could not be removed once set:
- `StudyUpdate.designId` and `licenceId` (`programsUpdateStudy`);
- `UnitUpdate.subjectId` and `germplasmId` (`unitsUpdateUnit`);
- `GermplasmUpdate.originId` (`germplasmUpdateEntry`).

The other fields of these inputs are unchanged (omitted or null, they are kept). `GermplasmUpdate.referenceIds` no
longer defaults to `[]`: omitted, the references are now kept rather than removed.

In breedview:
- `UpdateStudyModal.vue` sends `licenceId: selectedLicence.value?.id || null`, so a study without a licence now sends
  a removal, which is what the form shows. Add a "Remove" button beside "Change" that clears `selectedLicence`. A
  licence the editor can't read comes as a placeholder with its id (`read-access.md` rule 2), so it is sent back and
  kept. It sends `designId: values.designId || undefined`, so clearing the select changes nothing: send `null`.
- `updateUnitModal.vue` sends `subjectId` and `germplasmId` as `|| undefined`: send `null` when they are cleared.
- `GemplasmEntryModal.vue` already sends `originId: formData.value.originId || null`, so clearing the origin now
  removes it. Nothing to change.

## Units as record group levels

A record group dimension can now take its levels from the unit graph: `RecordGroupDimensionInput.subjectIds` lists
subjects, and a record of a study without one of the dimension's groupings takes the nearest unit of one of them (its
unit or an ancestor) as its level, e.g. the plots of a field as blocks. `groupingIds` is now optional; a dimension needs
at least one grouping or subject. The rules are in `docs/analysis.md` §3 (record groups, units as levels). Nothing
breaks: existing dimensions are unchanged.

- Config: `AnalysisRecordGroupDimension.subjectIds` (non-null, `[]` when none); `groupings` is `[]` for a dimension of
  subjects alone.
- Results: a unit level is keyed `unit|<unitId>`. Its `AnalysisRecordGroupAssignment` has `unitId` (the plot) and
  `shared: false`, with `groupingId`, `code` and `scopeDatasetIds` null.
- Errors: an unknown subject fails the analysis with `CONFIG_INVALID` at `grouping.recordGroups.i.subjectIds.j`; a
  subject in two dimensions is refused on submit.

In breedview:
- `RecordGroupDimensionEditor.vue`: add a subject picker beside the groupings. Mark the studies whose records will use
  units (those of the selected datasets with none of the dimension's groupings), and refuse a subject already used by
  another dimension, as for groupings.
- `useAnalysisForm.js`: send `subjectIds` in `groupingInput`, and read them back in `groupingFromOutput`
  (`subjectIds: d.subjectIds ?? []`). Add `subjectIds` to the dimension fields of
  `analysisFragments.graphql`. `GroupingSection.vue` starts a new dimension with `subjectIds: []`.
- `useAnalysisNames.js`: `recordGroupAssignmentLabel` gives `groupingName(null): null of <unit>` for a unit level.
  Return `unitName(a.unitId)` when `groupingId` is null and the level isn't shared, and have `keyLabel` read
  `unit|<id>` as that unit's name. `collectIds` already collects the `unitId`.
- `useTermRules.js`: `isWithinUnitDimension` needs no change (subjects are never WITHIN_UNIT).
