# Front-end changes: people, access control and registration

This lists the API changes made with the Person, control transfer and invitation work (branches `control_transfer`, `person_implementations` and `invitations`),
and later account deletion and Person institutions, and what the front end needs to do about each.
Field names are given as in GraphQL (camelCase). Design background is in `person.md` and `control-transfer.md`.

Checked against the front end (`breedview` master at `876ad5b`, 2026-10-17) and the API on master (`1a5a492`): every
operation in the front end validates against the current schema (§10).

## 0. Where the front end is

**The front end is current (2026-10-17).** breedview's master (`876ad5b`) implements §1–§16:
- §1–§10 (Persons, invitations, legal entities, claims, ORCID, transfers, account deletion), by 2026-10-14;
- §11–§15 (record group extent, replicate aggregation and factors in analysis, the WITHIN_GRAPH extent, the area
  renames, contributions with roles, Role entries, sources and locked entries, and times as periods), on 2026-10-17;
- §16 (what a team controls, and scopes for bulk control), built with the API on 2026-10-17;
- §18 (Person views, data controllers, no public directory of people or teams), built with the API on 2026-10-17;
- §19 (one data controller, no Persons for signed-out visitors, place search and map tiles from our server), built
  with the API on 2026-10-19.

`python scripts/check_front_end_queries.py ../breedview/src` reports no operation with errors, and breedview's e2e
suite (`tests/e2e`, on the synthetic test database) passes.

**For the next API change:** add a section for it, with what breaks and the work it needs; then, in breedview,
regenerate the schema files with the API running (`node scripts/fetchGraphqlSchema.js` writes `schema.graphql`,
`possibleTypes.json` and `unionTypes.json`) and run the check script here.

## 1. Breaking changes at a glance

| Area | Change | Action |
|---|---|---|
| Registration | `accountsAddEmail`, `accountsRemoveEmail` and `Account.allowedEmails` are removed | Replace with invitations (§2) |
| Registration | After the first account, `accountsCreateAccount` requires `invitationToken`, and the email must be the invited address | Read the token from the invitation link (§2) |
| Person | `Person.fullname` is removed; `Person.name` can be null | Handle restricted and erased Persons (§4) |
| Person | `PersonInput` and `PersonUpdate` change; `peopleDeletePerson` is replaced by `peopleErasePerson` | Update the forms (§4) |
| Person | `peopleCreatePerson` needs the control team's team tree to have a declared legal entity, and `informedAttestation: true` | §3, §4 |
| Ontology | `authors` / `authorIds` are removed from every entry type and input | Remove from forms and views |
| Ontology | `Title` entries are removed: the `TITLE` label, the `Title` type, `Term.titles`, and `titleIds` in inputs. `Role` returns as the roles of contributions (§14) | Remove titles from forms and views |
| Contributions | `Dataset.contributors` becomes `contributions`, and `contributorIds` in dataset inputs becomes `contributions` (§14) | Update the dataset views and forms |
| Germplasm | `GermplasmEntry.authors` and `authorIds` in inputs are removed | Cite authors through references |
| Programs | `contactIds` must name Persons linked to an account and released widely enough | Show the errors (§5) |
| Teams | `teamsDeleteTeam` is refused while the team controls anything | Explain and link to transfers (§7) |
| Programs | `GroupingInput` requires `extent` | Add it to the grouping form (§11.2) |
| Units, locations, layouts, teams | The `blocks`, `regions`, `arrangements` and `organisations` areas are renamed `units`, `locations`, `layouts` and `teams`; `Location.region` and `Layout.arrangement` become `root`, `DatasetSummary.blocks` becomes `unitRoots` | Rename the operations and the response keys (§13) |

Nothing else was renamed. Everything below that is not listed here is new.
Every section uses the new names; §13 maps them from the old ones, which breedview still uses.

## 2. Registration and invitations

Allowed emails are replaced by invitations, which hold the invited address only until they are accepted, cancelled or expire.

**Inviting** (signed-in users):
- `accountsInvite(email, teams: [TeamInvitationInput!], personId)`.
  - `teams`: affiliations to offer, `{ teamId, access }`, for teams the user administers.
  - `personId`: a Person controlled by a team the user administers, for the invited user to link to their account.
  - Inviting the same address twice is refused while the first invitation is pending; offer *resend* instead.
- `Account.invitations` lists the user's pending invitations: `id, email, teams { team, access }, person, createdAt, expiresAt`.
- `accountsResendInvitation(id)` sends a new link and extends the expiry. `accountsCancelInvitation(id)` deletes the invitation.
- Invitations expire after 30 days by default.

**The invitation email** links to `/register?token=<token>`. The registration page must read `token` from the URL.

**Registration page:**
1. Call `accountsInvitation(token)` (no login needed). It returns `email`, `invitedBy` (full name), `teams { teamId, teamName, access }`, `offersPerson` and `expiresAt`.
   An error means the invitation is invalid, expired, or already used.
2. Prefill the email, read only: registration requires the invited address.
3. Show each offered team with a choice to accept; none is accepted unless chosen.
4. If `offersPerson`, ask whether to link the Person, with the notice in §6.
5. Call `accountsCreateAccount(name, email, password, fullname, invitationToken, acceptTeamIds, linkPerson)`.
   `fullname` is optional and defaults to the name (this used to fail when omitted).

The first account on a new deployment still registers without an invitation.

## 3. Team trees: legal entity

**Removed on 2026-10-19 (§19).** Kept for the history of the API.

The root team of a team tree (the teams under one root, from `teamsRoots`) may declare the legal entity responsible
for it, e.g. a university, which is the data controller for the tree's Persons. Only team trees with a declared legal
entity can record Persons; others only model collaboration. Show the legal entity on the root team
("Legal entity: University of Galway") rather than labelling the tree as an organisation: an organisation need not be
a legal entity, and a department's team tree may declare its university.

- `Team.legalEntity` (root teams only): `legalName, privacyContact, termsVersion, declaredAt, declaredBy`.
  `declaredBy` is only resolved for admins of the team.
- `teamsDataProcessingTerms` (no login needed) returns `version` and `url` of the current data processing terms.
  When `version` is null, no terms are configured and declaring is not possible; hide the option.
- Declaring, by admins of the root team only:
  - when creating a root team: `TeamInput.legalEntity { legalName, privacyContact, termsVersion }`, with no `parentId`;
  - later: `teamsDeclareLegalEntity(teamId, legalEntity)`.
  Show the terms (link to `url`) and require the user to accept them; send the `version` shown as `termsVersion`.
  Declaring again replaces the current declaration, accepting the current terms again.
- `privacyContact` should be a role address, such as `dataprotection@…`, not a person's own.
- `teamsWithdrawLegalEntity(teamId)` withdraws the declaration, by root admins. It is refused while the team tree controls any Person, including erased ones: they must be transferred first.

## 4. Persons

A Person is someone credited for research, with or without an account. It holds only a display name, an optional institution, teams, lawful basis and, once linked, an ORCID iD.
Show the institution with the name where a Person is credited, e.g. "Name (Institution)".

**Type `Person`:** `id, name, institution, teams, basis, informedAttestation, orcid, linkedUser, recordedBy, recordedAt, erased, erasedAt, restricted`.

A Person appears in one of three forms:

| Form | How to tell | Show |
|---|---|---|
| Full | `restricted` false, `erased` false | The record |
| Restricted | `restricted` true | "Restricted person" and the id only. The id can be used with `controlsControllers` to show who controls it |
| Erased | `erased` true | "Erased person". Contributions stay attributed to it |

Anonymous users get nothing; Persons they cannot see are omitted from lists.

**Queries:**
- `people(name)`: Persons the user can read, optionally by exact name (case insensitive).
- `peoplePeople(ids)`, `peoplePerson(id)`: by id; restricted where the user cannot read the record.

**Creating:** `peopleCreatePerson(person: PersonInput!, controlTeamId, release)` with `PersonInput { name, institution, teamIds, basis, informedAttestation }`.
- `informedAttestation` must be true: ask the user to confirm the person has been informed that the record is held.
- `basis` is `PUBLIC_TASK` (default) or `LEGITIMATE_INTEREST`.
- Refused unless the control team's team tree has a declared legal entity (§3).

**Updating:** `peopleUpdatePerson(person: PersonUpdate!)` with `PersonUpdate { id, name, institution, teamIds, basis }`. An empty `institution` removes it.
The linked user can change the name and institution only; other changes need curate access.

**Erasing:** `peopleErasePerson(id)`, by admins of the controlling teams or the linked user.
It cannot be undone: identifying data is removed and the id kept. Ask for confirmation.
An erasure also survives restoring a backup, and its id is never given to a new Person afterwards
(`docs/person.md` §5). Nothing in the API changes for this, so the front end needs no work for it.

## 5. Contacts and messaging

`Program.contacts` and `Trial.contacts` resolve to Persons (they previously returned ids under a Person type), restricted for users who cannot read them.

**Setting contacts** (`contactIds` on Program and Trial inputs): each contact must be a Person linked to an account, and released at least as widely as the Program or Trial, and at least to registered users. Errors explain which rule failed. Offering only Persons that are linked and released widely enough avoids them.

**Messaging:** `peopleContactPerson(personId, entityLabel, entityId, subject, message)`, where `entityLabel` is `PROGRAM` or `TRIAL` and the Person is one of its contacts.
- BreedGraph emails the contact; their address is never shown.
- **Tell the sender before sending that their name and email address are included, so the contact can reply.**
- Limits: 10 messages per hour per sender, subject 200 and message 5000 characters (configurable). Show the errors returned.
- Offer this as "Contact" next to each contact the user can see.

**Removing yourself as a contact:** `peopleRemoveSelfAsContact(entityLabel, entityId)`, for the user linked to the contact.

## 6. Linking a Person to an account

Before a user links a Person to their account, by accepting an invitation or requesting a claim, tell them:
- Other users may message them through BreedGraph if the Person is listed as a contact on a Program or Trial. Messages arrive at their account email address, which senders never see.
- They can remove themselves as a contact, and unlink or erase the Person, at any time.

Show this in the confirmation step, not only in the privacy notice. The same text is in the descriptions of `linkPerson` and `peopleRequestClaim`.

**Through an invitation:** `linkPerson: true` on registration (§2).

**By request:**
- `peopleRequestClaim(personId)`: the user asks to be linked. Works for Persons they can only see restricted.
- `peopleMyClaims`: the user's pending requests (`person, requestedAt`); `peopleWithdrawClaim(personId)`.
- For admins of the controlling teams: `peopleClaimRequests` lists pending requests (`person, userId, name, fullname, requestedAt`), decided by `peopleApproveClaim(personId, userId)` or `peopleRejectClaim(personId, userId)`. Prompt the admin to confirm the user's identity before approving.
- Each account can be linked to one Person, and each Person to one account.

**Once linked:**
- `peopleMyPerson` returns the user's Person in full, for a "my profile" page: edit name, link ORCID, erase, unlink.
- `peopleUnlinkPerson(personId)`, by the linked user or admins of the controlling teams.
- Admins and linked users receive emails for requests and links; no front-end action is needed.

**ORCID iD** (linked users only):
1. A "Connect your ORCID iD" button, following ORCID's brand guidelines, calls `peopleStartOrcidLink` and sends the browser to the URL it returns.
2. ORCID redirects to the front-end page `/orcid` (the configured `ORCID_REDIRECT_URI`) with `code` and `state` in the query string, or `error` if the user cancelled.
3. That page calls `peopleCompleteOrcidLink(code, state)`, then returns to the profile.
- Show the iD as its full `https://orcid.org/…` address. `peopleRemoveOrcid` removes it.
- When ORCID is not configured on the server, `peopleStartOrcidLink` returns an error; hide the button if it does.

## 7. Control transfers and teams

Control of a controlled entity (Program, Trial, Study, Dataset, Germplasm, Location, Layout, Unit, Reference, Person) can move between teams by offer and acceptance. Each entity is transferred on its own, not with others in its aggregate; to move a Program with its Trials, list them all.

**Queries:** `controlsTransfers(statuses)` (offers to or from teams the user administers) and `controlsTransfer(id)`.
`ControlTransfer`: `id, status, entities { label, id }, fromTeams, keepFromTeams, recipientTeam, toTeams, release, offeredBy/At, acceptedBy/At, rejectedBy/At, cancelledBy/At`.
The `…By` users are often null, as user details are only shown to admins who can see them; show the team instead.

**Mutations:**
- `controlsOfferTransfer(offer: { entities, fromTeamIds, recipientTeamId, keepFromTeams, toTeamIds, release })`.
  The user must administer every team in `fromTeamIds`. `recipientTeamId` is often the root team of another team tree.
  `keepFromTeams: true` shares control instead of handing it over.
  If the user also administers the recipient team, giving `toTeamIds` (and `release`) accepts at once.
- `controlsAcceptTransfer(id, toTeamIds, release)`: by admins of the recipient team. `toTeamIds` are the recipient team or teams below it that the user administers; `release` defaults to `PRIVATE`.
- `controlsRejectTransfer(id)` (recipient side), `controlsCancelTransfer(id)` (offering side).
- `controlsRenounceControl(entities, teamIds)`: give up control where other teams also control the entities.

Persons can only be transferred to a team tree with a declared legal entity (§3), and shared only within one team tree.
Admins of the recipient team are emailed about new offers.

**Teams:**
- `teamsDeleteTeam` is refused while the team controls anything: transfer or renounce its control first.
- Deleting a team cancels pending transfers to or from it. Deleted teams no longer appear anywhere.
- Offers may become impossible to accept if the offering team loses control in the meantime; accepting then returns an error.

## 8. Other changes

- `accountsDeleteAccount(password, erasePerson)` deletes the user's own account and logs them out. Ask for the password, and ask whether to erase their linked Person as well, ticked by default.
  Errors explain when it is refused: the only ontology admin, or the only admin of a team (the message lists the teams).
  Deleted users show as null wherever a user is shown, like users the viewer can't see.
  The deletion takes effect at once: the user's login no longer works, and their username is free to register again. It stays deleted if a backup is restored,
  and its id is never given to a new account afterwards, so an id cached by the front end never comes to mean another user (`docs/person.md` §5).
  Nothing in the API changes for this.

- Dataset, Program and Trial `contributions` resolve their Persons, restricted where needed (§14).
- Password reset with a token works again (it always failed before).
- Fields that work without login: the account flows (register, log in, verify email, password reset), `accountsInvitation` and `teamsDataProcessingTerms`. Everything else still requires login.

- Record groupings have an `extent` (record group types an optional `defaultExtent`), and analysis terms have a `replicateAggregation` (§11).

## 9. Migrated BreedCAFS data

The BreedCAFS migration (`src/breedcafs_migration/`) loads data the front end has not shown at this scale. Nothing in the API changes for it, but expect:
- **Size.** 41 fields with up to about 3,300 units each (field → trees → cherries and samples), 1,176 datasets of up to about 6,900 records,
  35,665 units and 213,761 records in all, besides the curves. Unit graph (the blocks page), dataset and analysis views should page or virtualise rather than load a whole field.
- **Blocks, branches and leaves as record groups.** None is a unit. A branch's or leaf's records are on its tree, with the
  branch or leaf as a code in the study's Branch or Leaf grouping (`WITHIN_UNIT`), and a branch's canopy stratum in the
  Stratum grouping (`SHARED`). Records of what is in a BreedCAFS block carry its name in the Block grouping (`WITHIN_GRAPH`, §12),
  and the trees and samples hang from the field. Record and analysis views should show record group codes beside the unit,
  or a tree's branches look like repeated readings.
- **Persons as contributors.** Persons credited for datasets have an institution and are `PRIVATE` until handover, so most users see them restricted (§4).
  Submitters are credited with the Data curation role; the people who recorded the data have no roles (§14).
- **Curves.** The four fluorescence curve datasets (Fluorescence ~ Time, PocketPEA) have records with no value: each references its dataset's CSV data file,
  whose schema gives the index columns (`item_uid, unit_id, time, replicate`) that find a record's row. The existing complex-scale cells show the reference count.
- **Times as entered.** Record times are to the minute where a time of day was entered, and to the day otherwise. `DateTime` values keep their precision,
  e.g. `2018-11-25` or `2018-11-25T10:30`; show them as given rather than parsing a date alone into midnight in the browser's time zone. They are local times, without a time zone (§15).
- **Layouts.** Fields have "Row and Tree" layouts with ordinal Row and Tree axes, some per block, and Field 5 has a second layout for a later planting.
- **Studies** may start before their program (Nicaragua, 2015).
- Branch stratum and the shade treatments are factor records (Stratum, Shade Treatment, Shade Level Treatment), not unit properties.

## 10. Checking the front end against the API

```bash
set -a; . instance/breedgraph.env; . instance/private.breedgraph.env; set +a
.venv/bin/python scripts/check_front_end_queries.py ../breedview/src
```

It builds the API's schema and validates every operation in the front end's `.graphql` files, with the fragments each uses, and exits with 1 if any fails.
It does not check variables, so input fields built in JavaScript (as `roleIds` was) need a search.
Rerun it after changing the front end, and after any API change, before releasing either.

## 11. Record group extent and replicate aggregation

Record groupings now say how analysis groups records with the same code across units, and analyses can combine replicates before
aggregating. The extent is set on each grouping of a study, beside its scope; a record group type only suggests one. Background and rules: `docs/analysis.md` §2 (replicates) and §3 (record groups). Paths below are in `breedview/src`.

**The concepts, for help text:**
- A code can mean the same on every unit, e.g. a canopy stratum "Lower". The extent decides whether analysis uses that.
- **`SHARED`**: records of different units with the same code are one group, e.g. Block 2, Batch 3 or the Lower stratum,
  a level that can be estimated across units.
- **`WITHIN_UNIT`**: codes are nested in each record's unit. Records of one unit with the same code at one time, or within
  the replicate aggregation window, are one reading, e.g. replicate numbers or the branches of a tree.
  Replicate 1 of one tree is not grouped with replicate 1 of another.
- Something followed over time, sampled or positioned is better recorded as a child unit than as a code.
- Scope (study-wide or dataset-scoped) is unchanged and independent of extent. It still sets which datasets' codes can be compared.
- Both are set per grouping, so one type (e.g. "Block") can be used with different extents in different studies.

### 11.1 Ontology: record group types

`RecordGroupType.defaultExtent: RecordGroupExtent` (`SHARED` | `WITHIN_UNIT` | `WITHIN_GRAPH`, §12) is **optional** in
`RecordGroupTypeInput` and `RecordGroupTypeUpdate`. It only prefills the extent of a new grouping of the type (§11.2);
changing it doesn't change existing groupings. Omitting it on update leaves it unchanged.

- `composables/ontology/ontologyEntryConfig.js`, `RecordGroupType`:
  - add an optional single-choice `defaultExtent` field, with the descriptions above as help text and a "none" choice;
  - send it in `processCreate` and `processUpdate`, prefilled from the entry on update.
- `graphql/ontology/createRecordGroupType.graphql` and `updateRecordGroupType.graphql` take it through the input variable,
  so they don't change. The entry queries need `... on RecordGroupType { defaultExtent }` where the form is prefilled.
- `RecordGroupType.parents` and `children` are now typed `RecordGroupType` (they were `Design`). Regenerate the schema
  files (§0) and check any fragment that selected Design fields on them.

### 11.2 Study groupings

`RecordGrouping.extent: RecordGroupExtent!` is **required** in `GroupingInput`. Until the form sends it, creating a
grouping fails. In `GroupingUpdate` it is optional: omitted, it is unchanged.

- `components/programs/RecordGroupingForm.vue`:
  - add a required single-choice `extent` field beside the scope, with the descriptions above as help text;
  - when a type is picked, prefill it from the type's `defaultExtent` (if it has one, and the user hasn't chosen yet);
  - send it in `programsCreateGrouping` and `programsUpdateGrouping`, prefilled from the grouping on update.
- Changing the extent of a grouping with records changes how analysis groups their codes, not the records: say so
  next to the field when editing.
- `graphql/programs/study.graphql`: select `extent` on `groupings` (and the type's `defaultExtent` for the prefill).
  The curation table and the grouping list get it from there.
- `RecordGroupingList.vue`: show each grouping's extent, so it's clear which groupings hold replicates.
- `programsDeleteGrouping` is refused while any record has a code of the grouping (the error says to remove the codes
  first). It used to report success and keep the grouping. Codes no record has any more go with the grouping.

### 11.3 Dataset curation

`composables/datasets/useDatasetCurationTable.js` splits rows into sections by the codes of every DATASET_SCOPED grouping
(`datasetScopedColumns`, `rowSections`). For a WITHIN_UNIT grouping this puts replicate 1 of every unit in one section,
which is the grouping that prompted this change.
- Carry the extent onto each grouping column in `buildGroupingColumns`.
- Build sections only from SHARED groupings (`c.scope === 'DATASET_SCOPED' && c.extent === 'SHARED'`).
- WITHIN_UNIT codes stay as an ordinary column. Rows are already one per (unit, start, end, codes), so a unit's replicates
  appear as adjacent rows. Sort so that they stay together: unit, then time, then code.
- Records referencing groupings not returned for the loaded studies (the read-only fallback columns) have no extent:
  treat them as SHARED, as now.

### 11.4 Analysis: terms

The term input has a new object, for concept terms only:

```graphql
replicateAggregation: { aggregation: MEAN, window: "PT5M" }   # ReplicateAggregationInput; window optional
```

- **`aggregation`**: MEAN, MEDIAN, MIN, MAX or MODE. NONE, SUM and COUNT are refused. MEAN and MEDIAN need a numerical
  scale; MIN and MAX need ordered values, as for `aggregation`.
- **`window`**: an ISO 8601 duration, longer than zero (`PT5M`, `PT1H`, `P1D`). Free text such as "5 minutes" is refused.
  - Without it, a reading is the replicates with exactly the same start and end.
  - With it, a reading starts at its first record and takes in records up to the window later. The next record outside
    the window starts a new reading, so a run of readings 4 minutes apart doesn't chain into one with a 5-minute window.
  - Time bins (`grouping.time`) still split readings.
- The term's `aggregation` then combines the readings, e.g. units under a parent unit, or dates in a time bin.
  Without `aggregation` (NONE), each observation must have one reading.
- `replicateAggregation` can't be combined with a COUNT `aggregation`.

Changes:
- `components/analysis/config/TermEditor.vue`: a "Replicates" block under Aggregation, shown for concept terms:
  - an aggregation select (MEAN, MEDIAN, MIN, MAX, MODE, filtered by scale like `allowedAggregations`, plus "none" to
    leave `replicateAggregation` null);
  - a window input, shown when an aggregation is chosen. Offer presets (exact time, 5 min, 1 hour, 1 day) and a custom
    number and unit, sent as an ISO duration, e.g. `PT${n}M`, `PT${n}H`, `P${n}D`;
  - `FieldErrors` at `${path}.replicateAggregation` and `${path}.replicateAggregation.aggregation`.
  - Help: "Combines the replicate readings of each unit (codes of WITHIN_UNIT groupings) into one value before the
    aggregation, so units and dates count once however many replicates they have."
  - Show it whenever the selected datasets' studies have a WITHIN_UNIT grouping; otherwise hide it, or collapse it,
    as it has no effect.
- `composables/analysis/useTermRules.js`: `REPLICATE_AGGREGATIONS = ['MEAN', 'MEDIAN', 'MIN', 'MAX', 'MODE']`, filtered
  by scale. When `aggregation` is COUNT, disable or clear `replicateAggregation`.
- `composables/analysis/useAnalysisForm.js`: carry `replicateAggregation` through form state, submission and load-back.
  Send `null`, not `{}`, when unset.
- The term summary line in `TermEditor.vue` (~l.144): e.g. "mean of replicates within 5 min, then mean".
- `graphql/analysis/analysisFragments.graphql`, `AnalysisTermFields`: add `replicateAggregation { aggregation window }`
  so stored configurations load back into the form.

### 11.5 Analysis: record group dimensions

A record group dimension over WITHIN_UNIT groupings keeps each replicate as its own observation. That suits
descriptive statistics, outlier detection, correlation and MDS on individual readings. The server refuses, with
`CONFIG_INVALID`:
- such a dimension used as a term (path at the term's `reference`);
- such a dimension in ANOVA (path at `grouping.recordGroups.<i>`);
- WITHIN_UNIT codes as members of shared `levels` (path at the member).

Front end:
- `components/analysis/config/RecordGroupDimensionEditor.vue`: show each grouping's extent.
  - When a WITHIN_UNIT grouping is selected, hide the shared-levels editor for its codes.
  - Say that each replicate becomes an observation, and point to the term's replicate aggregation as the alternative.
- `components/analysis/config/TermsSection.vue`: don't offer a WITHIN_UNIT dimension as a RECORD_GROUP term.
- For ANOVA, warn when a WITHIN_UNIT dimension is configured, before submission.
- Results: `AnalysisRecordGroupAssignment.unitId` is set for WITHIN_UNIT levels, whose `level` key is
  `grouping|scope|unit|code`. Show the code with its unit (e.g. "Replicate 2 of Tree 15") from `code` and `unitId`;
  don't parse `level`.

### 11.6 Messages

`composables/analysis/useAnalysisMessages.js`:
- `DUPLICATE_OBSERVATION` with a path ending `replicateAggregation`: the duplicates are only replicates. Hint:
  "These values are replicates of the same reading. Set a replicate aggregation on the term, or add a record group
  dimension to analyse each replicate." Link to the term's replicate block, and keep offering to exclude `recordIds`.
  With a path ending `aggregation`, keep the current hint.
- New warning `REPLICATES_POOLED`, with a path at the term's `replicateAggregation`: "Replicates were pooled by the
  term's aggregation, so units and dates with more replicates weigh more. Set a replicate aggregation to combine
  each reading first." It is given for MEAN, MEDIAN, SUM and MODE, not for MIN, MAX or COUNT, whose results don't depend
  on it.

### 11.7 Factors in analysis

When an analysis has a variable term, factor records now describe the observations rather than forming them:
undated factor records apply to every time bin, factors on a parent unit apply to its descendants (the nearest
applies), and a factor without a code applies to every record-group level (`docs/analysis.md` §2). Nothing in the
schema changes. Help text in the term editor can say so: "Factors apply to the units they were recorded on and
their descendants, and, without a date, to every time bin."

### 11.8 Checks

- Regenerate the schema files and run `scripts/check_front_end_queries.py` (§10).
- Against the test database's replicates study (docs/test-databases.md, "The replicates study"; its manifest entry
  `replicates` gives the ids and the expected outcomes):
  - (a) create a grouping with each extent, of a type with a default extent and of one without;
  - (b) curate `same_time` and `width`: sections by Dataset Scoped Plate, none by replicate code;
  - (c) submit a descriptive analysis of `same_time`, without and then with `replicateAggregation`. Without, it fails
    with `DUPLICATE_OBSERVATION` at `replicateAggregation`; with, it completes. `dated`, `windowed` and the plot means
    check windows and pooling (`expected.cases`, `expected.windowed_readings_per_tree`, `expected.plot_means`).

## 12. The WITHIN_GRAPH extent

`RecordGroupExtent` has a third value, `WITHIN_GRAPH`. Its codes are shared like SHARED codes, but only by the units of
one unit graph (e.g. a field), so the design blocks of different fields, which reuse the same names
("Block 1"), stay apart without the code having to name the field. Background: `docs/analysis.md` §3 and the README's
"Record Group Type", which also gives the rule for choosing between a unit, a code and a factor. The BreedCAFS migration
uses it for the blocks of its fields.

**Help text** (with §11's concepts):
- **`WITHIN_GRAPH`**: records of units of one unit graph with the same code are one group, e.g. the design blocks of a field.
  Block 1 of one field is not grouped with Block 1 of another.

Front end:
- §11.1, §11.2: the extent fields offer the third value, with this help text; badges and lists show it.
- §11.3: curation sections may be built from WITHIN_GRAPH groupings as from SHARED ones (`c.extent !== 'WITHIN_UNIT'`).
- §11.5: a WITHIN_GRAPH dimension can be a term and be used in ANOVA, and its codes can be members of shared levels
  (a member merges the code across unit graphs). `AnalysisRecordGroupAssignment.unitId` is the unit graph's root for WITHIN_GRAPH
  levels (`level` key `grouping|scope|root|code`): show the code with its root, e.g. "Block 1 of ED1". The root may be a
  placeholder the user can't read; show its id only.

## 13. Units, locations, layouts and teams: renamed areas

The aggregates were renamed for the shape of what they hold: `Block` is now `UnitGraph` (a rooted graph of units, which
also stops it being confused with a design block, now a WITHIN_GRAPH code, §12), `Region` is `LocationTree`,
`Arrangement` is `LayoutTree` and `Organisation` is `TeamTree`. The GraphQL areas take the plural of the member type, as
`people` already does: `units`, `locations`, `layouts` and `teams`. The pages can keep showing whatever names suit users
("Regions", "Organisations"); only the operations change. Arguments, payloads and types are unchanged, except for the three
fields at the end of the table.

| Old | New |
|---|---|
| `blocks(locationIds)` | `unitsRoots(locationIds)` |
| `blocksUnits(ids)` | `unitsUnits(ids)` |
| `blocksDescendantsBySubject(unitIds)` | `unitsDescendantsBySubject(unitIds)` |
| `blocksCreateUnit`, `blocksUpdateUnit`, `blocksDeleteUnit` | `unitsCreateUnit`, `unitsUpdateUnit`, `unitsDeleteUnit` |
| `blocksAddPosition`, `blocksRemovePosition` | `unitsAddPosition`, `unitsRemovePosition` |
| `regions` | `locationsRoots` |
| `regionsLocations(ids)` | `locationsLocations(ids)` |
| `regionsLocationsByType(locationTypeId)` | `locationsLocationsByType(locationTypeId)` |
| `regionsDescendantsByType(locationIds)` | `locationsDescendantsByType(locationIds)` |
| `regionsCountries` | `locationsCountries` |
| `regionsCreateLocation`, `regionsUpdateLocation`, `regionsDeleteLocation` | `locationsCreateLocation`, `locationsUpdateLocation`, `locationsDeleteLocation` |
| `arrangements(locationId)` | `layoutsRoots(locationId)` |
| `arrangementsLayouts(ids)` | `layoutsLayouts(ids)` |
| `arrangementsCreateLayout`, `arrangementsUpdateLayout`, `arrangementsDeleteLayout` | `layoutsCreateLayout`, `layoutsUpdateLayout`, `layoutsDeleteLayout` |
| `organisations` | `teamsRoots` |
| `organisationsTeam(id)`, `organisationsTeams(ids)` | `teamsTeam(id)`, `teamsTeams(ids)` |
| `organisationsDataProcessingTerms` | `teamsDataProcessingTerms` (still open without login) |
| `organisationsCreateTeam`, `organisationsUpdateTeam`, `organisationsDeleteTeam` | `teamsCreateTeam`, `teamsUpdateTeam`, `teamsDeleteTeam` |
| `organisationsDeclareLegalEntity`, `organisationsWithdrawLegalEntity` | `teamsDeclareLegalEntity`, `teamsWithdrawLegalEntity` |
| `Location.region` (the root location) | `Location.root` |
| `Layout.arrangement` (the root layout) | `Layout.root` |
| `DatasetSummary.blocks` (the root units) | `DatasetSummary.unitRoots` |

Front end (`breedview` at `7636479`): `scripts/check_front_end_queries.py` (§10) finds 29 operations to rename, all in
`graphql/blocks/`, `graphql/regions/`, `graphql/arrangements/` and `graphql/organisations/`, plus
`graphql/datasets/datasetSummaries.graphql` (`blocks`) and `graphql/regions/locationFragment.graphql` (`region`).
The check does not see the response keys read in JavaScript: `result.data.regions`, `data.blocks`, `location.region`,
`layout.arrangement`, `summary.blocks` and the like, e.g. in `composables/regions/`, `composables/blocks/blocksQuery.js`,
`composables/analysis/useAnalysisDataContext.js`, `components/regions/`, `components/blocks/`,
`components/arrangements/ArrangementTree.vue`, `components/programs/DatasetScopeForm.vue` and
`components/datasets/StudyDatasetsPanel.vue`; search for them too. The Apollo `Query` field policy for `blocksUnits` (`graphql/apollo.js`) becomes `unitsUnits`.

**What each roots query returns** (unchanged, only renamed):
- `unitsRoots(locationIds)`: the root units of the unit graphs positioned at those locations that the user can read a
  unit in; a hidden root holding readable units is a placeholder (id, `REDACTED` name). Children load through
  `Unit.children` or `unitsUnits`.
- `locationsRoots`: the root location (a country) of every location tree the user can read a location in, not the
  whole trees; `Location.children` and `locationsLocations(ids)` give the rest. `Location.root` is the root of the
  location's tree (itself for a root).
- `layoutsRoots(locationId)`: the root layout of every layout tree at that location (the argument is required).
  `Layout.root` is the root of the layout's tree.
- `teamsRoots`: every team tree's root, with the teams the user is affiliated with below it; anonymous users see the
  roots only, with their legal entities.
- `DatasetSummary.unitRoots`: the roots of the unit graphs of a dataset's units, a placeholder when hidden.

**Access is unchanged**: the same fields work without login as before (`test_anonymous_queries.py` lists them), so the
anonymous pages for regions, arrangements and blocks keep working once renamed; `teamsDataProcessingTerms` is still open.

**Naming in the pages** is up to the front end. Routes, components and composables (`/regions`, `RegionsManagement`,
`BlockManagement`, `blocksQuery.js`, ...) need not change, but if they are renamed: the API's "unit graph" is not a
design block, which is now a `WITHIN_GRAPH` record group code (§12), so a page of unit graphs is better not called
"Blocks"; show the legal entity on a root team rather than calling the tree an organisation (§3).

**Order**: rename the operations, rerun `scripts/check_front_end_queries.py` until only real errors are left, then
search the JavaScript for the response keys. Regenerate `src/graphql/schema.graphql` first (§0), so tooling sees the
new fields.

## 14. Contributions, roles and locked ontology entries

Design background is in `contributions.md`.

**Contributions.** Datasets, Programs and Trials credit Persons with the roles they had:
- `Dataset.contributions`, `Program.contributions`, `Trial.contributions`, `FileReference.contributions`,
  `DataFileReference.contributions`, `ExternalDataReference.contributions` and submitted-data `contributions`
  are `[Contribution]`, where `Contribution { person: Person, roles: [Role!] }`. `Dataset.contributors` is removed.
- Inputs take `contributions: [ContributionInput!]`, where `ContributionInput { personId: ID!, roleIds: [ID!] }`:
  dataset create and update (in place of `contributorIds`), Program and Trial create and update, and the file, data file and
  external data reference create and update inputs. On update the list replaces all contributions.
  For a file or data file update with a new file, the update, contributions included, is applied once the file is saved.
- Roles are declared, not exhaustive: a contribution may have none, and roles can be added later. A Person is credited once per dataset, Program or Trial.
- Crediting a Person needs read access to them (others already credited stay), and each role must be a `Role` entry.
- Suggested display: "Name (Institution) — Investigation, Data curation". A role picker lists `Role` entries; the CRediT roles fit as below.

| Fits | Roles |
|---|---|
| Datasets | Investigation, Data curation, Methodology, Resources, Validation, Supervision |
| Programs and Trials | Conceptualization, Funding acquisition, Project administration, Supervision |
| File and data references | Formal analysis, Visualization, Writing – original draft, Writing – review & editing, Software, Data curation |

**Role entries.** `ROLE` is an ontology label again, with a `Role` type (in `OntologyEntryUnion`), `ontologyCreateRole`, `ontologyUpdateRole`,
and `Term.roles` / `roleIds` on terms. A Role describes what a Person did in a contribution, never the Person.
The 14 CRediT roles are seeded, locked, and can have children (e.g. "Sample collection" under Investigation).

**Sources.** Every ontology entry has `sourceUrl` and `sourceAttribution`, for entries taken from an external standard or ontology,
settable in every entry input and update. Show them with the entry: the CRediT roles' attribution is required by their CC BY 4.0 licence.

**Locked entries.** Every ontology entry has `locked: Boolean!`. Ontology admins lock and unlock entries with
`ontologyLockEntries(ids)` and `ontologyUnlockEntries(ids)`. A locked entry keeps its name, abbreviation, description and source,
and the relationships that define it (e.g. a scale's categories), and cannot be deprecated; synonyms, references, children and terms stay editable.
Disable those fields in the editing forms, and show a lock.

`referencesCreateExternalData` created each reference twice; it now creates one.

**References.** Citing a reference (in any input with `referenceIds`, or a study's or the ontology's licence) needs read access to it.
A reference's release cannot be lowered below the release of what cites it: `controlsSetRelease` returns an error saying so.

## 15. Times

**Observation times are local.** The times of records, studies, trials, positions and germplasm are the wall-clock time at the
location, at the precision entered (`2021`, `2021-05`, `2021-05-03`, `2021-05-03T10:30`). They carry no time zone, and an input
with `Z` or an offset (e.g. `2021-05-03T10:30+02:00`) is refused with an error; previously the offset was converted to UTC
and dropped. Send times as the user entered them, and never build them with `Date.toISOString()`, which adds `Z`.

**A time stands for its whole period.** As a start a time means the start of its period, as an end the end of it: a record
ending `2021-05-03` runs through that day, and one dated `2021` through the year.
- The `start` and `end` arguments of `records`, `recordCount`, `unitIds`, `datasetsUnits` and `datasetsUnitsBySubject` select
  records whose period overlaps the window, so `end: "2021"` includes all of 2021, and a record dated `2021` is found by a
  June 2021 window. A date picker for an end can send the day itself, not the next day.
- An end may now be given to a coarser precision than its start on the same day or month, e.g. start `2021-05-03T10:30`, end `2021-05-03`.
- `DatasetSummary.start` / `end` and the dataset dimensions' `start` / `end` are the first start and last end as entered, at their
  precision (they were cut to the day).
- Analysis time bins follow the same rule: `END` assigns a record by the last moment of the period of its end, and `MIDPOINT` by the
  middle of the record's period, so a record dated `2021` falls in July (`docs/analysis.md` §3). Both used the start of the period before.

**Timestamps carry an offset.** Times the server sets (`Control.time`, `WriteStamp.time`, `Controller.created` / `updated`,
`referencesFileDownload.expiresAt`, `submitted`, ...) are ISO 8601 with an offset, e.g. `2026-10-16T09:30:00+00:00`;
the control times had a space in place of the `T`. `FileRecovery.startedAt` is when retrieval was first requested, or null
while a file is archived and no retrieval has been requested (it was the time of the query).

## 16. What a team controls (bulk control)

Controls are an admin concern: setting a release and transfers both need ADMIN of a controlling team. These reads are
for teams the user is an admin of, and a request naming any other team is refused with an error saying so.

- `controlsControlledCounts(teamIds)`: `[ControlledCount { teamId, label, release, count }]`, how many entities of each
  label each team controls, by the release the team set.
- `controlsControlledEntities(teamId, label, release, offset, limit)`: `ControlledItems { total, items }`, the entities of
  a label a team controls, ordered by id, `limit` 50 by default. Each `ControlledItem` has `id`, `name` (a dataset's
  concept, a reference's file name or description; REDACTED where the user cannot read it), the team's `release`,
  `otherTeams` (TeamReferences, stand-ins for hidden teams) and `context`, the name of what holds it (a dataset's
  study, a study's trial, a trial's program, a location's parent, a layout's location).
- `controlsControlledUnits(teamId, parentIds)`: the units as a tree. Without `parentIds`, the roots of the unit graphs
  holding units the team controls; with them, the nearest units below each that the team controls or that hold units
  it controls, through hidden units (a hidden root is a placeholder, a hidden unit the team controls is shown named
  REDACTED). Each `ControlledUnit` has `unit` (id, name, subject and germplasm only), `parentId`, `release` (the team's,
  null where it controls only units below), `count` (the units it controls at and below) and `otherTeams`. For a
  field of 1,000 trees the children take about half a second.

**Scopes in place of id lists.** `ControlScopeInput { teamId, label, release, belowUnitIds }` stands for everything of
a label the team controls, at a release when given, and for units only those at and below `belowUnitIds`. It can
be given instead of the ids to `controlsSetRelease(scope, release)` (whose `entityLabel` and `entityIds` are now
optional), `controlsOfferTransfer(offer: { scope, ... })` (`entities` optional) and
`controlsRenounceControl(scope, teamIds)` (`entities` optional). Give one or the other: both, or neither, is refused.
The server resolves the scope, so the client never posts 100,000 ids; a release set on 5,000 units takes about 3 s.

## 17. Ancestors, and records of exactly some units

Additions, nothing breaks; breedview uses both for the factors describing the curation table's rows.
- `Unit.ancestors`: the units above a unit, closest first: those you can read, found through hidden units as `parents`
  are, and its unit graph's root, a placeholder when hidden. Empty for a unit you cannot read. It is read for every
  unit of the request at once, so `unitsUnits(ids) { ancestors { id positions { … } } }` costs one query for a page.
- `Dataset.records(includeBelow: false)`: `unitIds` then narrows to the records of exactly those units, rather than
  also everything below them, e.g. the factor records of a page's units and their ancestors.

## 18. Person views, data controllers, and no public directory

Design in `person.md` §2–§3 and `read-access.md` rules 2, 7 and 9.

**Breaking for signed-out visitors.**
- `people`, `peoplePeople`, `peoplePerson`, `teamsRoots`, `teamsTeam` and `teamsTeams` need an account: anonymous
  requests get the authentication error. Signed-out visitors meet Persons only nested in what they can read
  (`Program`/`Trial.contacts`, `contributions { person }` on programs, trials, datasets and references), and see no
  teams. The People page and anything else listing people or teams should be for signed-in users only.

**Three views of a Person** (`Person.view: PersonView!`):
- `FULL`, for read affiliates of a controlling team and the linked user: as before, plus `linked: Boolean`, whether
  an account is linked, which full viewers see even when `linkedUser` is hidden from them (rule 9). Use `linked`, not
  `linkedUser`, to say whether a Person has an account, and to offer contacts (which must be linked).
- `ATTRIBUTION`, for those reading it by release only, signed-in users without a read affiliation included: `name`,
  `institution`, `orcid` and `erased`. `teams` is empty and `basis`, `informedAttestation`, `recordedBy`,
  `recordedAt`, `erasedAt`, `linked` and `linkedUser` are null. A person picker should accept these, and tell people
  apart by institution where teams are missing.
- `RESTRICTED`: the id only, as before (`restricted` stays, true for this view). `basis`, `informedAttestation` and
  `erasedAt` are now null here too, and `erased` is false: an erased Person shows as erased only to those who could
  see it.

**Who holds a record** (removed in §19). `Person.dataController: DataController { legalName, privacyContact }`, in every view, restricted
ones included: the legal entity declared on the root of the team tree controlling the Person, null when it can't be
told. Show it with Persons, for signed-out visitors too, e.g. "Record held by <legal name>" with the privacy contact.
`LegalEntity` on teams is unchanged (signed-in users only, `declaredBy` for root admins).

**Affiliations.** Read access can no longer be removed or revoked while curate or admin access is authorised on the same
team: remove those first. Removing curate access now leaves read access in place (revoking read used to revoke curate
too). The mutations return an error saying which access to remove first.

**Transfers.** An offer must go to a team the offering user can see (a team tree root, or one of their own teams);
others are refused as not found. A transfer of a Person is refused when teams of its old team tree would keep
control alongside the recipient's. `controlsSetRelease` is refused for an entity without current controls.

## 19. One data controller, no Persons signed out, maps from our server

Design in `person.md` §2–§3, `read-access.md` rule 2 and `legal/privacy-notice.md`. The University is the data
controller of all personal data in BreedGraph, so organisations no longer declare legal entities, and browsers contact
no third party.

**Removed.**
- Legal entity declarations (§3): `Team.legalEntity`, `LegalEntity`, `LegalEntityInput`, `TeamInput.legalEntity`,
  `teamsDeclareLegalEntity`, `teamsWithdrawLegalEntity`, `teamsDataProcessingTerms` and `DataProcessingTerms`.
  Any team can record Persons.
- `Person.dataController` and `DataController` (§18): every Person is held by the University, named in the privacy
  notice.
- `Person.basis`, `PersonInput.basis`, `PersonUpdate.basis` and the `LawfulBasis` enum: the basis is the same for every
  Person, and stated in the privacy notice.
- The rule that a Person's controlling teams stay within one team tree: transfers of Persons go to any team.

**Persons are for signed-in users.**
- A Person's release is at most `REGISTERED`. `peopleCreatePerson`, `controlsSetRelease` (by ids or by scope) and
  `controlsAcceptTransfer` refuse `PUBLIC` for Persons ("People can be released at most to registered users"). Offer
  no public release for Persons, including in bulk control and transfers that hold Persons.
- Anonymous requests get empty `contacts` and `contributions` on programs, trials, datasets and references. Hide those
  sections when signed out.
- A contact must be released to registered users, whatever the release of its program or trial.

**Location search** (`locationsSearch(name, limit)`): the locations the viewer can read whose name contains `name`,
ignoring case, those starting with it first, at most `limit` (10, up to 50). Open to anonymous users, like the other
location reads; hidden locations are left out. List them in the map's search box above the places.

**Place search** (`locationsSearchPlaces(query, viewbox, bounded, countryCode, limit)` and
`locationsGeocodeCountry(name)`, returning `Place { name latitude longitude bounds }`): the server asks Nominatim, so
the browser doesn't. They need an account and are limited per user per hour (`GEOCODING_RATE_LIMIT_PER_HOUR`, 120).
`viewbox` is `[west, south, east, north]`; `bounds` is `[[south, west], [north, east]]`, or null.

**Map tiles** are served at `/tiles` from `MAP_TILES_PATH` (nginx serves them in production), all PMTiles from
Protomaps' OpenStreetMap builds, read in byte ranges (e.g. by protomaps-leaflet). `/tiles/tiles.json` lists them:
`{attribution, updated, layers}`. Until the world file is cut there is none (404).
- The first layer is the low-detail world file, `{url, maxZoom, build}`, cut by `scripts/map_tiles.py`.
- The others are regions in full detail, `{url, name, minZoom, maxZoom, bounds}` with `bounds` as
  `[[south, west], [north, east]]`: whole countries, or sections (states or provinces) of countries too large to fetch
  whole. The API fetches them in the background when a country is added, or a location placed in a divided country
  (README.md, Maps), and adds each to `tiles.json` once complete. Regions share the tiles along their borders, so draw
  them with one layer whose source asks each tile of the regions whose zooms and bounds hold it and takes the first
  found (breedview `composables/locations/baseMap.js`). Fetch `tiles.json` without caching it (`cache: 'no-cache'`), so
  new regions appear at the next page load.
- The user who added the country or placed the location is emailed when the fetch starts and ends; say so where
  countries are added. There is no status in the API.
