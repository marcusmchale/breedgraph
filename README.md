# BreedGraph API
A package to manage data in breeding projects by aggregation into a knowledge graph.

## Background and design
BreedGraph was developed with the experience of developing and using the [breedcafs database tools](https://github.com/marcusmchale/breedcafs).
The largely monolithic design of this tool made it difficult to adapt to new situations. 
So, in BreedGraph we have sought to separate concerns, in particular by applying [domain](#domain) driven design
to better isolate domain logic from other concerns.

BreedGraph currently relies on the Neo4j graph database management system (DBMS) for persistence, 
with transactions and the unit-of-work pattern ensuring ACID compliance
(Atomicity, Consistency, Isolation, and Durability).
However, all interactions with this DBMS are contained within a repository layer,
providing the opportunity to adapt to alternative database technologies in the future.
Repositories retrieve and compose domain model objects with change tracking using object proxy wrappers.
This isolates the domain from persistence concerns, allows repositories to operate efficiently 
and preserves records for audit purposes. 

Surrounding the inner persistence layer, in an outer-repository layer, 
is a combined group- and role-based [access control](#access-control).
Repositories return whole aggregates, so that writes and their integrity checks see every member;
changes to controlled domain models are checked against the user's access when they are stored.
What users are shown is read through views that check access and redact in the database
([docs/read-access.md](docs/read-access.md)).

This service layer employs a messaging bus with commands to trigger changes and events
to asynchronously issue other responses such as emails (aiosmtplib).
Command and query responsibility segregation (CQRS) is further implemented
with read-only views and an in memory cache (Redis) improving the efficiency of simple queries. 

A graphql entry-point is provided (Ariadne) to access views and issue service commands.
The GraphQL standard is well suited to querying the knowledge graph, 
allowing efficient navigation and complex nested queries that return only the required information.
This can be accessed through in-browser applications like GraphQL playground, 
where documentation is presented to assist in schema interpretation.
This interface will guide front-end development for customised tools in data entry and analysis.   

Refs.  [Architecture patterns with Python](https://www.cosmicpython.com/book/preface.html). 

## Access Control
Most [aggregates](#domain-aggregates) are "controlled", meaning that access is restricted.

To contribute to these aggregates, users must have a WRITE affiliation with a [team](#team).
Access to READ and CURATE these contributions is then controlled 
by users with an ADMIN affiliation to that team.

These ADMIN affiliates set the read RELEASE status to one of three levels:
- PRIVATE models are only accessible to users with a READ affiliation to a controlling team
- REGISTERED models are accessible only to registered users.
- PUBLIC models are accessible to anyone.

Users may request READ/WRITE/CURATE/ADMIN affiliations from a team
which are then approved by ADMIN affiliates for that team. 
CURATE and ADMIN affiliations include READ: authorising either also authorises READ to the same extent,
and READ cannot be removed or revoked while CURATE or ADMIN is authorised (remove those first; removing them
leaves READ in place). Existing deployments can
grant READ to current admins with `scripts/grant_admin_read.py`.
READ/CURATE and ADMIN affiliations may be heritable,
meaning that the same authorisation is applied to all teams in that branch of the [team tree](#team-tree). 

Multiple write affiliations should be discouraged, 
though in these situations the following rules apply:
- The minimum read RELEASE across all controlling teams is obeyed 
  - PRIVATE being the lowest level and PUBLIC being the highest
- ADMIN affiliates from any controlling team may approve affiliation requests.

## Domain aggregates
Models in the domain provide an interface to data 
that reflects the use-cases and intuitions within the domain.
Simple models are grouped according to consistency boundaries into aggregates,
with each aggregate being sourced from and committed back to its own repository. 
The aggregate types in BreedGraph and their constituent parts are defined in this section.

Established API specifications (e.g. BrAPI), ontologies (e.g. Planteome, CropOntology) and standards (e.g. MIAPPE)
all informed domain modeling for BreedGraph.
These were extended and adapted, particularly with the inclusion of a [subject](#subject) concept
and representation of observation units in flexible [unit graphs](#unit-graph) 
to ease modeling of more complex relationships among observation units.
The CropOntology [trait](#trait)/[method](#observationmethod)/[scale](#scale) definition of a [variable](#variable) 
was also adapted to the definition of factors in a [study](#study)
using [datasets](#dataset) for [parameters](#parameter) and [events](#eventtype).

### Ontology
A central feature of BreedGraph is an adaptive ontology, 
or system to define concepts and categories, their properties and relationships.
Entries in the ontology are referenced by other domain models, 
allowing for flexible creation of new types of entry by end-users.

Ontologies are version controlled, with the addition of each new entry
(or substantive change) triggering a fork of a new version.
Similarly, removed entries and relationships are not truly deleted, 
only retired from the current version of the ontology.
This allows for reconstruction of a given ontology version, 
and for evolution of the system of terms 
without losing the context for any established references from outside the ontology.

All entries are stored as nodes in a directed-acyclic graph 
with a label, internal identifier (ID, an integer) and a name, with optional; 
  - abbreviation,
  - synonyms 
  - description
  - [authors](#people), and
  - [references](#reference).
Generic source (parent) and sink (child) relationships to other entries provide an intuitive navigation.
Specific entries then have additional properties, either defining them as belonging to a specific type
or as having a relationship to other ontology entries.
##### Term
Term entries may be used to relate other key terms in the ontology.
Example: "Metabolism" may be a term.
##### Subject
Subject entries describe the [units](#unit) being observed in a study.
These also provide context for the relevance of [traits](#trait) in the ontology.
Examples: "Leaf", "Tree", "Field", "Rhizosphere Soil"
##### Scale
Scale entries describe the measurement unit or classes used in a:
- [variable](#variable) or 
- [factor](#factor) or
Scale entries require a ScaleType, one of:
- date,
- duration,
- numerical,
- nominal,
- ordinal,
- text
For nominal and ordinal types, additional category references may be provided.
Examples:
"Centimeters", "Counts per million", "Micro-Einsteins" are all ScaleType numerical.
##### ScaleCategory
Category entries describe classes for [scale](#scale) entries with type Nominal or Ordinal.
Ordinal scales require an additional "rank" parameter (integer value) for each category.
Examples: "High", "Medium", "Low" with ranks 2, 1 and 0, respectively.
##### ObservationMethod
Observation method entries describe the way a value is determined for [variables](#variable).
Observation method entries require an ObservationMethodType, one of:
- measurement, 
- counting, 
- estimation, 
- computation, 
- prediction, 
- description, 
- classification
Examples: "Distance measurement with calibrated reference", "Short-read sequencing", "Rain Gauge".
##### Trait
Trait entries describe observed properties of a [#subject] (phenotype for a plant subject) 
described by a [variable](#variable).
Examples: "Height", "Gene expression" are traits of a tree subject.
##### Variable
Variable entries link a [trait](#trait), [method](#observationmethod) and [scale](#scale)
to form a single definition for a [dataset](#dataset).
Examples: 
- "Tree height" where trait = "Height", method = "Distance measurement with calibrated reference" and scale = "Centimeters".
- "Normalised Expression" where trait = "Gene expression", method = "Short read sequencing", scale = "Counts per million"
##### ControlMethod
Control method entries describe the way a value is maintained for a [parameter](#parameter).
Examples: "Fluorescent Lighting", "Fertilizer application".
##### Condition
Condition entries describe the quantities/qualities that are fixed/controlled 
for a [parameter](#parameter).
Examples: "Light level", "Water availability"
##### Parameter
Parameter entries link a [condition](#condition), [method](#controlmethod) and [scale](#scale)
to form a single entry for a [dataset](#dataset).
Examples:
- "Controlled lighting" where condition = "Light level", method = "Fluorescent lighting", scale = "Micro Einsteins"
- "Controlled water availability" where condition = "Water availability", method = "Controlled water application", scale = "L/m2/day"

Parameters are called factors in the code and the API. Variables and factors differ in what their records mean:
a variable's record is an observation of a unit at a time; a factor's record describes the conditions of a unit,
e.g. a treatment or a stratum. In analysis, factor records describe the observations of variables: they hold for the
unit's descendants (the nearest record applies, and on separate lineages the nearest must agree), and for all time
when they have none (docs/analysis.md §2).
##### Event
Event entries link  variables](#variable) and [factors](#factor).
This is to support the definition of details that may be recorded in association with an event. 
##### LocationType
Location entries describe types of locations within a [location tree](#location-tree).
Examples: "Country", "State", "Field"
##### LayoutType
Layout entries describe types of [layout](#layout) within a [layout tree](#layout-tree).
Examples: "Grid", "Row"
##### Design
Design entries describe statistical designs for a [study](#study) in a [program](#program).
Examples: "Split-plot", "Randomized block"
##### Record Group Type
Record group types describe the codes that group [records](#data-record) within a [study](#study).
A study uses a type through a record grouping, which has a scope (study-wide or dataset-scoped) and an extent.
A code can mean the same on every unit, e.g. a canopy stratum "Lower"; the grouping's extent decides whether analysis
uses that. A type can have a default extent, which a new grouping of it starts with.
With SHARED, records of different units with the same code are one group, a level that can be estimated across units
(e.g. "Batch", "Plate", "Stratum"). With WITHIN_GRAPH, codes are shared in the same way, but only by the units of one
[unit graph](#unit-graph) (e.g. a field and the units in it): the design blocks of a field (e.g. "Block"), whose names recur in
other fields, are one level per field. With WITHIN_UNIT, codes are nested in each record's unit: records of one unit
with the same code at one time, or within the replicate aggregation window, are one reading (e.g. "Replicate",
or "Branch" for the branches of a tree).

Whether to record something as a unit, a code or a factor:
* a [unit](#unit), if it persists or is followed over time, is sampled, has a position, carries its own germplasm,
  or other units hang from it (a tree, a sample sent for analysis);
* a WITHIN_UNIT code, for repeated readings or one-off parts of one unit (replicates, the branches or leaves of a tree
  each measured once);
* a WITHIN_GRAPH code, for a group of units within one unit graph (the design blocks of a field). Where the blocks
  are already units for a reason above (e.g. plots that trees hang from), they need no code: an analysis can take the
  units of their subject as the levels of a record group dimension (docs/analysis.md §3);
* a SHARED code, for a group across unit graphs (a batch, a plate, a session, a canopy stratum);
* a [factor](#factor), for a level the design sets that is to be estimated (a treatment).
##### Role
Role entries describe roles for [people](#people).
Examples: "Post-doctoral researcher", "Principal Investigator"
##### Title
Title entries describe titles for [people](#people).
Examples: "Professor", "Doctor"

### Account
Access to most functions of BreedGraph through the GraphQL API require an account.
The add_email mutation in the GraphQL interface sends an invitation to register a new user. 
There is currently no facility to request an invitation.

### Team tree
A team tree is a tree of [teams](#team) with a single root team.
These form the foundation of [access control](#access-control) logic.
Teams decide who can read and change what they control, Persons included; the University of Galway is the data
controller of all personal data in BreedGraph ([docs/person.md](docs/person.md) §2).

In the GraphQL interface, the teamsCreateTeam mutation will create a team.
If the optional "parent" parameter is not supplied then the created team 
becomes the root of a new team tree. When more teams are required for a team tree, 
this parameter results in the new team being a child of the parent.
The user that creates a team is automatically given a heritable ADMIN affiliation to that team, 
allowing them to approve further affiliations. 

All root teams are visible to all users,
though child teams are visible only to affiliates in that branch.
Other users may request READ,WRITE,ADMIN or CURATE affiliations,
with ADMIN affiliates receiving an email to approve this request. 
Such requests are heritable, such that a user may request an affiliation to the root of a team tree, 
and ADMIN affiliates may approve the affiliation only to a chosen child team.
#### Team
Teams have name and fullname attributes.
### Layout tree
A layout tree is a tree of [layouts](#layout) with a single root.
These are used to describe positions for [units](#unit) within [unit graphs](#unit-graph).
#### Layout
Layouts have attributes for:
  - type, an ID for [layout type](#layouttype) in the ontology
  - location: an ID for a [location](#location) within a [location tree](#location-tree)
  - axes: labels for the axes (a list of strings). 
    - The order of axes must be preserved when describing positions for a [unit](#unit).
  - Optional:
    - name: a string to describe this specific layout

### Unit graph
A unit graph is a directed acyclic graph with a single root, composed of [units](#unit), e.g. a field and the trees
and samples in it. A unit may have several parents, e.g. a sample taken from two trees. Design blocks are not unit
graphs: they are best recorded as WITHIN_GRAPH [record group](#record-group-type) codes.
#### Unit
Units have attributes for:
- subject, an ID for [subject](#subject) in the ontology
- Optional
  - name
  - description
  - germplasm: an ID for a [germplasm entry](#germplasm-entry)
  - positions: a list of [positions](#position)
  - derived from: the units its material came from, each with the stage the material was at when it became this unit,
    and a description (below)

A unit without germplasm of its own takes that of the units above it, so a sample needs none: on each path up its
parents, the first unit with germplasm, and these must agree (a sample pooled from trees of two varieties has none).
A unit's own germplasm overrides what it would take, e.g. a seedling raised from a cross.
Germplasm produced here, e.g. a selection made from a tree, can name the unit it came from (a
[germplasm entry](#germplasm-entry)'s unit); that unit then cannot be deleted.

A unit's parents are its context: it takes their germplasm, it is where they are without a position of its own, their
factor records describe it in analysis, and it shares the WITHIN_GRAPH codes of their unit graph. Material that starts
a context of its own is a new unit **derived from** the units it came from, rather than their child: microcuttings from
a lab that become plantlets in a field, seed that becomes seedlings, a cutting rooted elsewhere. The derived unit is in
a unit graph of its own team's, as its root or under a unit there (e.g. a field-season unit), and nothing comes down a
derivation: its germplasm is its own (deriving the units of an arrival at once copies the germplasm each source has or
takes, where the user can read it, unless another or none is chosen), and analysis doesn't follow it. The derivation is
kept as the unit's history. A unit stays a child where its parent's context describes its observations: a sample sent
for analysis describes its tree. Deriving needs read access to the units derived from, and leaves them as they are, so
a lot can be split, some of it derived at one place and the rest moved on. A unit is not derived from itself, from the
units above or below it in its unit graph, or from a unit derived from it, and a unit with units derived from it cannot
be deleted.

Each unit it is derived from comes with the stage the material was at when it became the unit, a physical form rather
than the genetic relationship [germplasm](#germplasm) describes:
- SEED: seed, or a seed lot;
- SEEDLING: a young plant grown from seed;
- CUTTING: an unrooted vegetative piece, such as a stem or nodal cutting, budwood, a scion or a bud chip;
- ROOTED_CUTTING: a rooted vegetative piece;
- PLANT: an established whole plant, with its approximate stage given in the description;
- IN_VITRO: material in culture, such as an explant, callus, somatic embryos, embryo rescue, anther or microspore
  culture, a micro-graft or a cryopreserved shoot tip;
- PLANTLET: in vitro material acclimatised ex vitro;
- UNKNOWN.

A graft is derived from several units, each at its own stage, e.g. a scion as a CUTTING and its rootstock as a SEEDLING;
how they were joined, intergrafts included, goes in the descriptions. As nothing comes down a derivation, a treatment
in a nursery whose effect is studied in the field is lost to a unit derived from the nursery's: move the unit instead,
or record the factor on the derived unit. And a plant that stays where it is is better kept as one unit across seasons,
with its records grouped by time or record group, than derived anew each season: derive where its context really
changes, such as a new trial, site or team.

A unit can't be deleted while anything else refers to it: records for it, which would be left without a unit (remove
them first), germplasm that came from it, or units derived from it.

Children can be added to many units at once, as for a sampling event: the leaves taken from each tree of a field on
one day. Each is named from a template of its parent's name, its subject and its number among its parent's new
children ("{parent} - {subject} {n}" names the first leaf of Tree 1 "Tree 1 - Leaf 1"). Given the day, each has a
position at its parent's place then, from then (where its parent is, by its own position or the one it takes from the
units above it), which keeps the day it was taken; moving the samples on to a lab later makes them an arrival there.
Without one, they are where their parents are.
##### Position
Positions have attributes for:
- location: an ID for a [location](#location) within a [location tree](#location-tree)
- Optional:
  - start: a start date and time for this position (see [times](#times))
  - layout: an ID for a [layout](#layout) within a [layout tree](#layout-tree)
  - coordinates: a coordinate list that should correspond to the axes in a layout
  - end: an end date and time for this position

A unit graph's root needs a position, so that the graph can be found by its location.
Positions have no identity of their own: a position is found by its value, times compared as entered.

A position holds from the start of its start's period to the end of its end's, a missing start or end leaving it open.
A unit is where its own position at a time puts it, the later-starting one where a move ends one position and starts
another at the same time; without a position of its own then, it is where its parent is. A position that ended with
nothing after it means the unit left, e.g. a sample used up; a unit that comes back is given a position there.
Analyses group records by where their units were in a way of their own: at locations of chosen types and by layout
axes, a sample by its tree where its own position doesn't count (docs/analysis.md §3).

Positions are written apart from the rest of the unit graph, so that a batch of samples moves in one request without
their unit graphs loaded, and an edit of a unit can't undo a move it never saw. A **move** of units to a position from
a start ends each unit's own positions holding then at that start, unless they end by then, and adds the position; it
is refused for a unit with a position from that start or later. A **change** finds one position of each unit by the
values given and replaces those given, e.g. to end an arrival there or correct its start. Either takes the units given,
or an arrival's, and takes their write locks first, so writes to the same units follow one another.

Units that came to a location together from elsewhere in their unit graphs, e.g. samples from the trees of a field
sent to a lab, are an **arrival**: the units, other than roots, with a position at the location from the same start
whose parents were not there then. An arrival is known by its location and start, so it needs no record of its own,
and its units stay in their unit graph, below the units they came from. A unit taken from one already there is not an
arrival; one that comes back later is a new one. An arrival counts its units with units derived from them, and those
pending: still there, with nothing derived from them. With none pending, it is settled: its units were derived from,
moved on or used up.
### Dataset
Datasets are collections of [record](#data-record) for [units](#unit)
They have attributes for:
- term: an ID for [variable](#variable), [parameter](#parameter) or [event](#eventtype) in the ontology
- unit records: a map of [unit](#unit) ID to a list of [records](#data-record).
- contributors: a list of [people](#people) (by ID) that contributed to this dataset
- references: a list of [references](#reference).
  - This should not be used to link supporting data files as there is it does not provide a mapping to units. 
#### Data Record
Data records have attributes for:
- value: a string, integer or float value
- start: the date and time the value for this record is known to be relevant to this unit 
- end: the date and time that the value for this record is no longer known to be relevant to this unit  
- start and end are [times](#times) as entered: either may be missing, standing in for the other
- references: a list of [references](#reference).
  - References may be used to link supporting data files, e.g. library sequencing data
#### Times
The times of records, positions, studies, trials and germplasm are the local wall-clock time at the location, stored at the
precision they were entered to (a year, month, day, hour, minute, ...), without a time zone: a time with an offset is refused.
A time stands for its whole period: as a start, the start of the period, and as an end, the end of it,
so a record ending on 2021-05-03 runs through that day, and a record of 2021 overlaps any window in 2021.
Times the system sets, such as when data was submitted, are timestamps in UTC.
### Germplasm
Germplasm is a directed acyclic graph with a single root node, composed of [germplasm entries](#germplasm-entry).
Relationships among these entries form a "pedigree" of source to sink relationships:
These relationships may be of the following types:
- UNKNOWN: sink entry is derived from source entry, though details of the relationship are not known.
- SEED: sink is derived from seed obtained from source.
- TISSUE: sink is derived from vegetative tissue from source.
- MATERNAL: sink is derived from seed obtained from source in a controlled cross.
- PATERNAL: sink is derived from pollen obtained from source in a controlled cross.

The root node for a germplasm in plant breeding would typically be a crop name, 
e.g. "Coffee" with species being defined as being sourced through UNKNOWN relationships.
This allows the construction of a graph of any broad relationship categories, 
though further details may be specified on the individual entries.
#### Germplasm Entry
Germplasm entries have attributes for:
- origin: an ID for a [location](#location) within a [location tree](#location-tree)
- time: to describe when this germplasm was sourced from origin.
- unit: an ID for the [unit](#unit) it came from, for germplasm produced by the breeding recorded in BreedGraph,
  e.g. the plant a selection was made from, or the seed of a cross; origin and time describe germplasm sourced from
  elsewhere
- reproduction: one of CLONAL, ASEXUAL or APOMIXIS used to describe the maintainence of this germplasm
- methods: a list of [germplasm methods](#germplasmmethod) in the ontology, describing the protocol for the generation of this germplasm
  - e.g. clonal propagation via tissue culture, controlled self-fertilisation, uncontrolled pollination
### People
- This aspect is not fully implemented due to GDPR considerations.

Each person is a singleton aggregate that may be referenced elsewhere as authors, contributors or contacts.
Person has the following attributes:
- name
- Optional
  - fullname
  - email
  - mail
  - phone
  - orcid
  - description
  - user (corresponding to a registered User ID)
  - teams (corresponding to registered teams associated with this person)
  - locations (corresponding to regisered locations associated with this person)
  - roles: references to [roles](#role) in the ontology
  - titles: references to [titles](#title) in the ontology

### Program
A program describes the highest level aggregation of a group of trials and studies 
and would typically represent a funded project, e.g. Bolero
The program has attributes for: 
- name
- fullname
- description
- contacts: a list of [people](#people) (by ID) that are suitable to contact for queries about this program.
- references:  a list of [references](#reference).

Each program contains a collection of [trials](#trial), which is itself a collection of [studies](#study)
#### Trial
Trials are a collection of [studies](#study), with attributes for:
- name
- fullname
- description
- start
- end
- contacts: a list of [people](#people) (by ID) that are suitable to contact for queries about this trial.
- references:  a list of [references](#reference).
##### Study
Studies collect [datasets](#dataset) with attributes for: 
- name
- fullname
- description
- external_id: a permanent external identifier (e.g. UUID)
- practices: from MIAPPE V1.1 (DM-28), a description of the cultural practices associated with the study.
- start
- end
- factors: a list of [dataset](#dataset) IDs, typically corresponding to a [parameter](#parameter) or [event](#eventtype).
- observations: a list of [dataset](#dataset) IDs, typically corresponding to a [variable](#variable).
- design: a reference to the [design](#design) in the ontology
- licence: a legal [reference](#reference) that describes legal terms for usage of datasets (factors/observations) from this experiment, released at least as widely as the study and its datasets
- references: a list of other supporting [references](#reference)
### Location tree
A location tree is a tree of [locations](#location) with a single root, typically a country. 
#### Location
A location has attributes for:
- name
- synonyms
- description
- code (e.g. a country code, zip-code etc.)
- type: a reference to [location type](#locationtype) in the ontology
- address
- coordinates: a list of [GeoCoordinate](#geocoordinate). 
  - When multiple coordinates are supplied these are interpreted to be the boundaries of the location
  - When a single coordinate is supplied this is interpreted to be within the location.
##### GeoCoordinate
Geocoordinates have attributes for:
- latitude: float
- longitude: float 
- Optional:
  - altitude: float
  - uncertainty: float
  - description: a string describing more details about this coordinate.

### Reference
All references may include a description, other reference types have varying attributes.
#### External reference
- url: the URL for the external source
- external id: a string defining an identifier relevant to the external source 
#### External data reference
As for [external reference](#external-reference) but with the addition of:
- data_format: a string defining the data format
- file_format: a string defining the file format
#### File reference
File references are created when a file is submitted with attributes for:
- filename
- UUID: a global unique identifier (UUID4) that may be used to identify this file.
#### Data file reference
As for [file reference](#file-reference) but with the addition of:
- data_format: a string defining the data format
- file_format: a string defining the file format
#### Legal reference
- text: Legal text.


## Setup 

### neo4j
get the key, add the source and apt install

    wget -O - https://debian.neo4j.com/neotechnology.gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/neo4j.gpg
    deb [signed-by=/usr/share/keyrings/neo4j.gpg] https://debian.neo4j.com stable latest
    sudo apt install neo4j

set initial password for neo4j user (only works if run before starting for the first time)

    neo4j-admin dbms set-initial-password <password-here> 

enable systemd to start the neo4j service

    sudo systemctl enable neo4j    
    sudo systemctl start neo4j

#### neo4j offline install
  install java

#### tmp directory 
  neo4j requires an executable tmp directory.
  If the server has noexec on /tmp

    findmnt /tmp

  then create a directory somewhere with executable permissions and make it owned by neo4j user with all permissions.
  
    sudo mkdir -p /var/lib/neo4j/tmp
    sudo chown neo4j:neo4j /var/lib/neo4j/tmp
    sudo chmod 700 /var/lib/neo4j/tmp

  Then add these lines to the neo4j.conf and neo4j-admin.conf in /etc/neo4j/

    server.jvm.additional=-Djansi.tmpdir=/var/lib/neo4j/tmp
    server.jvm.additional=-Djava.io.tmpdir=/var/lib/neo4j/tmp
    server.jvm.additional=-Djna.tmpdir=/var/lib/neo4j/tmp
    

### redis
    sudo apt install redis-server

change /etc/redis/redis.conf "supervised no" to "supervised systemd" to allow systemd to manage startup
restart to load config

    sudo systemctl restart redis.service

### Run with uvicorn
To test with the uvicorn server, go to the root of the project, export the environment variables from the instance directory and run, e.g.

    pip install -e .[server]
    set -a
    . ./instance/breedgraph.env
    . ./instance/private.breedgraph.env
    set +a
    uvicorn src.breedgraph.main:app --log-level debug

./instance/breedgraph.env lists every variable the API reads, with public defaults.
Values in ./instance/private.breedgraph.env override them, and this file is not tracked by git.
If you are cloning this project, create ./instance/private.breedgraph.env
with your own values for secrets, the neo4j connection, mail hosting and log file creation.
Among the secrets, `ACCEPTANCE_SALT` signs the cookies that hold acceptances of the Terms of Use and of study licences
(docs/licences.md §4); the API refuses to start without it. The Terms and the privacy notice the API serves are
`src/breedgraph/legal/terms_of_use.md` and `privacy_notice.md`, unless `TERMS_OF_USE_PATH` or `PRIVACY_NOTICE_PATH`
names another file.


### Nginx
Set nginx's `client_max_body_size` to the largest file users may upload, e.g. `100M`. It is the upload size limit:
the API sets none of its own, but for legal references given as files (`LEGAL_FILE_SIZE_LIMIT`). nginx refuses a larger
request with 413 before it reaches the API, and breedview says the file is larger than the server accepts. breedview
and the API are served from one origin, so the browser lets breedview read the 413; were they served from separate
origins, nginx's error page would need the CORS headers too (`add_header ... always`), or breedview would see only a
failed request.

Serve the map tiles (see Maps) directly from `MAP_TILES_PATH`, beside the front end; nginx answers the range requests
they are read with. `tiles.json` changes as regions are fetched, so browsers check it at each page load:

    location = /tiles/tiles.json {
        alias /opt/breedgraph/instance/map_tiles/tiles.json;
        add_header Cache-Control "no-cache";
    }
    location /tiles/ {
        alias /opt/breedgraph/instance/map_tiles/;
        add_header Cache-Control "public, max-age=86400";
    }

### Maps

Browsers contact no third party for maps: tiles come from our server, and place searches go through the API, which asks
Nominatim (`NOMINATIM_URL`, limited per user by `GEOCODING_RATE_LIMIT_PER_HOUR`).

The tiles are cut from a [Protomaps](https://docs.protomaps.com/basemaps/downloads) build of OpenStreetMap into
`MAP_TILES_PATH`, served at `/tiles` and listed in `tiles.json`. Only the parts needed are downloaded.
- **The world** at low detail, to zoom 8 (about 560 MB), is cut by `scripts/map_tiles.py`.
- **Regions** in full detail, to zoom 15, are fetched by the API in the background (`adapters/pmtiles/map_regions.py`):
  - When a country is added, the whole country is fetched (Ireland 454 MB, Kenya 404 MB).
  - A country larger than `MAP_REGION_MAX_GB` (2) is divided into its states or provinces (ADM1 units), and a section
    is fetched when a location in it is placed on the map. A section over the cap too is fetched by its ADM2 unit
    (a county, say) instead, and one still over the cap fails as too large. Brazil (4.2 GB), France (5.5 GB) and the
    United States (17 GB) are divided.
  - The user who added the country or placed the location is emailed when the fetch starts and when it ends, or that
    the country is divided.
  - Countries are public, and a section shows only that some location lies within it. Sections are found on our
    server, from its copy of the outlines, so no site coordinates leave it.
  - Each region is a file, `regions/<key>.pmtiles`, with a `<key>.json` description, and each country has its extent
    for the map to show it by in `countries/<code>.json`, whether fetched whole or divided. Removing a country deletes
    its files; a section stays until its country is removed.
  - Before a fetch, a dry run gives the region's size. The fetch fails unless the disk has room for it, with 10% of
    its size and 1 GB to spare. Plan for up to `MAP_REGION_MAX_GB` per country added or section placed.
  - Each API process fetches one region at a time. Redis holds a lock per region, who asked, and the regions under way,
    which resume after a restart. Finished regions are known from their files.

`/tiles/tiles.json` (404 until the world file is cut) is what the map reads: `{attribution, updated, layers, countries}`.
Bounds in it are `[[south, west], [north, east]]`.
- The first layer is the world file, `{url, maxZoom, build}`. The others are regions, `{url, name, minZoom, maxZoom,
  bounds}`, each added once complete. Regions share the tiles along their borders, so the map draws them as one layer
  whose source takes each tile from the first region whose zooms and bounds hold it (breedview
  `composables/locations/baseMap.js`). Fetch `tiles.json` without caching, so new regions appear at the next page load.
- `countries` maps each country's code to `{name, bounds}`, the extent to show it by around its main parts (east is
  above 180 for a country across the antimeridian), for every country fetched or divided. Where a country has none,
  `locationsGeocodeCountry(name).bounds` is the fallback.

Country outlines come from [geoBoundaries](https://www.geoboundaries.org) (`GEOBOUNDARIES_URL`; open licences, which
vary by country and are kept beside each file). They are cached in `MAP_BOUNDARIES_PATH`, which is not served, and used
only to cut tiles. Regions are cut from the newest Protomaps build (`PROTOMAPS_BUILDS_URL`) of the same version as the
world file, or from the build `MAP_TILES_BUILD` pins.

The API's server needs the `pmtiles` command from [go-pmtiles](https://github.com/protomaps/go-pmtiles/releases)
(`MAP_PMTILES_COMMAND`), a single program. Without it, or with the setting empty, no regions are fetched and the API
logs a warning at startup. Install it once (`Linux_arm64` on ARM):

    curl -LO https://github.com/protomaps/go-pmtiles/releases/download/v1.31.2/go-pmtiles_1.31.2_Linux_x86_64.tar.gz
    curl -LO https://github.com/protomaps/go-pmtiles/releases/download/v1.31.2/checksums.txt
    sha256sum --check --ignore-missing checksums.txt
    tar xzf go-pmtiles_1.31.2_Linux_x86_64.tar.gz pmtiles
    sudo install pmtiles /usr/local/bin/

Then cut the world file, from the newest build unless `--build` or `MAP_TILES_BUILD` names one:

    set -a; . ./breedgraph.env; set +a
    scripts/map_tiles.py

Run it again now and then to refresh the world file, and then `scripts/map_tiles.py --refresh` to fetch the regions
again from the newest build. `--regions` fetches what the API would for every country and placed location, for a first
setup or after losing the files, and `--dry-run` reports what would be fetched and its size. The script sends no
emails, and shares the API's locks, so both can run at once. Deploying leaves `MAP_TILES_PATH` and
`MAP_BOUNDARIES_PATH` as they are. For development, `--world-maxzoom 6` gives a world file of about 45 MB.



### Notes for developers
  - for testing on community we can only have one active db
  - change the /etc/neo4j/neo4j.conf line to specify which to run, e.g.
    - initial.dbms.default_database=test

## deploy :

### Build a wheelhouse and install from that 

    cd path/to/breedgraph
    python -m build
    python -m pip download --only-binary=:all: --dest dist/wheelhouse_server dist/breedgraph-0.1.0-py3-none-any.whl[server]
    scp -r dist/wheelhouse_server user@server:~/breedgraph_deployment

then on the server, su to the user controlling breedgraph

    cd /opt/breedgraph
    python3 -m venv venv
    . ./venv/bin/activate
    python -m pip install --no-index --find-links wheelhouse_server/ breedgraph[server]
  
to run the scripts

    /opt/breedgraph/venv/bin/activate
    set -a
    . /opt/breedgraph/breedgraph.env
    set +a
    ./setup_initial_data.py

### Encryption key

Database backups and archived files are encrypted with [age](https://age-encryption.org) before they leave the web
server, so the archive server holds only copies it cannot read. The web server keeps the private key, as it decrypts
archived files when users ask for them back, and restores need it too. On the web server, install age and make the key
as the user that runs BreedGraph (here `breedgraph`):

    sudo apt install age
    sudo -u breedgraph age-keygen -o /opt/breedgraph/encryption_key.txt
    sudo -u breedgraph age-keygen -y /opt/breedgraph/encryption_key.txt

`age-keygen` makes the key file readable only by its owner. The last command prints the public key, `age1…`.
Set both in `breedgraph.env`, and restart the API:

    ENCRYPTION_RECIPIENT="age1…"
    ENCRYPTION_IDENTITY_PATH="/opt/breedgraph/encryption_key.txt"

Run `scripts/backup.sh` and `scripts/restore.sh` as that user too. The archive server needs neither age nor the key:
never copy the private key there. In development (`ENVIRONMENT=development`) both settings may be left empty, and
backups and archived files are then not encrypted. Elsewhere `backup.sh` refuses to run without a public key, and the
API refuses to send files to the archive server or take them back.

**Keep copies of the private key**, the `AGE-SECRET-KEY-1…` line in the key file, somewhere safe away from the web
server and the archive server, including a printed copy in a sealed envelope on campus. Without the key no backup or
archived file can be read, so losing the web server without a copy loses them all.

**Check each copy** once it is made, by decrypting a backup with it on a machine with age installed, then deleting the
copied key file:

    age --decrypt --identity copy_of_key.txt <database>-<date>.dump.age > /dev/null && echo "the key works"

**Changing the key.** Make a new key with `age-keygen -o new_key.txt`, add it to the end of the key file
(`cat new_key.txt >> encryption_key.txt`, then delete `new_key.txt`), set `ENCRYPTION_RECIPIENT` to its public key,
restart the API, and replace the copies. age tries every key in the key file, so backups and archived files made with
the old key can still be read. Keep an old key for as long as anything made with it exists: backups are kept for 90
days, but archived files can be kept indefinitely.

### Backups, restores and retention

Neo4j is dumped on the web server, encrypted, and the dumps and the erasure log are copied to an archive server.
The erasure log records erased Persons and deleted accounts outside the database, so a restore can apply them
again ([docs/person.md](docs/person.md) §5). Redis is not backed up: it holds read models, which are rebuilt from
Neo4j, and work in progress (dataset submissions, analysis jobs and their results for `ANALYSIS_RETENTION_DAYS`,
upload progress), which is lost if Redis is.

**Back up** on the web server with `scripts/backup.sh`. It stops Neo4j (the API is unavailable meanwhile),
dumps `DATABASE_NAME` to `NEO4J_ARCHIVE_PATH` as `<database>-<date>.dump.age`, encrypted to `ENCRYPTION_RECIPIENT`
as it is written, and starts Neo4j again. No unencrypted dump is written, and a dump is named `.partial` until complete.
In development without a key it writes an unencrypted `<database>-<date>.dump`, as before.
It uses `sudo` to stop Neo4j and dump as the neo4j user, and writes the encrypted dump as the user running it, who
needs write access to `NEO4J_ARCHIVE_PATH`. It reads its settings from the environment, which cron doesn't load.
For example, in the crontab of the user that runs BreedGraph, allowed those commands, nightly:

    15 2 * * * cd /path/to/breedgraph && set -a && . ./breedgraph.env && set +a && scripts/backup.sh >> /var/log/breedgraph_backup.log 2>&1

Dumps accumulate on the web server; remove old ones there as space requires, once the archive server has them.

**Copy** the dumps and the erasure log to the archive server with `scripts/sync_database_backups.sh`, run from cron
*on the archive server*, at least as often as dumps are made: an erasure is at risk until the log is copied.
Its settings are in `/etc/breedgraph/backup_sync.env` (example: `instance/backup_sync.env`), and it needs ssh key
access to the web server, but never the encryption key. New dumps are copied as they appear, and the log with
`rsync --append-verify`, as it is only ever appended to. `BACKUP_RETENTION_DAYS` removes old dumps there: set it to
90, the period the privacy notice states. The erasure log is never removed, and is not encrypted: it holds only
record and account numbers, and must stay appendable.

    0 * * * * /path/to/breedgraph/scripts/sync_database_backups.sh >> /var/log/breedgraph_backup_sync.log 2>&1

**Restore** on the web server, with the environment loaded, by the dump's file name in `NEO4J_ARCHIVE_PATH`
(copy it back from the archive server first if needed):

    cd /path/to/breedgraph
    set -a; . ./breedgraph.env; set +a
    scripts/restore.sh <database>-20261015-021500.dump.age

An encrypted dump needs the key file `ENCRYPTION_IDENTITY_PATH`, so run it as the key's owner, or, if the web server
was lost, with `ENCRYPTION_IDENTITY_PATH` set to a copy of the key. It decrypts the whole dump first, so a wrong key or
a damaged dump stops it before anything is changed. An unencrypted `.dump`, such as a test database, loads as it is.
It asks for confirmation, stops Neo4j, loads the dump over `DATABASE_NAME`, starts Neo4j, and replays the erasure log
(`scripts/apply_erasures.py`), so Persons erased and accounts deleted since the dump stay that way. Each entry is
applied to its own record only, and the id counters are advanced past the logged ids, so no erased id is given out
again. If the log isn't on the web server, restore it from the archive server and run `scripts/apply_erasures.py <log>`
before the database is used. Then rebuild the read models in Redis from the restored database:

    scripts/load_state_store.py

Uploaded files are not in the dump: they stay in `FILE_STORAGE_PATH`, or in archive storage (the archive worker).
The API encrypts files as it sends them to the archive worker and decrypts them when they come back, with the same
key, so the archive server holds only encrypted copies, while `FILE_STORAGE_PATH` holds files as uploaded. Once a file
is archived, the retention job removes the web server's copy after `LOCAL_STORAGE_DURATION` days, so the archive server
then holds its only copy. The API checks the archive server stored exactly what it sent before marking a file archived.

**Erasure on request.** The University is the data controller, so people without an account linked to their Person
record ask us to erase it. Confirm who is asking, then, with the environment loaded:

    scripts/erase_person.py <person id>

It erases the Person and appends it to the erasure log, as erasures in BreedGraph are, so a restore applies it again.

**Logs** are kept for the periods the privacy notice states: access logs 30 days, the others 90. The application writes
them to `LOG_BASE` without rotating, as several processes write them, so rotate them with logrotate, e.g. in
`/etc/logrotate.d/breedgraph`:

    /var/log/breedgraph/access.log {
        daily
        rotate 30
        copytruncate
        compress
        delaycompress
        missingok
        notifempty
    }
    /var/log/breedgraph/breedgraph.log /var/log/breedgraph/graphql.log /var/log/breedgraph/neo4j.log /var/log/breedgraph/redis.log {
        daily
        rotate 90
        copytruncate
        compress
        delaycompress
        missingok
        notifempty
    }

and keep nginx's access logs no longer than 30 days (`rotate` in `/etc/logrotate.d/nginx`).

**Retention** of files and expired invitations runs through the API, with `scripts/trigger_retention.sh` from cron
on the web server (it loads the env files itself). Each run notes the file references nothing cites (as a licence, a
copyright or a reference of anything), and removes those it has found unused, and that were not written, for
`UNUSED_REFERENCE_RETENTION_DAYS` (default 7), with their files, here and from the archive. A reference cited again
before then is kept. Then it removes the local copies of archived files, as above. Run it e.g. daily:

    30 3 * * * /path/to/breedgraph/scripts/trigger_retention.sh >> /var/log/breedgraph_retention.log 2>&1

### Migrating the BreedCAFS data

The legacy BreedCAFS data is migrated once, after the initial setup and the germplasm import,
following [src/breedcafs_migration/RUNBOOK.md](src/breedcafs_migration/RUNBOOK.md).
The data is extracted and rehearsed locally, then copied to the server as a checked bundle,
with the migration as its own wheel (`scripts/build_migration_wheel.py`), installed only for the run.
