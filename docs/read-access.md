# Read access: design note

Status: **agreed 2026-10-15**.
This note says what a user sees of controlled entities they cannot read, so that every read follows one rule.

## 1. Who can read what

A controlled entity is readable by a user when any of these holds:

- it has no current controls;
- a team in the user's read teams controls it;
- the least release of its current controls is at least the minimum release: `REGISTERED` for a signed-in user,
  `PUBLIC` for an anonymous one.

The check is written once, in `cypher/query_builders/access.py` (`visible` as a call, `readable` as a predicate
usable inside quantified path patterns), and runs in the Cypher of each view. No readable flag is returned to Python.

The views' queries are composed by query builders (`cypher/query_builders/`) so that this check is not copied into
each query: a copied check in the dataset summaries once used Cypher's aggregate `min()` on a list and hid every
released dataset. Composing queries is safe under one rule: **a builder interpolates only code constants** (variable
names, labels from enums, relationship types, field names checked against a fixed set) **and other builders, and
every value is a `$parameter`.** Each builder then gives the same text on every call, so Neo4j caches its plan, and no
request can change a query's text. `tests/breedgraph/integration/test_query_builders_compile.py` plans every builder's
output with `EXPLAIN`, so a composition error fails a test rather than a request.

## 2. The policy

> Releasing an entity releases what it holds. Anything it points to that you can't read shows as a placeholder: you
> see that it exists and its id, nothing more. Inside a tree you can't fully read, hidden levels are skipped, and you
> see the readable parts joined to their nearest readable ancestor. A hidden level is shown as a placeholder only where
> the tree's shape requires it, such as a trial between a program and a study.

In detail:

1. **A readable entity is returned in full**, including the parts of its aggregate that have no controls of their own
   (a dataset's records, a study's groupings).
2. **References across aggregates give placeholders.** When a readable entity refers to an entity in another
   aggregate that the user cannot read, the reference is kept and the target is a placeholder: its id and the name
   `REDACTED`, with empty lists and no other fields. Examples: a record's unit, a unit position's layout, a hidden
   entity asked for directly by id. References to teams are the exception (rule 7).
3. **Within an aggregate, hidden members are skipped.** A tree (a block of units, a region of locations, an
   arrangement of layouts) is shown with its hidden members left out and their readable descendants joined to the
   nearest readable ancestor. Nothing about the hidden members is shown: not their number, nor how the readable
   members were grouped under them.
4. **Except where the shape requires a placeholder.** A hidden member is kept as a placeholder when its readable
   members cannot be reached otherwise:
   - fixed depth: a hidden trial between a readable program and study, a hidden program above a readable trial;
   - a hidden root holding readable members (a block root, a region root), so the tree has a root to hang from.
5. **Searches leave hidden entities out.** Listing by a filter (datasets by study or concept, programs, units by
   subject) returns only readable entities, and placeholders only where rule 4 needs them. A search is not a
   reference, so it gives no placeholders for what it found hidden.
6. **Counts follow what is released.** A count of things a readable entity holds counts them all (a released dataset's
   records); a count over a tree counts what rules 2 to 4 would show.
7. **A reference to a team resolves to the nearest team you can see.** A controlling team hidden from the user is
   shown as the nearest team they can see that includes it, at furthest its organisation's root, which is never
   hidden. This is a stand-in rather than a placeholder: its purpose is that a user can always follow a reference to
   a responsible party and ask there for an affiliation. Stand-ins are marked as such (`Controller.standInTeams`,
   `Control.teamHidden`), never mixed with the controlling teams the user can see (`Controller.teams`), so a reader
   can tell "Galway controls this" from "a team within Galway that you can't see controls this". Because a
   stand-in's id is not the controlling team's, access is never decided by comparing team ids on the client: the
   server answers it (`Controller.access`) from the user's affiliations.
8. **Write paths are separate.** Write handlers and integrity checks still load whole aggregates through the
   repositories, where redaction keeps hidden members present. Making them independent of redaction is open.

## 3. Datasets under this policy

A dataset's records belong to the dataset aggregate and have no controls of their own, so a released dataset's
records are all readable. Each record's unit is a reference into a block, another aggregate, so a hidden unit is a
placeholder (rule 2). Releasing a dataset therefore publishes its values and the ids of the units they are for, but
not those units' names, subjects, germplasm, positions or how they are grouped in their blocks.

- `datasets(ids)`: readable datasets in full; hidden ones asked for by id as placeholders (id, no concept, no counts).
- `datasets(studyIds, conceptIds)`: readable datasets only (rule 5).
- `Dataset.records`, `recordCount`, `datasetsSummaries` counts: every record of a readable dataset; units as
  placeholders where hidden.
- `datasetsUnits`, the units the records are for as a tree from their blocks: each recorded unit as itself or a
  placeholder (rule 2), joined to its nearest readable ancestor, hidden ancestors skipped (rule 3). A recorded unit
  with no readable ancestor is a root itself; no hidden root is kept for it, since it is reachable without one.
  Counts are of the recorded units and records below each shown unit.
- `datasetsUnitsBySubject`: readable recorded units by subject, and the hidden ones as one group without a subject
  (a placeholder has none).

## 4. Status

Reads of the domains below that follow this note are open to anonymous users (no `require_authentication`), who
see what is released to the public; writes, and every other domain, still need an account. The ontology's reads are
open too, as it is not controlled by teams, but anonymous users get the PUBLISHED and REFERENTIAL views only: the
EDITORIAL view, with drafts, needs an account.

| Domain | Follows this note |
|---|---|
| Programs (`views.programs`) | yes |
| Regions, arrangements (`views.regions`, `views.arrangements`) | yes |
| Blocks (`views.blocks`) | yes |
| Datasets (`views.datasets`, `query_builders/datasets.py`) | yes |
| People, accounts, controls, references, ontology, germplasm | not yet reviewed |
