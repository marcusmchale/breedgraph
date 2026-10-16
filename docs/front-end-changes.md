# Front-end changes: people, access control and registration

This lists the API changes made with the Person, control transfer and invitation work (branches `control_transfer`, `person_implementations` and `invitations`),
and later account deletion and Person institutions, and what the front end needs to do about each.
Field names are given as in GraphQL (camelCase). Design background is in `person.md` and `control-transfer.md`.

Checked against the front end (`breedview` at `7c27267`, 2026-10-13) and the API on master (2026-10-13):
the front end's schema snapshot was compared with the current schema, and every operation in it was validated (§10).
All API changes since the snapshot are listed here.

## 0. Starting point and work list

**Where the front end is.** It is up to date with the API up to the analysis and record grouping work.
It has none of the changes below: no Person pages or forms (contacts and contributors are only read, as `{ id }` and `{ id name }`),
no invitations, transfers, legal entities, account deletion or ORCID. The regions components had uncommitted changes on 2026-10-13.

**First:** regenerate the schema files with the API running, so tooling and the Apollo cache know the new types:
`node scripts/fetchGraphqlSchema.js` writes `src/graphql/schema.graphql`; regenerate `possibleTypes.json` and `unionTypes.json` the same way
(`OntologyEntryUnion` no longer includes `Role` and `Title`). Then `python scripts/check_front_end_queries.py ../breedview/src`
in this repository lists the operations that no longer validate (§10).

**What breaks now** (seven operations, and code the check does not see):

| File | Problem | Fix |
|---|---|---|
| `graphql/account/account.graphql` | queries `allowedEmails` | Query `invitations` instead (§2) |
| `graphql/account/addEmail.graphql`, `removeEmail.graphql` | mutations removed | Delete; use `accountsInvite`, `accountsCancelInvitation` (§2) |
| `components/user/InviteUserModal.vue`, `composables/user/useAuthentication.js` | use allowed emails | Rewrite as invitations (§2) |
| `graphql/ontology/entries.graphql`, `ontology.graphql`, `graphql/programs/study.graphql` | query `Term.roles`, `Term.titles` | Remove them |
| `composables/ontology/createOntologyEntries.js`, `updateOntologyEntries.js` | send `roleIds`, `titleIds` (not caught by the check, as they are variables) | Remove the fields and their form inputs |
| `composables/ontology/nodeColorMap.js` | `ROLE` and `TITLE` labels | Remove |
| `graphql/datasets/submissionWithData.graphql` | spreads `RecordFields` (on `Record`) on `SubmittedRecord`, whose fields differ (`unitId`, `referenceIds`). Older than these changes, and unused | Delete it, or give it its own fields |

`authors` / `authorIds` (§1) are not used by the front end, so need no change.

**Then, new work, in a suggested order:**
1. Registration by invitation (§2): `/register` reads `token`, and the invite modal. Needed before anyone else can register.
2. Persons (§4): a Person display component ("Name (Institution)", restricted and erased forms), used for contacts and dataset contributors,
   then create, edit and erase forms, and a people list.
3. Organisation legal entity (§3), needed before Persons can be created.
4. Profile page from `peopleMyPerson`: edit, ORCID (with a new `/orcid` route), claims, unlink, erase, and account deletion (§6, §8).
5. Contacts on Programs and Trials, with messaging (§5).
6. Claim requests for admins (§6).
7. Control transfers (§7): a transfers page, and "transfer control" from the controller modal.
8. Record group extent and replicate aggregation (§11): the grouping form first, as creating a record grouping fails without it.
9. The area renames (§13): every units, locations, layouts and teams operation fails until it is renamed, so do this
   first, with step 8's grouping form, before the rest.

New routes needed: `/orcid` (ORCID's redirect, §6); probably a profile page, a people page and a transfers page.

## 1. Breaking changes at a glance

| Area | Change | Action |
|---|---|---|
| Registration | `accountsAddEmail`, `accountsRemoveEmail` and `Account.allowedEmails` are removed | Replace with invitations (§2) |
| Registration | After the first account, `accountsCreateAccount` requires `invitationToken`, and the email must be the invited address | Read the token from the invitation link (§2) |
| Person | `Person.fullname` is removed; `Person.name` can be null | Handle restricted and erased Persons (§4) |
| Person | `PersonInput` and `PersonUpdate` change; `peopleDeletePerson` is replaced by `peopleErasePerson` | Update the forms (§4) |
| Person | `peopleCreatePerson` needs the control team's organisation to have a legal entity, and `informedAttestation: true` | §3, §4 |
| Ontology | `authors` / `authorIds` are removed from every entry type and input | Remove from forms and views |
| Ontology | `Role` and `Title` entries are removed: the `ROLE` and `TITLE` labels, the `Role` and `Title` types, `Term.roles`, `Term.titles`, and `roleIds` / `titleIds` in inputs | Remove from forms and views |
| Germplasm | `GermplasmEntry.authors` and `authorIds` in inputs are removed | Cite authors through references |
| Programs | `contactIds` must name Persons linked to an account and released widely enough | Show the errors (§5) |
| Teams | `organisationsDeleteTeam` is refused while the team controls anything | Explain and link to transfers (§7) |
| Programs | `GroupingInput` requires `extent` | Add it to the grouping form (§11.2) |
| Units, locations, layouts, teams | The `blocks`, `regions`, `arrangements` and `organisations` areas are renamed `units`, `locations`, `layouts` and `teams`; `Location.region` and `Layout.arrangement` become `root`, `DatasetSummary.blocks` becomes `unitRoots` | Rename the operations and the response keys (§13) |

Nothing else was renamed. Everything below that is not listed here is new.
Sections before §13 still use the old area names, e.g. `organisationsDeclareLegalEntity` for `teamsDeclareLegalEntity`: §13 maps them.

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

## 3. Organisations: legal entity

An organisation must declare the legal entity responsible for it before it can record Persons.

- `Team.legalEntity` (organisation roots only): `legalName, privacyContact, termsVersion, declaredAt, declaredBy`.
  `declaredBy` is only resolved for admins of the team.
- `organisationsDataProcessingTerms` (no login needed) returns `version` and `url` of the current data processing terms.
  When `version` is null, no terms are configured and declaring is not possible; hide the option.
- Declaring, by admins of the root team only:
  - when creating an organisation: `TeamInput.legalEntity { legalName, privacyContact, termsVersion }`, with no `parentId`;
  - later: `organisationsDeclareLegalEntity(teamId, legalEntity)`.
  Show the terms (link to `url`) and require the user to accept them; send the `version` shown as `termsVersion`.
  Declaring again replaces the current declaration, accepting the current terms again.
- `privacyContact` should be a role address, such as `dataprotection@…`, not a person's own.
- `organisationsWithdrawLegalEntity(teamId)` withdraws the declaration, by root admins. It is refused while the organisation controls any Person, including erased ones: they must be transferred first.

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
- Refused unless the control team's organisation has a legal entity (§3).

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
  The user must administer every team in `fromTeamIds`. `recipientTeamId` is often another organisation's root team.
  `keepFromTeams: true` shares control instead of handing it over.
  If the user also administers the recipient team, giving `toTeamIds` (and `release`) accepts at once.
- `controlsAcceptTransfer(id, toTeamIds, release)`: by admins of the recipient team. `toTeamIds` are the recipient team or teams below it that the user administers; `release` defaults to `PRIVATE`.
- `controlsRejectTransfer(id)` (recipient side), `controlsCancelTransfer(id)` (offering side).
- `controlsRenounceControl(entities, teamIds)`: give up control where other teams also control the entities.

Persons can only be transferred to an organisation with a legal entity (§3), and shared only within one organisation.
Admins of the recipient team are emailed about new offers.

**Teams:**
- `organisationsDeleteTeam` is refused while the team controls anything: transfer or renounce its control first.
- Deleting a team cancels pending transfers to or from it. Deleted teams no longer appear anywhere.
- Offers may become impossible to accept if the offering team loses control in the meantime; accepting then returns an error.

## 8. Other changes

- `accountsDeleteAccount(password, erasePerson)` deletes the user's own account and logs them out. Ask for the password, and ask whether to erase their linked Person as well, ticked by default.
  Errors explain when it is refused: the only ontology admin, or the only admin of a team (the message lists the teams).
  Deleted users show as null wherever a user is shown, like users the viewer can't see.
  The deletion takes effect at once: the user's login no longer works, and their username is free to register again. It stays deleted if a backup is restored,
  and its id is never given to a new account afterwards, so an id cached by the front end never comes to mean another user (`docs/person.md` §5).
  Nothing in the API changes for this.

- `Dataset.contributors` and submitted-data `contributors` resolve to Persons, restricted where needed.
- Password reset with a token works again (it always failed before).
- Fields that work without login: the account flows (register, log in, verify email, password reset), `accountsInvitation` and `organisationsDataProcessingTerms`. Everything else still requires login.

- Record groupings have an `extent` (record group types an optional `defaultExtent`), and analysis terms have a `replicateAggregation` (§11).

## 9. Migrated BreedCAFS data

The BreedCAFS migration (`src/breedcafs_migration/`) loads data the front end has not shown at this scale. Nothing in the API changes for it, but expect:
- **Size.** 41 fields with up to about 3,300 units each (field → trees → cherries and samples), 1,176 datasets of up to about 6,900 records,
  35,665 units and 213,761 records in all, besides the curves. Block, dataset and analysis views should page or virtualise rather than load a whole field.
- **Blocks, branches and leaves as record groups.** None is a unit. A branch's or leaf's records are on its tree, with the
  branch or leaf as a code in the study's Branch or Leaf grouping (`WITHIN_UNIT`), and a branch's canopy stratum in the
  Stratum grouping (`SHARED`). Records of what is in a BreedCAFS block carry its name in the Block grouping (`WITHIN_GRAPH`, §12),
  and the trees and samples hang from the field. Record and analysis views should show record group codes beside the unit,
  or a tree's branches look like repeated readings.
- **Persons as contributors.** Dataset contributors are Persons with an institution, `PRIVATE` until handover, so most users see them restricted (§4).
- **Curves.** The four fluorescence curve datasets (Fluorescence ~ Time, PocketPEA) have records with no value: each references its dataset's CSV data file,
  whose schema gives the index columns (`item_uid, unit_id, time, replicate`) that find a record's row. The existing complex-scale cells show the reference count.
- **Times as entered.** Record times are to the minute where a time of day was entered, and to the day otherwise. `DateTime` values keep their precision,
  e.g. `2018-11-25` or `2018-11-25T10:30`; show them as given rather than parsing a date alone into midnight in the browser's time zone.
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
- Against the test database:
  - (a) create a grouping with each extent, of a type with a default extent and of one without;
  - (b) curate a dataset with a WITHIN_UNIT grouping: there are no sections by replicate code;
  - (c) submit a descriptive analysis of replicate data, without and then with `replicateAggregation`. Without, it fails
    with `DUPLICATE_OBSERVATION` at `replicateAggregation`; with, it completes.
- The test database must be rebuilt for the groupings to have an extent.

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
