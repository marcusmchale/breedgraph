# Control transfer: design note

Status: **draft for review**.
This note describes how control of a controlled entity moves from one team to another.
It applies to every controlled entity. Person adds one extra rule (§5); see `person.md`.

## 1. Current behaviour

- Control teams are set once, when an entity is created.
  The write team is used if one is given; otherwise **all** of the user's write teams, which may be in several team trees.
- After creation, `set_controls` keeps only teams that already control the entity (`cypher/query_builders/controls.py`).
  The only change possible is the release level (`SetRelease`).
- Each change adds a `Control` node with `user`, `release`, `time` and `sequence`, so control history is kept.
- Team structure can change (the repository has `split`, and the team tree supports adding and removing links), which moves every entity controlled by the moved teams into another team tree without any check.

## 2. Principles

- **Control moves only with the agreement of both sides.**
  The side giving up control offers, and the side taking it accepts.
- **The unit of transfer is a controlled model, not an aggregate.**
  Models within an aggregate have their own controls, e.g. a Trial may be controlled by a different team from its Program.
  Transferring a Program moves control of the Program only; its Trials and Studies are managed independently.
  Each is edited or removed with curate access to it alone, and adding a Trial or Study needs curate access to the
  Program or Trial it is added to. Writes are stamped on the models changed.
  So a Study given to another team is that team's to edit and remove, and no longer the Trial team's.
  To move several models together, list each of them in one transfer.
- **Only the offering teams' control moves.**
  Other teams controlling the same model keep their control.
- **History is kept.** Old controls are ended, not deleted, and each transfer is recorded.

## 3. Explicit transfer

```
ControlTransfer
  id
  entities            # controlled models: (label, id) pairs
  from_teams[]        # current control teams giving up control
  keep_from_teams     # true for shared control: from_teams keep control as well
  recipient_team      # chosen by the offering side, often a team tree root
  to_teams[]?         # chosen by the receiving side on acceptance
  release?            # chosen by the receiving side on acceptance
  offered_by, offered_at
  accepted_by?, accepted_at?
  rejected_by?, rejected_at?
  cancelled_by?, cancelled_at?
```

1. **Offer.** An admin of every team in `from_teams` (directly or inherited) offers the entities to one `recipient_team`.
   The offering side must be able to see the recipient team: the root of a team tree, which every signed-in user
   sees, or one of their own teams. An offer to a team hidden from them is refused as not found, so hidden team ids
   can't be probed nor their admins sent offers.
   Controls do not change yet.
2. **Accept.** An admin of `recipient_team` (directly or inherited) accepts, and chooses:
   - `to_teams`: `recipient_team` or teams below it in the tree. The accepting user must be an admin of each, directly or through heritable admin affiliations.
   - `release`: the release level for the new controls. Defaults to private.

   In one transaction: checks are repeated, new controls are created for `to_teams`, controls for `from_teams` are ended unless `keep_from_teams`, and a write is recorded.
3. **Reject or cancel.** An admin of `recipient_team` rejects; an admin of `from_teams` cancels. Nothing changes. The offer is kept as a record.

Checks at offer and at acceptance:
- The entities still exist and every team in `from_teams` controls each of them.
- Entity-specific rules hold (§5).

Only admins of `recipient_team` can accept. Admins of teams below it see the offer only if they are also admins of `recipient_team`.
If a team tree root receives an offer meant for a child team, a root admin accepts and assigns control to that child team.

If the offering user is also an admin of `recipient_team`, they choose `to_teams` and `release` when offering, and acceptance happens immediately, as affiliation requests already do for admins.
The record shows the same user and time for offer and acceptance.

Offers do not expire. They stay pending until accepted, rejected or cancelled.

### Renouncing control

A team can give up its control of a model without a transfer, when other teams also control it.
An admin of the renouncing team ends its control. Nobody gains control, so no acceptance is needed.
Renouncing is refused if it would leave the model with no control team.

## 4. Team structure changes

Teams cannot yet be moved between parents: `UpdateTeam` changes only names, and the repository's `split` is unused.
When moving teams is added, a change to the team tree that would put entities under a different team tree is a transfer of everything controlled by the moved teams.

| Change | Offered by | Accepted by |
|---|---|---|
| Move a team within its team tree | No transfer | |
| Split: a team becomes the root of a new team tree | An admin of the current team tree's root | An admin of the team being split off |
| Merge: a root becomes a child of a team in another team tree | An admin of the merging root | An admin of the destination team tree's root |
| Move a team to another team tree | An admin of the current team tree's root | An admin of the destination team tree's root |
| Delete a team that controls entities | Refused until its control is transferred or renounced | |

The structure change is held as a pending change, using the same offer and accept steps as §3, and applied on acceptance together with the moved entities.

### Deleting a team

A team that currently controls entities cannot be deleted. Once it controls none, deleting it marks it as deleted rather than removing it, so the history of its controls is kept:
- The node's `Team` label is replaced by `DeletedTeam`, so it is excluded from every query that matches `Team`.
- Its link to its parent is removed and the parent's ID is kept as `parent`, with `deleted_at` and `deleted_by`.
- Affiliations to the team are removed, and it is cleared as any user's default write team.
- Its `Control` nodes, all ended, stay attached.
- Pending transfers to or from the team are cancelled, recorded as cancelled by the user deleting it.

## 5. Entity-specific rules

| Entity | Rule |
|---|---|
| Person | The release chosen on acceptance can be at most REGISTERED, as for every Person (`person.md` §3). Control teams may span team trees: the University holds every Person whichever teams control it (`person.md` §2), so a transfer changes access, not the data controller. |
| Reference | The release chosen on acceptance can't be below that of what cites it (`contributions.md` §6), and a study's licence can't end up released less widely than the study or its datasets. |
| Study, Dataset | A transfer or renouncing control can't leave a study, or a dataset of it, released more widely than the study's licence (`read-access.md` rule 10). The release that results counts: the least of the controls that remain. |
| Others | None. Control teams may span team trees. |

Until 2026-10-19, Persons also had to stay within one team tree whose root had declared a legal entity, its data
controller; that rule went with the per-organisation model.

## 6. Decisions

| Question | Decision |
|---|---|
| Transfers within a team tree | Same offer and accept steps as between team trees. |
| Admin on both sides | Acceptance happens with the offer, as for affiliation requests (§3). |
| Shared control | Adding control teams without removing any is a transfer with `keep_from_teams`. |
| Receiving side | Offers go to one recipient team. Only its admins accept, choosing `to_teams` from the recipient team and the teams below it, and the release level. |
| Offer expiry | None. Offers stay pending until accepted, rejected or cancelled. |
| Notifications | A `ControlTransferOffered` event emails the admins of `recipient_team`, following `AffiliationRequested` (`handlers/events/accounts.py`, `AffiliationRequestedMessage`). |
| Write team on creation | **Required for every controlled entity.** Creating a controlled entity without an explicit write team is refused, so entities are never controlled by all of a user's write teams by default. The user's `default_write_team` is for the front end to preselect, not a server-side fallback. |

## 7. Implementation plan

0. **Require a write team.** Refuse creation of controlled entities without an explicit write team (`repositories/controlled.py`, `_create` and added models in `_update`).
   Make `controlTeamId` required on create mutations, and update tests and scenario builders that create controlled entities without one.
1. **Adding and ending controls.** `add_controls` and `end_controls` on the access control service.
   Ending appends a `Control` marked `ended`, so history is kept; a team controls an entity while its latest `Control` is not ended.
   Every query that reads controls ignores ended ones. At least one control team must remain.
   These are private to the access control service; only transfers and renouncing use them.
2. **Domain.** `ControlTransfer` model, commands `OfferControlTransfer`, `AcceptControlTransfer`, `RejectControlTransfer`, `CancelControlTransfer`, and the `ControlTransferOffered` event.
3. **Service and handlers.** Transfers belong to the access control service, which owns controls, rather than a repository.
   `offer_transfer`, `accept_transfer`, `reject_transfer`, `cancel_transfer`, `renounce_controls`, `get_transfer` and `get_transfers`.
   The service supplies the user's admin teams and the recipient team's sub-tree to the domain model, writes each change directly,
   and applies accepted transfers in the same transaction. Transfers are visible to admins of the recipient team or of a team giving up control.
   Command handlers, and an event handler emailing the recipient team's admins.
4. **Rules.** Done: the release floor and ceiling (`_require_release_floor`, `_require_release_ceiling`) checked on acceptance (§5). The Person team tree rule (`_verify_entity_rules`) was removed on 2026-10-19.
5. **Team structure.** Done: deletion of teams that control entities is refused, and deleted teams are kept as `DeletedTeam`.
   Later, when moving teams is needed: pending structure changes for split, merge and move.
6. **GraphQL.** Queries `controlsTransfers(statuses)` and `controlsTransfer(id)`, for transfers to or from teams the user administers.
   Mutations `controlsOfferTransfer`, `controlsAcceptTransfer`, `controlsRejectTransfer`, `controlsCancelTransfer` and `controlsRenounceControl`.
7. **Tests.** Offer and accept flows, immediate acceptance for admins on both sides, authorisation on each side, cancellation, shared control, team structure changes.
