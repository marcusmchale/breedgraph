# Person: design note

Status: **draft for review**, including review by the Data Protection Officer.
This note records why Person exists, what it stores, and how GDPR requirements shape it.
It is not legal advice. The legal points summarise the usual reading of GDPR and need confirming for our institution.

## 1. Purpose

A Person is **someone who took part in our research**: staff, technicians, collaborators.
It gives them a stable identity for **attribution** ("who produced this data") whether or not they have an account.

A Person is **not**:
- an account. Accounts are Users. A User may be linked to one Person (see §6).
- a way to contact someone directly. Messages to a contact go through the platform to the linked User (see §4).
- a record of external or historical people such as literature authors or variety breeders. Those are cited through References (see §4).

## 2. Legal framing

| Topic | Position |
|---|---|
| Lawful basis | Research: **Art. 6(1)(e) public task**, as the University is the data controller of every Person (below). **Not consent**, because consent can be withdrawn and that would break attribution. The basis is stated in the privacy notice, not per record. |
| Minimisation | Store only what attribution needs: a display name, institution, affiliation, optionally ORCID. No email, phone, postal address or free text. |
| Informing people (Art. 14) | Covered by the published BreedGraph privacy notice, with the employer's staff notice (Art. 14(5)(b) research exemption from notifying each person individually). The person creating a record confirms the person was told about the record and the BreedGraph privacy notice, and that confirmation is stored. BreedGraph never emails people who are not users. |
| Erasure (Art. 17) | Research may be exempt (Art. 17(3)(d)), but we don't rely on that. Erasure **tombstones** the Person: identifying data is removed, and contributions stay attributed to an anonymous id. This satisfies both the person and the research record. |
| Objection (Art. 21) | Limited for public-interest research (Art. 21(6)). In practice, erasure is the remedy we offer. |

### Data controller

BreedGraph is operated by a team within the University of Galway. Partner organisations enter data, including Person
records about their own staff.

- **The University is the data controller of every Person record**, as of all personal data in BreedGraph
  (docs/legal/privacy-notice.md). This was decided on 2026-10-19, to keep the obligations simple while BreedGraph is
  in development; it replaced a model in which each team tree's root declared a legal entity, the data controller of
  its Persons, and accepted data processing terms (in git history before then).
- **Teams decide access, not legal responsibility.** A Person's controlling teams decide who reads it, as for every
  controlled entity, and transfers move that control between teams of any team trees.
- Users who record a Person act for the University. They confirm that the person took part in the research, was
  told about the record and the BreedGraph privacy notice, and consented to it (`consent_attestation`).
- Requests from people about their data go to the University (the privacy notice's contact). Admins of the
  controlling teams and the linked user can erase a Person in BreedGraph; for anyone else, the operator erases it with
  `scripts/erase_person.py` after confirming who is asking (§5), or invites them to claim the record (§6).
- If a partner later needs to be the data controller of its own staff's records, the per-organisation model would have
  to come back.

**Terminology.** In GDPR, a *data controller* is the legal organisation responsible for the data. In BreedGraph,
`Controller` is the access-control object on a model, and has nothing to do with it. Documents about data protection
should say "data controller" for the legal sense.

## 3. Model

```
Person
  id
  name                    # display name used for attribution
  institution?            # institution the person did the work with, as free text, for attribution
  orcid?                  # set only by the linked User, verified through ORCID sign-in (§6)
  teams[]                 # affiliation: (Person)-[:IN_TEAM]->(Team)
  user?                   # (User)-[:IS_PERSON]->(Person), one-to-one; gives subject rights
  consent_attestation     # creator confirmed the person consented
  recorded_by, recorded_at  # set by the system
  erased_at?              # tombstone marker
```

Person remains an access-controlled model (`ControlledModel`), released at most to registered users (§3).
The lawful basis is the same for every Person, as the University holds them all (§2), so it is not stored per record;
older nodes may keep a `basis` property, which is ignored.

`institution` is shown with the name, as an author's affiliation is in a publication.
Teams only cover organisations represented in BreedGraph, and many people are credited for work done with other institutions,
e.g. the partners of migrated BreedCAFS data. It is set and changed like the name, by curators and the linked User,
has the same visibility as the name, and is cleared on erasure.

### Removed from the current model

| Field | Reason |
|---|---|
| `email`, `phone`, `mail` | Contact details belong to the User account, if anywhere. |
| `description` | Free text tends to collect sensitive information. |
| `fullname` | One `name` is enough for display. |
| `titles` (and the `Title` ontology entry) | Not needed for attribution. The ontology entry is removed. |
| `roles` (and the `Role` ontology entry) | Not needed for attribution. Roles describing a Person stay removed; the roles a Person had in a contribution are `Role` ontology entries on the contribution (`contributions.md`). |
| `locations` | Extra personal data; teams and institution already give affiliation. |

### What viewers see

| Viewer | View (`Person.view`) | Sees |
|---|---|---|
| A read affiliate of a team controlling the record, or the linked User | `FULL` | The record: name, institution, ORCID iD, teams, informed attestation, when it was recorded, whether an account is linked (`linked`), and erasure. Who recorded it and the linked account follow docs/read-access.md rule 9 |
| A signed-in user who can read it only because it is released to registered users | `ATTRIBUTION` | What attribution needs: name, institution, ORCID iD, and whether it was erased |
| Any other signed-in user, where the Person is referred to (a contact, a contributor) or asked for by id | `RESTRICTED` | The id only (`restricted`). They can use it to look up who controls the record |

Releasing a Person therefore shows only its attribution: teams and record-keeping stay with the controlling teams and
the subject. Curators and admins of a controlling team see the full record, as approving curate or admin access also
grants read access, and read access can't be removed while either is held.
A Person without current controls is not released to anyone, so it fails closed.

**Persons are for signed-in users only.** A Person's release is at most REGISTERED: creating one, setting its release
(`controlsSetRelease`, by ids or in bulk) and accepting a transfer of it all refuse PUBLIC
(`AccessControlService._require_release_ceiling`). Anonymous users get no contacts or contributions at all
(`query_builders.access.signed_in_only`), not even restricted placeholders, so they meet no Persons; listing and
looking up Persons (`people`, `peoplePeople`, `peoplePerson`) needs an account too. There is no public directory, and
public research shows no one's name: credit is for the registered, invited community.

Searches (`people`, by name or not) return only the Persons the viewer sees in full or by attribution, so a name does
not reveal that a hidden Person has it. In the full view, a Person's teams the viewer cannot see are shown as the
nearest team they can see that includes them, marked as standing in (`TeamReference.standIn`), as for controllers
(docs/read-access.md, rule 7). A Person's teams are affiliation for attribution (`(Person)-[:IN_TEAM]->(Team)`),
separate from the linked user's access affiliations, and only curators change them. A curator can only give teams
they can see, and saving keeps the teams hidden from them, so curators who see different teams do not drop each other's.
Reads go through the people view (`query_builders/people.py`), which builds each view in Cypher; the repository and
`PersonStored.redacted` serve writes.

An erased Person shows as "Erased person" with its `id` to everyone who could see it before; to others it is
restricted, as before, so erasure is not revealed to them.

## 4. Where Person is referenced

| Reference | Decision |
|---|---|
| `Dataset.contributors` | Replaced by contributions, `(Person)-[:CONTRIBUTED_TO {roles}]->(Dataset)`, with optional roles (`contributions.md`). Resolved through `people_map`. |
| `Program/Trial.contact_ids` | Resolved through `people_map`. Contacts are described below. |
| Contributions to Programs, Trials and file, data file and external data references | As for datasets (`contributions.md`). |
| `OntologyEntry.authors` | Removed. External authors are cited through `references`; contributors to the ontology are recorded by its edit history. |
| `GermplasmEntry.authors` | Removed, cited through `references`. Older entries may keep an `authors` property, which is ignored. |

### Contacts

A contact is someone others can ask about a Program or Trial, by message through BreedGraph. To be listed as a contact, a Person:
- is linked to a User, who receives the messages, and
- is released to registered users, the widest a Person can be (§3), so every signed-in user who can see the Program sees the contact.
  This is checked when contacts are set. If its release is lowered later, signed-in users who can't read it see it restricted (id only).
  Anonymous users see no contacts.

The linked User can remove themselves as a contact.

Messages are sent by BreedGraph to the linked User's email address, which the sender never sees:
- Only registered users can send, and only to Persons listed as contacts of something they can read.
- The sender's name is included, with their email address as reply-to; the sender is told it will be shared.
- Messages are rate limited per sender, limited in length, and have no attachments.
- Logs record that a message was sent, from whom and to whom, never its content.

The User is told about messaging when they link the Person to their account (§6, Notes for front-end development).

Implemented in step 9b:
- Program and Trial handlers check contacts when they are added: each must exist, not be erased, be linked, and be released to registered users.
- `peopleRemoveSelfAsContact(entityLabel, entityId)` removes the user's Person as a contact.
- `peopleContactPerson(personId, entityLabel, entityId, subject, message)` sends a message about a Program or Trial the sender can read, to a Person listed as its contact.
  `MESSAGE_RATE_LIMIT_PER_HOUR` (default 10), `MESSAGE_MAX_LENGTH` (5000) and `MESSAGE_SUBJECT_MAX_LENGTH` (200) apply; the rate is counted in Redis per sender.
| `UserStored.person` | Becomes the `IS_PERSON` relationship, which is currently never saved. |

## 5. Erasure (tombstone)

Deleted accounts are tombstoned too, and logged in the same erasure log (§6, Deleting an account).

Erasing a Person:
- clears `name`, `institution`, `orcid` and `IN_TEAM` relationships, and sets `erased_at`.
- keeps `id`, access controls and provenance fields, and the `CONTRIBUTED_TO` and `HAS_CONTACT` references to it.
- removes the `IS_PERSON` link and pending requests to be linked (`CLAIMS`).
- appends the `id` to an **erasure log** (ids only, no personal data). After restoring a backup, erasures in the log are re-applied.

Who can erase: admins of the teams that control the record, and the linked User. For requests made to the University by
anyone else, the operator runs `scripts/erase_person.py <id>` after confirming who is asking: it logs the erasure and
applies it as a replay would (`adapters/neo4j/erasures.erase_person`), so it is applied again after a restore.

Backups and logs:
- Backups (e.g. `instance/neo4j_archive/`) are kept for a documented retention period.
- The erasure log is a JSON-lines file at `PERSON_ERASURE_LOG_PATH` (default `instance/person_erasure_log.jsonl`), outside the database, so restoring a backup does not roll it back.
  There is one log, and it is only ever appended to: nothing in it is changed or removed.
  It has one line per erased Person, `{"person_id", "erased_at", "created_at"}`, and per deleted account, `{"user_id", "deleted_at", "created_at"}`,
  where `created_at` is when the Person or account was created (`recorded_at`, `time`).
  It is appended to by the `PersonErased` and `AccountDeleted` event handlers after the change is committed, so every logged erasure happened.
  The setting and file keep their Person names, so existing deployments need no change.
- `scripts/backup.sh` (cron on the web server) writes timestamped dumps, encrypted with age (README, "Encryption key"). `scripts/sync_database_backups.sh` (cron on the archive server, settings as in `instance/backup_sync.env`) copies new dumps and the erasure log.
  It is unrelated to the file archive worker. The log is copied with `rsync --append-verify`, so a truncated log on the web server never shortens the copy. Run it at least as often as dumps are made.
  `BACKUP_RETENTION_DAYS` optionally removes old dumps on the archive server; the erasure log is never removed.
- `scripts/restore.sh` loads a dump and then runs `scripts/apply_erasures.py`, which applies the log again: Persons are erased and accounts tombstoned again, with their logged times, including those logged after the dump was taken. Replaying is idempotent.
- **Ids issued again after a restore.** Ids come from counters in the database, so a restored backup has the counters of its time: a Person or account created after the restore can be given the id of one erased after the backup, which a replay would then erase. Two guards:
  - A replay erases or deletes only the record with the logged id *and* creation time (to the millisecond). A record holding the id but created at another time is left alone, and reported as reissued. This also covers ids issued again before the replay ran, and a log replayed onto another database's dump, e.g. a test database on a development machine, whose records were created at other times. Entries without a creation time, which only a log written before they were logged has, can't be matched to their record, so are skipped and reported.
  - A replay advances the Person and account id counters past every id in the log, so after a restore and replay no logged id is issued again.
  - Restores should still be followed by the replay before the API takes requests, as `restore.sh` does.
- Personal data is not written to application logs. Log ids and actions, not mutation payloads.

## 6. Linking a User to a Person (claiming)

Two routes, both ending in a confirmed `IS_PERSON` link:

1. **Invitation.** An invitation can name a `person_id`. Registering with `linkPerson` links it, because the invitation token and email verification prove identity.
   The link is made with the inviter's authority, which is checked again: they must still administer a team controlling the Person. The user can register without linking.
2. **Request and approve.** A registered user asks to claim a Person by id (`peopleRequestClaim`), even one they can only see as an id; the request reveals only whether the Person can be linked (it is refused for an erased or already linked Person).
   Admins of the controlling teams are emailed, see pending requests with the requester's name (`peopleClaimRequests`), and approve or reject them, confirming the user's identity first.
   Approving links the user and drops other pending requests. The requester sees their own pending requests (`peopleMyClaims`) and can withdraw them.

A request is stored as `(User)-[:CLAIMS {time}]->(Person)`. Each account is linked to at most one Person, and each Person to at most one account.
The user is emailed when linked, including the notice about messaging below. The linked user or admins of the controlling teams can unlink (`peopleUnlinkPerson`).
`peopleMyPerson` returns the user's linked Person in full.

### Notes for front-end development

When a user links a Person to their account (accepting an invitation that names a Person, or confirming a claim), tell them before they confirm:
- Other users may message them through BreedGraph if the Person is listed as a contact on a Program or Trial.
  Messages arrive at their account email address, which senders never see.
- They can remove themselves as a contact, and unlink or erase the Person at any time.

Show this as part of the confirmation step, not only in the privacy notice.

### Invitations replace allowed emails

Instead of allowed emails, or unregistered Users holding email addresses indefinitely:

```
Invitation
  email
  invited_by
  teams[]
  person_id?
  expires_at
```

```
(inviter: User)-[:INVITED]->(Invitation {email, created_at, expires_at})
(Invitation)-[:OFFERS_TEAM {access}]->(Team)
(Invitation)-[:OFFERS_PERSON]->(Person)
```

The invitation, including its email address, is deleted when accepted, cancelled or expired. This gives a clear retention period for the only email address held for a non-user.

- **Inviting.** Any registered user can invite an email address, once per address while their invitation is pending.
  They can offer affiliations to teams they administer, with one or more access levels to each, and a Person controlled by a team they administer.
- **The invitation email** links to `/register?token=…`, with the token also attached as JSON. The token is signed and names the invitation.
  `accountsInvitation(token)` shows what the invitation offers, without login, for the registration form.
- **Registering.** Registration requires the token, and the email address must be the one invited; email verification then proves ownership. The site's first account, which invites the others, is made on the server (`scripts/create_first_account.py`), so that nobody can register before it.
  The user chooses which offered teams to accept (`acceptTeamIds`), with every access offered to each; others are declined. Accepted affiliations are authorised, provided the inviter still administers the team; Curate and Admin include Read, as when a request is approved.
  The offered Person is linked only when the user confirms, see claiming (step 9).
- **Expiry.** `INVITATION_EXPIRY_DAYS` (default 30). The inviter can resend, which extends the expiry with a new token, or cancel.
  Expired invitations are ignored, and deleted by `/retention/run`, which `scripts/trigger_retention.sh` calls from cron.

### Subject rights

A linked User can always, regardless of access controls:
- read their Person record
- edit `name`
- link or remove their ORCID iD
- erase the record (§5)
- unlink their account

### ORCID

The ORCID iD is public. What BreedGraph controls is the link between the iD and a person's contributions, so it shares the record's release level and is cleared on erasure.

Only the linked User can set it, by signing in with ORCID. This means every stored iD is verified, and nobody can be wrongly credited through a mistyped iD. Unlinked Persons are identified by name and teams only.

The flow runs through GraphQL, so every step is authenticated and protected against request forgery.
The login cookie is `SameSite=Strict`, so it would not be sent on ORCID's redirect back to a server route.
1. `peopleStartOrcidLink` returns ORCID's sign-in URL (`scope=/authenticate`), with a random single-use `state` stored in Redis against the user for `ORCID_STATE_EXPIRES_SECONDS` (600).
2. ORCID redirects to `ORCID_REDIRECT_URI`, a front-end page (default `/orcid`), adding `code` and `state`, or `error` if the user cancelled.
3. The page calls `peopleCompleteOrcidLink(code, state)`. The server checks the state was issued to this user, exchanges the code with ORCID using `httpx`, validates the returned iD (including its check digit), and stores it.

- Only the iD is stored. ORCID's access token and name are not kept.
- One Person per iD: checked when linking, and a uniqueness constraint in `create_constraints.cypher` for new databases.
- `peopleRemoveOrcid` removes it. Only the linked user can set or remove it.
- Config in `instance/*.env`: `ORCID_CLIENT_ID`, `ORCID_CLIENT_SECRET` (ORCID **Public API** credentials, free), `ORCID_BASE_URL` (default `https://sandbox.orcid.org`; `https://orcid.org` in production) and `ORCID_REDIRECT_URI`, which must be registered with ORCID.
  Without credentials, `peopleStartOrcidLink` returns an error saying linking is not available.
- Front end: a "Connect your ORCID iD" button following ORCID's brand guidelines, showing the iD as its full `https://orcid.org/…` address.

This links an ORCID iD to an existing account. Signing in to BreedGraph with ORCID is a separate, later decision.

Everything else (other users' visibility, write access) follows the normal access controls.
Persons are also how others see who did something: write stamps and ontology commits name the account's Person,
as accounts themselves are shown only to their owner and admins of their teams (docs/read-access.md, rule 9).
This includes the record's controller: a linked user who cannot otherwise read their Person sees its placeholder
controller (docs/read-access.md, rule 8), without its history, and the controlling teams stood in for by the nearest
teams they can see, which is where to ask for changes they cannot make themselves. This is intended.
The subject may lower the release level, but cannot hide the record from the teams that control it. Erasure is available if they want more.

### Deleting an account

The user is asked whether to erase their Person record as well. Erasure is the default. Either way the link is removed.

`accountsDeleteAccount(password, erasePerson = true)` deletes the user's own account after checking the password (failures count towards the login lockout), and clears the login cookie.
- Refused while the user is the only ontology admin, or the only authorised admin of a team, counting heritable admins of ancestor teams.
- The User node is **tombstoned**: relabelled `DeletedUser`, keeping only `id` and `deleted_at`. Affiliations, the Person link, claims and pending invitations they sent are removed, as are their archive retrieval requests.
  Provenance (contributions, ontology commits and lifecycle changes) stays attributed to the anonymous id; user ids are never reused.
- A login token holds until it expires, so the GraphQL context checks on every request that the user still exists, and
  that the token was signed after the user's sign-ins were last ended (`User.sign_ins_ended_at`, set when the password
  changes or is reset, which re-signs the browser that changed it and refuses reset links sent before).
- Their submissions and analyses in Redis are deleted, cancelling queued analyses. Uploaded files are kept, as they belong to References.
- Unverified accounts are still deleted outright, when someone registers again with the same email.
- The deletion is logged in the erasure log (§5), and tombstoned again if a backup taken before it is restored. If the Person was erased, that is logged too.
  `AccountStored.delete()` raises `AccountDeleted`; repositories keep removed aggregates until commit so their events are published.
  Its handlers write the log entry and clear the Redis state.

## 7. Decisions

| Question | Decision |
|---|---|
| Data controller | The University, for every Person (2026-10-19, §2). It replaced per-team-tree legal entities and data processing terms. |
| Lawful basis | Public task, the same for every Person, so stated in the privacy notice rather than per record. |
| ORCID | Set only by the linked User through ORCID sign-in. Not recorded for unlinked Persons. |
| Public attribution | None: Persons are released at most to registered users, and anonymous users see no contacts or contributions (§3). Admins of the controlling team decide between their teams and registered users. |
| User and Person names | The Person keeps its own `name`, so people choose how they are credited, separate from their account name. |
| User without a Person | Allowed. A Person is created only when someone is credited or named as a contact. |
| Retention of unlinked Persons | Kept as long as the data they are attached to, as stated in the privacy notice. |

## 8. Open questions

None for Person. Open questions on control transfer are in `control-transfer.md` §6.

## 9. Implementation plan

0. **Team tree legal entity.** Built, then removed on 2026-10-19 (step 13).
1. **Domain.** Done: `PersonInput` requires a name and the informed attestation; `PersonStored` adds `orcid`, `user`, provenance and `erased_at`, `redacted()` gives readers and the linked user the full record and other registered users the ID only, and `erase()` clears identifying data for admins of the controlling teams or the linked user. `LawfulBasis` enumerated the bases until step 13.
2. **Commands.** Done: `CreatePerson`, `UpdatePerson`, `ErasePerson`, replacing `DeletePerson`.
3. **Cypher and repository.** Done: queries rewritten for the reduced model, fixing the wrong `teams` match, the role and title labels (both removed), the unescaped name search, and the error on a missing ID.
   Persons cannot be removed. `ControlledRepository._can_change` lets the linked user store changes to their own record, and admins of the controlling teams store an erasure, besides curators.
4. **Handlers.** Done: creating requires the referenced teams to exist; updating an erased Person is refused, and the linked user can change only the name; erasing raises `PersonErased`, which is written to the erasure log. Replay script and backup scripts as in §5.
5. **GraphQL.** Done: `Person` type with `restricted` (id only) and `erased` flags, queries `people(name)`, `peoplePeople(ids)` and `peoplePerson(id)`, mutations `peopleCreatePerson`, `peopleUpdatePerson` and `peopleErasePerson`.
   `update_people_map` loads Persons by id into the request context; lookups by id return the id-only form to registered users without read access.
   Mutation resolvers log IDs and actions only.
6. **References to Person.** Done: `contributors` and `contacts` resolve through `people_map`; ontology and germplasm `authors`, and the `Role` and `Title` ontology entries, are removed.
   Contacts as described in §4, with the email endpoint, follow claiming (step 9).
7. **Logging.** Done: the message bus logs commands and events as their name and ID fields (`service_layer/log_safety.py`); validation errors are logged without input values;
   the auth token and request context, user records, account names, emails and login usernames are no longer logged at debug level.
   `LOG_LEVEL` defaults to `INFO` unless `ENVIRONMENT=development`, as library debug logs (e.g. Neo4j query parameters) may contain personal data.
   GraphQL errors include Ariadne's debug extension (stack trace and local variables) only when `ENVIRONMENT=development`.
   Usernames of locked-out login attempts are still logged as warnings, for security monitoring; the privacy notice should say so.
8. **Invitations.** Done, on the `invitations` branch: invitations replace allowed emails, which are removed with their `Email` nodes and `ALLOWED_REGISTRATION` links.
   Existing data is not migrated; the development database is flushed.
9. **Claiming and subject rights.** Done: linking through invitations and through requests approved by admins, unlinking, and the linked user's rights from step 1.
   Person changes are stored field by field, so changes stored from the id-only form, such as a request, do not overwrite the record.
   9b, done: contacts and messaging (§4).
   Done: deleting an account erases the linked Person by default (§6).
10. **ORCID linking.** Done, as described in §6, through GraphQL rather than server routes. Tested against a fake ORCID service and a mocked token exchange; to test against ORCID, register an application in the sandbox and set the credentials.
11. **Privacy notice.** Drafted for the DPO: `docs/legal/privacy-notice.md`, with the points to confirm in
    `docs/legal/privacy-notice-notes.md`.
12. **Views.** Done (2026-10-17): the three views of §3 (`Person.view`, `linked`), no public directory (the people and
    team queries need an account), setting the release refused without current controls, and transfer offers only to
    teams the offerer can see.
13. **One data controller.** Done (2026-10-19): the University holds every Person (§2). Legal entity declarations, the
    data processing terms, `Person.dataController`, the per-record lawful basis and the one-team-tree rule for
    transfers are removed. Persons are released at most to registered users, anonymous users get no contacts or
    contributions, and `scripts/erase_person.py` erases for requests made to the University.

Tests accompany each step: repository, handlers, then GraphQL end-to-end covering each viewer type in §3 and erasure.
