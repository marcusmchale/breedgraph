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
   `REDACTED`, with empty lists and no other fields. Examples: a record's unit, a unit position's layout, the unit a
   germplasm entry came from, the units a unit is derived from, a record's, study's or ontology entry's reference, a hidden entity asked for directly by
   id. A study's licence is never a placeholder for those who read the study or its datasets by release (rule 10). A query by a list of ids leaves out ids of no entity (one deleted since it was read, say): they are not hidden,
   so there is nothing to stand in for.
   A reference placeholder keeps its type as well (legal, external, file and so on), as GraphQL needs it to choose the
   reference's type. References to teams are the exception (rule 7).
   Readers of a Person by release see its attribution only (docs/person.md §3). Persons are the other exception:
   they are released at most to registered users, and anonymous users get no references to them at all, neither
   contacts nor contributions (`query_builders.access.signed_in_only`), rather than placeholders.
3. **Within an aggregate, hidden members are skipped.** A tree or graph (a unit graph, a location tree, a
   layout tree, a crop's pedigree of germplasm) is shown with its hidden members left out and their
   readable descendants joined to the nearest readable ancestor. Nothing about the hidden members is shown: not their
   number, nor how the readable members were grouped under them. Where joining loses the kind of link, the joined
   link says so (a germplasm relationship through hidden entries is UNKNOWN). What comes down a unit graph passes
   through hidden members that hold none of it: a unit without germplasm takes that of the nearest units above it
   with germplasm (`Unit.inheritedGermplasm`), but a path that reaches a hidden unit with germplasm gives none, since
   that germplasm is not shown and one from further up would be wrong.
   Aggregate here means what is read as one structure, which need not be what is written as one: germplasm entries
   are written one at a time through `GermplasmApplicationService`, as no rule spans a crop's whole pedigree and loading
   it for each edit would be wasted, yet a crop and its connected entries are read as one pedigree.
4. **Except where the shape requires a placeholder.** A hidden member is kept as a placeholder when its readable
   members cannot be reached otherwise:
   - fixed depth: a hidden trial between a readable program and study, a hidden program above a readable trial;
   - a hidden root holding readable members (a unit graph root, a location tree root, a crop), so the tree has a root to hang
     from; a readable entry can then name the hidden root as its parent or source.
5. **Searches leave hidden entities out.** Listing by a filter (datasets by study or concept, programs, units by
   subject) returns only readable entities, and placeholders only where rule 4 needs them. A search is not a
   reference, so it gives no placeholders for what it found hidden. A search from a given entity (what lies below a
   unit or location, by subject or type; the units derived from a unit; the descendants of a germplasm, for analysis grouping; the program or trial
   holding a trial or study) starts only from one the user can read, or from a hidden root rule 4 keeps (and a trial
   holding readable studies); from any other hidden entity it finds nothing, as for a missing id, rather than show
   what lies below or above it. Units by location (the unit graph roots at a location, and its arrivals: the units
   that came there from elsewhere in their unit graphs) are searches from the location, so a location the user cannot
   read gives none; an arrival lists readable units only, judging where their parents were through the units the user
   can read, so a readable unit below a hidden one that came with it is listed in its place. Its count of units
   derived from counts those with a derived unit the user can read.
6. **Counts follow what is released.** A count of things a readable entity holds counts them all (a released dataset's
   records); a count over a tree counts what rules 2 to 4 would show.
7. **A reference to a team resolves to the nearest team you can see.** A controlling team hidden from the user is
   shown as the nearest team they can see that includes it, at furthest its team tree's root, which is never
   hidden. This is a stand-in rather than a placeholder: its purpose is that a user can always follow a reference to
   a responsible party and ask there for an affiliation. A team is always referred to through a `TeamReference`
   (`Controller.teams`, `Control.team`, `Person.teams`): the team and whether it stands in (`standIn`), so a reader can
   tell "Galway controls this" from "a team within Galway that you can't see controls this". The flag belongs to the
   reference, not the team, as the same team can be itself in one place and a stand-in in another. Because a
   stand-in's id is not the controlling team's, access is never decided by comparing team ids on the client: the
   server answers it (`Controller.access`) from the user's affiliations.
   Team references are for signed-in users: anonymous users see no controllers, nor a Person's teams (in its full
   view only), so they meet no teams at all.
8. **An entity's controller follows the entity.** The controller of an entity the user can read is returned in
   full: its controls, writes, and when each was made. For an entity they cannot read it is a placeholder: its release
   level, its controlling teams (stood in for as rule 7 says), and the user's own access, but no writes and no times,
   as the history of hidden data is part of it. Controllers are for signed-in users only, as only they can ask for
   access (`controlsControllers` requires authentication); anonymous users see no controller badges.
9. **Accounts are private; attribution goes through Persons.** An account (User) is shown only to its owner and
   admins of its teams. What an account did, a write or an ontology commit, is attributed to its linked Person
   (`WriteStamp.person`, `OntologyCommit.person`), which follows the people rules: in full, restricted, or none if the
   account has no Person. Teams are not controlled entities, and are for signed-in users: a team is seen by those
   affiliated with it, and a team tree's root by every signed-in user, so they can ask to join it, offer it
   transfers and follow stand-ins to it. Anonymous users see no teams (the team queries need an account), so the
   organisations using BreedGraph are not listed publicly. Hidden teams are skipped within a team tree (rule 3),
   stood in for where referred to (rule 7), and a placeholder when asked for by id (rule 2).
10. **Write paths are separate: load whole, authorise explicitly, redact only on read.** Repositories return whole
   aggregates, team trees included, so write handlers and integrity checks see members the writer cannot read:
   deleting a location with hidden children, or a location tree, layout tree or unit graph root with hidden members, is refused, and
   removal needs curate access to hidden members too. So is deleting a germplasm entry that units are of, or a unit
   that germplasm came from, whether or not the writer can read them; a unit is checked only once its removal is
   authorised, so only its curators learn of germplasm from it. A hidden aggregate still cannot be found by a filter other than
   its id. Where redaction used to hide a member from the writer, one rule now applies: **you can only link to what
   you can read.** Each added or removed edge in a rooted aggregate (location trees, layout trees, unit graphs) needs read access
   to both stored ends, a new member needs read access to its parent, and attaching a merged unit graph's root needs curate
   access to it, as moving a member does (`ControlledRepository._check_links`). In a program, whose trials and studies
   have controls of their own, editing or removing one needs curate access to it alone, and adding a trial or study
   needs it to the program or trial it is added to (`control-transfer.md` §2). Links the repositories do not see are
   checked in the handlers (`AccessControlService.require_access`): a unit's position to its location and layout, a
   unit to its germplasm, a germplasm entry to its origin location and the unit it came from, a layout to its location, a dataset to its study, a record to its unit (created, added or moved), splitting a unit graph (curate on the unit, read on its parents),
   and citing a reference (`AccessControlService.require_read`): references of datasets and their records, of programs,
   trials, studies and germplasm entries, a study's licence, and the references, licence and copyright of the ontology.
   Only references added are checked, so an entry can still be edited while it cites one the editor cannot read.
   In turn, a reference's release cannot be lowered, by setting it or by a control transfer, below the release of what cites it
   (the ontology counts as public, a record counts as its dataset), so a citation is never hidden later from those who can see
   what cites it (`AccessControlService._require_release_floor`). The ontology is shared, so it cites public references
   only: an entry's references, and a version's licence and copyright, are refused unless public when cited
   (`OntologyService._require_citable_references`), and the floor keeps them public.
   A study's licence is held to more: **it is a legal reference released at least as widely as the study, every
   dataset of the study, and every file its datasets or their records cite**, so whoever reads them by release can read
   the terms they are under, not a placeholder (rule 2), and accept them before downloading a file that holds the
   study's data (docs/licences.md §5). Those who read them through a controlling team make their own agreements, so a
   private study can have a licence private to another team. Giving a study a licence, creating a dataset or moving
   one to another study, citing a file from a dataset or its records, setting a release, a control transfer and
   renouncing control are refused if they would leave a study, one of its datasets, or a file they cite, released more
   widely than its licence. The rule spans several aggregates and every controlling team, so it is checked as the unit
   of work commits, on the releases that result, over the studies, datasets and references the transaction touched or
   newly cited (`AccessControlService.require_released_licences`); the refusal rolls the transaction back. It names
   the licence, the release of the data and a file cited, never a study or dataset. `scripts/check_study_licences.py`
   reports studies that break it, from before it or written by other means.
   Changing or removing a controlled model needs curate access, which includes read. The few reads that still use a
   repository redact explicitly: team trees with `TeamTree.redacted` (the teams map, and the teams a user may
   give a Person), analysis contexts with `ControlledRepository.redacted`, and a request for an affiliation is refused
   for a team the user cannot see.
   Units' positions are written outside the unit graph aggregate (`application.unit_positions`), many units in one
   transaction, as germplasm entries are written outside a pedigree: changing them needs curate access to every unit,
   all or none (those refused are named; those the user cannot read are reported as not found, by id), and read access
   to a new location and layout. Selected by arrival, a write takes only the units the user can read, so hidden units
   stay where they are.

## 3. Datasets under this policy

A dataset's records belong to the dataset aggregate and have no controls of their own, so a released dataset's
records are all readable. Each record's unit is a reference into a unit graph, another aggregate, so a hidden unit is a
placeholder (rule 2). Releasing a dataset therefore publishes its values and the ids of the units they are for, but
not those units' names, subjects, germplasm, positions or how they are grouped in their unit graphs.

- `datasets(ids)`: readable datasets in full; hidden ones asked for by id as placeholders (id, no concept, no counts).
- `datasets(studyIds, conceptIds)`: readable datasets only (rule 5).
- `Dataset.records`, `recordCount`, `datasetsSummaries` counts: every record of a readable dataset; units as
  placeholders where hidden.
- `datasetsUnits`, the units the records are for as a tree from their unit graphs: each recorded unit as itself or a
  placeholder (rule 2), joined to its nearest readable ancestor, hidden ancestors skipped (rule 3). A recorded unit
  with no readable ancestor is a root itself; no hidden root is kept for it, since it is reachable without one.
  Counts are of the recorded units and records below each shown unit.
- `datasetsUnitsBySubject`: readable recorded units by subject, and the hidden ones as one group without a subject
  (a placeholder has none).
- Analysis: every record of a readable dataset is analysed. A record on a hidden unit has that unit as a placeholder
  context, hung from its nearest readable ancestors (for unit grouping and the factors describing it), without its
  germplasm or positions, so it is not assigned to a germplasm or position group. A readable unit's germplasm is its
  own or the one it inherits, as rule 3 gives it, so a unit below a hidden one with germplasm is unassigned too.
  Position grouping places a readable unit by its own positions or those of the units above it, in the same way:
  a placement stops at a hidden unit with positions, and at a position at a location or in a layout the user cannot
  read. Hidden locations' types and hidden layouts' axes are not matched.
  Germplasm grouping takes the readable descendants of a selected germplasm, which must be readable or a crop.

## 4. Status

Reads of the domains below that follow this note are open to anonymous users (no `require_authentication`), who
see what is released to the public, except people and team trees, as noted; writes, and every other domain, still
need an account. The ontology's reads are
open too, as it is not controlled by teams, but anonymous users get the PUBLISHED and REFERENTIAL views only: the
EDITORIAL view, with drafts, needs an account.

| Domain | Follows this note |
|---|---|
| Programs (`views.programs`) | yes |
| Location trees, layout trees (`views.location_trees`, `views.layout_trees`) | yes |
| Units (`views.units`) | yes |
| Datasets (`views.datasets`, `query_builders/datasets.py`) | yes |
| References (`views.references`, `query_builders/references.py`) | yes; a file downloads, and an archived one is retrieved, for anyone who can read its reference |
| Germplasm (`views.germplasm`, `query_builders/germplasm.py`) | yes |
| People (`views.people`, `query_builders/people.py`) | yes, in three views (docs/person.md §3), for signed-in users only: Persons are released at most to registered users, anonymous users get no contacts or contributions, and listing and looking up Persons needs an account |
| Controls (`views.controls`, `query_builders/controls.read_controllers`) | yes; signed-in users only, transfers stay admin-only |
| Accounts and team trees | yes; team trees are read through the repository and redacted explicitly in Python (small, and already following the note), and need an account |
