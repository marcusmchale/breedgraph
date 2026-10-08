# Control transfer: design note

Status: **draft for review**.
This note describes how control of a controlled entity moves from one team to another.
It applies to every controlled entity. Person adds one extra rule (§5); see `person.md`.

## 1. Current behaviour

- Control teams are set once, when an entity is created.
  The write team is used if one is given; otherwise **all** of the user's write teams, which may be in several organisations.
- After creation, `set_controls` keeps only teams that already control the entity (`cypher/query_builders/controls.py`).
  The only change possible is the release level (`SetRelease`).
- Each change adds a `Control` node with `user`, `release`, `time` and `sequence`, so control history is kept.
- Team structure can change (the repository has `split`, and the team tree supports adding and removing links), which moves every entity controlled by the moved teams into another organisation without any check.

## 2. Principles

- **Control moves only with the agreement of both sides.**
  The side giving up control offers, and the side taking it accepts.
- **The unit of transfer is an aggregate.**
  All controlled models in the aggregate move together, e.g. a Program with its Trials and Studies.
  Partial transfers would leave an aggregate split between teams.
- **History is kept.** Old controls are ended, not deleted, and each transfer is recorded.

## 3. Explicit transfer

```
ControlTransfer
  id
  entities            # aggregate roots: (label, id) pairs
  from_teams[]        # control teams being replaced
  to_teams[]          # control teams being added
  release             # release level after transfer
  offered_by, offered_at
  accepted_by?, accepted_at?
  rejected_by?, rejected_at?
  cancelled_by?, cancelled_at?
```

1. **Offer.** An admin of every team in `from_teams` (directly or inherited) offers the entities.
   Controls do not change yet.
2. **Accept.** An admin of every team in `to_teams` accepts.
   In one transaction: checks are repeated, new controls are created for `to_teams`, controls for `from_teams` are ended, and a write is recorded.
3. **Reject or cancel.** Nothing changes. The offer is kept as a record.

Checks at offer and at acceptance:
- The entities still exist and are still controlled by `from_teams`.
- Entity-specific rules hold (§5).

If the offering user is also an admin of every team in `to_teams`, acceptance happens immediately as part of the offer, as affiliation requests already do for admins.
The record shows the same user and time for offer and acceptance.

Offers do not expire. They stay pending until accepted, rejected or cancelled by the offering side.

## 4. Team structure changes

A change to the team tree that would put entities under a different organisation is a transfer of everything controlled by the moved teams.

| Change | Offered by | Accepted by |
|---|---|---|
| Move a team within its organisation | No transfer | |
| Split: a team becomes the root of a new organisation | An admin of the current organisation's root | An admin of the team being split off |
| Merge: a root becomes a child of a team in another organisation | An admin of the merging root | An admin of the destination organisation's root |
| Move a team to another organisation | An admin of the current organisation's root | An admin of the destination organisation's root |
| Delete a team that controls entities | Refused until its entities are transferred or removed | |

The structure change is held as a pending change, using the same offer and accept steps as §3, and applied on acceptance together with the moved entities.
A team becoming a root triggers the legal entity declaration described in `person.md` §2, if the new organisation will control Persons.

## 5. Entity-specific rules

Rules are checked at offer and at acceptance. Initially:

| Entity | Rule |
|---|---|
| Person | All control teams must be in one organisation, and that organisation must have a declared legal entity. A transfer to another organisation changes the data controller. |
| Others | None. Control teams may span organisations. |

## 6. Decisions

| Question | Decision |
|---|---|
| Transfers within an organisation | Same offer and accept steps as between organisations. |
| Admin on both sides | Acceptance happens with the offer, as for affiliation requests (§3). |
| Shared control | Adding control teams without removing any is a transfer with `from_teams` kept, accepted by the added teams. |
| Offer expiry | None. Offers stay pending until accepted, rejected or cancelled. |
| Notifications | A `ControlTransferOffered` event emails the admins of `to_teams`, following `AffiliationRequested` (`handlers/events/accounts.py`, `AffiliationRequestedMessage`). |
| Write team on creation | **Required for every controlled entity.** Creating a controlled entity without an explicit write team is refused, so entities are never controlled by all of a user's write teams by default. The user's `default_write_team` is for the front end to preselect, not a server-side fallback. |

## 7. Implementation plan

0. **Require a write team.** Refuse creation of controlled entities without an explicit write team (`repositories/controlled.py`, `_create` and added models in `_update`).
   Make `controlTeamId` required on create mutations, and update tests and scenario builders that create controlled entities without one.
1. **Ending controls.** Mark a `Control` as ended instead of deleting it, and make access checks use only current controls.
2. **Domain.** `ControlTransfer` model, commands `OfferControlTransfer`, `AcceptControlTransfer`, `RejectControlTransfer`, `CancelControlTransfer`, and the `ControlTransferOffered` event.
3. **Persistence.** Repository and Cypher for transfers. Transactional apply on acceptance.
4. **Rules.** A hook for entity-specific checks (§5). The Person rule is added with Person.
5. **Team structure.** Pending structure changes for split, merge and move. Refuse deletion of teams that control entities.
6. **GraphQL.** Transfer queries (offers to my teams, offers from my teams) and mutations.
7. **Tests.** Offer and accept flows, immediate acceptance for admins on both sides, authorisation on each side, cancellation, shared control, team structure changes.
