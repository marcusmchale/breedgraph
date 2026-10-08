# Front-end changes: people, access control and registration

This lists the API changes made with the Person, control transfer and invitation work (branches `control_transfer`, `person_implementations` and `invitations`), and what the front end needs to do about each.
Field names are given as in GraphQL (camelCase). Design background is in `person.md` and `control-transfer.md`.

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

Nothing else was renamed. Everything below that is not listed here is new.

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

A Person is someone credited for research, with or without an account. It holds only a display name, teams, lawful basis and, once linked, an ORCID iD.

**Type `Person`:** `id, name, teams, basis, informedAttestation, orcid, linkedUser, recordedBy, recordedAt, erased, erasedAt, restricted`.

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

**Creating:** `peopleCreatePerson(person: PersonInput!, controlTeamId, release)` with `PersonInput { name, teamIds, basis, informedAttestation }`.
- `informedAttestation` must be true: ask the user to confirm the person has been informed that the record is held.
- `basis` is `PUBLIC_TASK` (default) or `LEGITIMATE_INTEREST`.
- Refused unless the control team's organisation has a legal entity (§3).

**Updating:** `peopleUpdatePerson(person: PersonUpdate!)` with `PersonUpdate { id, name, teamIds, basis }`. The linked user can change the name only; other changes need curate access.

**Erasing:** `peopleErasePerson(id)`, by admins of the controlling teams or the linked user.
It cannot be undone: identifying data is removed and the id kept. Ask for confirmation.

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

- `Dataset.contributors` and submitted-data `contributors` resolve to Persons, restricted where needed.
- Password reset with a token works again (it always failed before).
- Fields that work without login: the account flows (register, log in, verify email, password reset), `accountsInvitation` and `organisationsDataProcessingTerms`. Everything else still requires login.
