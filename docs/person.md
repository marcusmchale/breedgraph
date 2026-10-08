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
| Lawful basis | Research. Usually **Art. 6(1)(e) public task** for a university, **6(1)(f) legitimate interests** for private partners. **Not consent**, because consent can be withdrawn and that would break attribution. |
| Minimisation | Store only what attribution needs: a display name, affiliation, optionally ORCID. No email, phone, postal address or free text. |
| Informing people (Art. 14) | Covered by the employer's staff privacy notice plus a published BreedGraph privacy notice (Art. 14(5)(b) research exemption from notifying each person individually). The person creating a record confirms the person has been informed, and that confirmation is stored. BreedGraph never emails people who are not users. |
| Erasure (Art. 17) | Research may be exempt (Art. 17(3)(d)), but we don't rely on that. Erasure **tombstones** the Person: identifying data is removed, and contributions stay attributed to an anonymous id. This satisfies both the person and the research record. |
| Objection (Art. 21) | Limited for public-interest research (Art. 21(6)). In practice, erasure is the remedy we offer. |

### Data controllers

BreedGraph is operated by a team within the university. Partner organisations enter data, including Person records about their own staff.

- **Each organisation has exactly one legal entity, declared on its root team.**
  Child teams never declare a legal entity of their own.
  An organisation's team tree can model a collaborative network for data registration, but a Person always has one definite responsible party.
  Partners in a consortium who are separate legal entities are separate organisations.
- **The data controller of a Person is the legal entity of the organisation containing the record's write team.**
  The write team comes from the creating user's write affiliation.
  The user acts on behalf of that organisation; the user is not the data controller.
- **The agreement is made when an organisation root is created**, i.e. when a team is created without a parent, or a team is moved to become the root of an organisation.
  The creating admin gives the legal entity's name and a privacy contact (a role address such as `dataprotection@partner.org`, not an individual's), and accepts the BreedGraph data processing terms.
  The terms set out the university's role as host, and the partner's responsibilities as data controller: informing staff, handling requests from people about their data, and erasure.
  The terms text comes from the university's DPO or legal office. The software records who accepted which version, and when.
- The formal arrangement between the university and partners (joint controllers under Art. 26, or processor under Art. 28) is set by those terms or a consortium agreement, not by the software.
- Release decisions follow the existing access-control pattern: admins of the controlling team decide who can read the record, up to public release.
  Releasing a Person publicly is a disclosure decision, so the organisation's privacy notice must cover public attribution.

#### Legal entity declarations

```
(root: Team)-[:DECLARED {current}]->(LegalEntityDeclaration)
  legal_name
  privacy_contact
  terms_version
  declared_by, declared_at
```

- The current data processing terms are configured by `DATA_PROCESSING_TERMS_VERSION` and `DATA_PROCESSING_TERMS_URL`.
  Declaring requires the version the user was shown to equal the configured version. Without a configured version, declaring is refused.
- Declaring again creates a new declaration and accepts the current terms again. Earlier declarations are kept, and only the latest is current.
- Visibility follows the team: the legal name, privacy contact, terms version and time are visible wherever the root team is.
  Who declared is visible to admins of the root team only, as for affiliations.
- Withdrawing a declaration is not supported yet. When Persons exist, it will be allowed only for organisations that control no Persons.

#### Declaring is optional

Declaring a legal entity is optional for an organisation. Organisations that only model collaboration can exist without one.
**Creating a Person requires the write team's organisation to have a declared legal entity.**
Root admins of existing organisations, or organisations created without a declaration, can declare one later and accept the terms at that point.

#### One organisation per Person

A Person's access controls may only name teams in a single organisation.
`Controller.controls` can otherwise hold teams from several organisations, which would leave the data controller ambiguous.
`set_controls` for a Person refuses control teams from another organisation.

#### Changing the data controller

Any change that would put a Person under a different organisation is a **transfer of data controller**.
This can happen in several ways:

| Change | Effect on Persons controlled by the moved teams |
|---|---|
| Move a team within its organisation | None |
| Split: a team becomes the root of a new organisation | Would move to the new organisation |
| Merge: a root becomes a child of a team in another organisation | Would move to the other organisation. The merged root's declaration ends, since only roots declare |
| Move a team to another organisation | Would move to the other organisation |
| Set a Person's control teams to teams in another organisation | Would move to the other organisation |
| Delete a team that controls Persons | Would leave Persons without a controlling team |

All of these go through the control transfer mechanism in `control-transfer.md`, which applies to every controlled entity:
an admin on the giving side offers, an admin on the receiving side accepts, and the transfer is recorded.
For Persons, the receiving organisation must have a declared legal entity, and this applies to erased Persons too.

As for every controlled entity, a Person is created with an explicit write team (`control-transfer.md` §6).

Declarations are kept as history when a root stops being a root, so it remains possible to see which legal entity was responsible at any time.

**Terminology.** In GDPR, a *data controller* is the legal organisation responsible for the data.
In BreedGraph, `Controller` is the access-control object on a model.
They are connected through the controlling team's organisation, but are not the same thing.
Documents about data protection should say "data controller" for the legal sense.

## 3. Model

```
Person
  id
  name                    # display name used for attribution
  orcid?                  # set only by the linked User, verified through ORCID sign-in (§6)
  teams[]                 # affiliation: (Person)-[:IN_TEAM]->(Team)
  user?                   # (User)-[:IS_PERSON]->(Person), one-to-one; gives subject rights
  basis                   # PUBLIC_TASK | LEGITIMATE_INTEREST
  informed_attestation    # creator confirmed the person was informed
  recorded_by, recorded_at  # set by the system
  erased_at?              # tombstone marker
```

Person remains an access-controlled model (`ControlledModel`) with the usual release levels.

### Removed from the current model

| Field | Reason |
|---|---|
| `email`, `phone`, `mail` | Contact details belong to the User account, if anywhere. |
| `description` | Free text tends to collect sensitive information. |
| `fullname` | One `name` is enough for display. |
| `titles` (and the `Title` ontology entry) | Not needed for attribution. The ontology entry is removed. |
| `roles` (and the `Role` ontology entry) | Not needed for attribution, including on contributions. The ontology entry is removed. |
| `locations` | Extra personal data; teams already give affiliation. |

### What viewers see

| Viewer | Sees |
|---|---|
| Has read access, or is the linked User | The full record |
| Registered, without read access | `id` only. The id can be used to look up who controls access to the record. |
| Anonymous | Nothing |

An erased Person shows as "Erased person" with its `id` to everyone who could see it before.

## 4. Where Person is referenced

| Reference | Decision |
|---|---|
| `Dataset.contributors` | Keep, as `(Person)-[:CONTRIBUTED_TO]->(Dataset)` without a role. Resolved through `people_map`. |
| `Program/Trial.contact_ids` | Resolved through `people_map`. Contacts are described below. |
| `OntologyEntry.authors` | Removed. External authors are cited through `references`; contributors to the ontology are recorded by its edit history. |
| `GermplasmEntry.authors` | Removed, cited through `references`. Older entries may keep an `authors` property, which is ignored. |

### Contacts

A contact is someone others can ask about a Program or Trial, by message through BreedGraph. To be listed as a contact, a Person:
- is linked to a User, who receives the messages, and
- has a release level at least that of the Program or Trial, and at least REGISTERED, so anyone who can see the Program can see the contact.
  This is checked when contacts are set. If either release changes later, contacts the viewer cannot read are shown restricted (id only).

The linked User can remove themselves as a contact.

Messages are sent by BreedGraph to the linked User's email address, which the sender never sees:
- Only registered users can send, and only to Persons listed as contacts of something they can read.
- The sender's name is included, with their email address as reply-to; the sender is told it will be shared.
- Messages are rate limited per sender, limited in length, and have no attachments.
- Logs record that a message was sent, from whom and to whom, never its content.

The User is told about messaging when they link the Person to their account (§6, Notes for front-end development).

Contacts depend on linking Users to Persons (§6), so they are implemented with or after claiming.
| `UserStored.person` | Becomes the `IS_PERSON` relationship, which is currently never saved. |

## 5. Erasure (tombstone)

Erasing a Person:
- clears `name`, `orcid` and `IN_TEAM` relationships, and sets `erased_at`.
- keeps `id`, access controls, `basis` and provenance fields, and the `CONTRIBUTED_TO` and `HAS_CONTACT` references to it.
- removes the `IS_PERSON` link.
- appends the `id` to an **erasure log** (ids only, no personal data). After restoring a backup, erasures in the log are re-applied.

Who can erase: admins of the teams that control the record, and the linked User.

Backups and logs:
- Backups (e.g. `instance/neo4j_archive/`) are kept for a documented retention period.
- The erasure log is a JSON-lines file at `PERSON_ERASURE_LOG_PATH` (default `instance/person_erasure_log.jsonl`), outside the database, so restoring a backup does not roll it back.
  It is appended to by the `PersonErased` event handler after an erasure is committed, so every logged erasure happened.
- `scripts/backup.sh` (cron on the web server) writes timestamped dumps. `scripts/archive_sync.sh` (cron on the archive server) copies new dumps and the erasure log.
  The log is copied with `rsync --append-verify`, so a truncated log on the web server never shortens the archived copy. Run it at least as often as dumps are made.
- `scripts/restore.sh` loads a dump and then runs `scripts/apply_person_erasures.py`, which applies the whole log again. Replaying is idempotent.
- Personal data is not written to application logs. Log ids and actions, not mutation payloads.

## 6. Linking a User to a Person (claiming)

Two routes, both ending in a confirmed `IS_PERSON` link:

1. **Invitation.** An invitation can name a `person_id`. Registering with `linkPerson` links it, because the invitation token and email verification prove identity.
   The link is made with the inviter's authority, which is checked again: they must still administer a team controlling the Person. The user can register without linking.
2. **Request and approve.** A registered user asks to claim a Person by id (`peopleRequestClaim`), even one they can only see as an id; the request reveals nothing.
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
  They can offer affiliations, with an access level, to teams they administer, and a Person controlled by a team they administer.
- **The invitation email** links to `/register?token=…`, with the token also attached as JSON. The token is signed and names the invitation.
  `accountsInvitation(token)` shows what the invitation offers, without login, for the registration form.
- **Registering.** Except for the first account, registration requires the token, and the email address must be the one invited; email verification then proves ownership.
  The user chooses which offered affiliations to accept (`acceptTeamIds`); others are declined. Accepted affiliations are authorised, provided the inviter still administers the team.
  The offered Person is linked only when the user confirms, see claiming (step 9).
- **Expiry.** `INVITATION_EXPIRY_DAYS` (default 30). The inviter can resend, which extends the expiry with a new token, or cancel.
  Expired invitations are ignored, and deleted by `/retention/run`, which the retention cron job already calls.

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

Requirements:
- ORCID **Public API** credentials (free; membership is not needed for verifying an iD). Develop against `sandbox.orcid.org`.
- Config in `instance/*.env`: `ORCID_CLIENT_ID`, `ORCID_CLIENT_SECRET`, `ORCID_BASE_URL`, and the registered HTTPS redirect address.
- `GET /orcid/link` (signed-in users): stores a random `state` in Redis with a short expiry and redirects to ORCID with `scope=/authenticate`.
- `GET /orcid/callback`: checks `state`, exchanges the code with ORCID using `httpx`, stores the returned iD on the user's Person, and handles the user cancelling.
- Only the iD is stored. ORCID's access token is not kept.
- A Neo4j uniqueness constraint: one Person per iD.
- Front end: a "Connect your ORCID iD" button following ORCID's brand guidelines, showing the iD as its full `https://orcid.org/…` address.

This links an ORCID iD to an existing account. Signing in to BreedGraph with ORCID is a separate, later decision.

Everything else (other users' visibility, write access) follows the normal access controls.
The subject may lower the release level, but cannot hide the record from the teams that control it. Erasure is available if they want more.

### Deleting an account

The user is asked whether to erase their Person record as well. Erasure is the default. Either way the link is removed.
Accounts cannot be deleted yet (verified accounts are protected); this applies when account deletion is added.

## 7. Decisions

| Question | Decision |
|---|---|
| Data controllers | The legal entity declared on the root of the organisation containing the record's write team (see §2). One legal entity per organisation. |
| Agreement | Accepted when an organisation root is created or a team is moved to become a root. No separate operator approval. |
| Declaring a legal entity | Optional for an organisation, required to create a Person. Can be declared after the organisation is created. |
| Changing the data controller | Through the general control transfer mechanism (`control-transfer.md`), with the receiving organisation required to have a declared legal entity (§2). |
| ORCID | Set only by the linked User through ORCID sign-in. Not recorded for unlinked Persons. |
| Public attribution | Follows the existing release pattern. Admins of the controlling team decide, up to public release. |
| User and Person names | The Person keeps its own `name`, so people choose how they are credited, separate from their account name. |
| User without a Person | Allowed. A Person is created only when someone is credited or named as a contact. |
| Retention of unlinked Persons | Kept as long as the data they are attached to, as stated in the privacy notice. |

## 8. Open questions

None for Person. Open questions on control transfer are in `control-transfer.md` §6.

## 9. Implementation plan

0. **Organisation legal entity.** Done: declarations on roots with history, terms acceptance when creating a root or later, and GraphQL (`Team.legalEntity`, `organisationsDeclareLegalEntity`, `organisationsDataProcessingTerms`).
   The check that the write team's organisation has a legal entity is added with Person (`Organisation.legal_entity`).
   Builds on the control transfer mechanism (`control-transfer.md`), which is implemented first. The Person rule (§2) is added to its entity-specific rules.
1. **Domain.** Done: `PersonInput` requires a name and the informed attestation; `PersonStored` adds `orcid`, `user`, provenance and `erased_at`, `redacted()` gives readers and the linked user the full record and other registered users the ID only, and `erase()` clears identifying data for admins of the controlling teams or the linked user. `LawfulBasis` enumerates the bases.
2. **Commands.** Done: `CreatePerson`, `UpdatePerson`, `ErasePerson`, replacing `DeletePerson`.
3. **Cypher and repository.** Done: queries rewritten for the reduced model, fixing the wrong `teams` match, the role and title labels (both removed), the unescaped name search, and the error on a missing ID.
   Persons cannot be removed. `ControlledRepository._can_change` lets the linked user store changes to their own record, and admins of the controlling teams store an erasure, besides curators.
4. **Handlers.** Done: creating requires the write team's organisation to have a declared legal entity and the referenced teams to exist; updating an erased Person is refused, and the linked user can change only the name; erasing raises `PersonErased`, which is written to the erasure log. Replay script and backup scripts as in §5.
   Person rules for control transfers: the receiving organisation must have a declared legal entity, and shared control stays within one organisation.
5. **GraphQL.** Done: `Person` type with `restricted` (id only) and `erased` flags, queries `people(name)`, `peoplePeople(ids)` and `peoplePerson(id)`, mutations `peopleCreatePerson`, `peopleUpdatePerson` and `peopleErasePerson`.
   `update_people_map` loads Persons by id into the request context; lookups by id return the id-only form to registered users without read access.
   Mutation resolvers log IDs and actions only.
6. **References to Person.** Done: `contributors` and `contacts` resolve through `people_map`; ontology and germplasm `authors`, and the `Role` and `Title` ontology entries, are removed.
   Contacts as described in §4, with the email endpoint, follow claiming (step 9).
7. **Logging.** Done: the message bus logs commands and events as their name and ID fields (`service_layer/log_safety.py`); validation errors are logged without input values;
   the auth token and request context, user records, account names, emails and login usernames are no longer logged at debug level.
   `LOG_LEVEL` defaults to `INFO` unless `ENVIRONMENT=development`, as library debug logs (e.g. Neo4j query parameters) may contain personal data.
   Usernames of locked-out login attempts are still logged as warnings, for security monitoring; the privacy notice should say so.
8. **Invitations.** Done, on the `invitations` branch: invitations replace allowed emails, which are removed with their `Email` nodes and `ALLOWED_REGISTRATION` links.
   Existing data is not migrated; the development database is flushed.
9. **Claiming and subject rights.** Done: linking through invitations and through requests approved by admins, unlinking, and the linked user's rights from step 1.
   Person changes are stored field by field, so changes stored from the id-only form, such as a request, do not overwrite the record.
   Still to do: 9b, contacts and messaging (§4); and the account-deletion option, once account deletion exists.
10. **ORCID linking.** Routes, config and constraint from §6.
11. **Privacy notice and data processing terms.** Draft text describing what is stored, why, retention and erasure, for the DPO to finalise.

Tests accompany each step: repository, handlers, then GraphQL end-to-end covering each viewer type in §3 and erasure.
