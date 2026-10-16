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
Domain aggregates composed of controlled domain models
are redacted prior to presentation to the service layer.

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
and READ cannot be revoked from an authorised ADMIN (revoke ADMIN first). Existing deployments can
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
unit's descendants (the nearest record applies), and for all time when they have none (docs/analysis.md §2).
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
* a WITHIN_GRAPH code, for a group of units within one unit graph (the design blocks of a field);
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
A team tree whose root team has declared a legal entity is an organisation, such as a university: the data controller
for the Persons its teams record. Only organisations can record Persons. Withdrawing the declaration, which is refused
while the tree controls any Person, makes it a plain team tree again.

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
  - synonyms
  - description
  - positions: a list of [positions](#position)
##### Position
Positions have attributes for:
- location: an ID for a [location](#location) within a [location tree](#location-tree)
- start: a start date and time for this position
- Optional:
  - layout: an ID for a [layout](#layout) within a [layout tree](#layout-tree)
  - coordinates: a coordinate list that should correspond to the axes in a layout
  - end: an end date and time for this position
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
- references: a list of [references](#reference).
  - References may be used to link supporting data files, e.g. library sequencing data
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
- licence: a [reference](#reference) that describes legal terms for usage of datasets (factors/observations) from this experiment
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


### Nginx
  be sure to set nginx client_max_body_size to a value that is appropriate for your use case, e.g. 100M



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

### Backups, restores and retention

Neo4j is dumped on the web server, and the dumps and the erasure log are copied to an archive server.
The erasure log records erased Persons and deleted accounts outside the database, so a restore can apply them
again ([docs/person.md](docs/person.md) §5). Redis is not backed up: it holds read models, which are rebuilt from
Neo4j, and work in progress (dataset submissions, analysis jobs and their results for `ANALYSIS_RETENTION_DAYS`,
upload progress), which is lost if Redis is.

**Back up** on the web server with `scripts/backup.sh`. It stops Neo4j (the API is unavailable meanwhile),
dumps `DATABASE_NAME` to `NEO4J_ARCHIVE_PATH` as `<database>-<date>.dump`, and starts Neo4j again.
It uses `sudo` to stop Neo4j and dump as the neo4j user, and reads its settings from the environment, which cron
doesn't load. For example, in the crontab of a user allowed those commands, nightly:

    15 2 * * * cd /path/to/breedgraph && set -a && . ./breedgraph.env && set +a && scripts/backup.sh >> /var/log/breedgraph_backup.log 2>&1

Dumps accumulate on the web server; remove old ones there as space requires, once the archive server has them.

**Copy** the dumps and the erasure log to the archive server with `scripts/sync_database_backups.sh`, run from cron
*on the archive server*, at least as often as dumps are made: an erasure is at risk until the log is copied.
Its settings are in `/etc/breedgraph/backup_sync.env` (example: `instance/backup_sync.env`), and it needs ssh key
access to the web server. New dumps are copied as they appear, and the log with `rsync --append-verify`, as it is only
ever appended to. `BACKUP_RETENTION_DAYS` optionally removes old dumps there; the erasure log is never removed.

    0 * * * * /path/to/breedgraph/scripts/sync_database_backups.sh >> /var/log/breedgraph_backup_sync.log 2>&1

**Restore** on the web server, with the environment loaded, by the dump's file name in `NEO4J_ARCHIVE_PATH`
(copy it back from the archive server first if needed):

    cd /path/to/breedgraph
    set -a; . ./breedgraph.env; set +a
    scripts/restore.sh <database>-20261015-021500.dump

It asks for confirmation, stops Neo4j, loads the dump over `DATABASE_NAME`, starts Neo4j, and replays the erasure log
(`scripts/apply_erasures.py`), so Persons erased and accounts deleted since the dump stay that way. Each entry is
applied to its own record only, and the id counters are advanced past the logged ids, so no erased id is given out
again. If the log isn't on the web server, restore it from the archive server and run `scripts/apply_erasures.py <log>`
before the database is used. Then rebuild the read models in Redis from the restored database:

    scripts/load_state_store.py

Uploaded files are not in the dump: they stay in `FILE_STORAGE_PATH`, or in archive storage (the archive worker).

**Retention** of files and expired invitations runs through the API, with `scripts/trigger_retention.sh` from cron
on the web server (it loads the env files itself), e.g. daily:

    30 3 * * * /path/to/breedgraph/scripts/trigger_retention.sh >> /var/log/breedgraph_retention.log 2>&1

### Migrating the BreedCAFS data

The legacy BreedCAFS data is migrated once, after the initial setup and the germplasm import,
following [src/breedcafs_migration/RUNBOOK.md](src/breedcafs_migration/RUNBOOK.md).
The data is extracted and rehearsed locally, then copied to the server as a checked bundle,
with the migration as its own wheel (`scripts/build_migration_wheel.py`), installed only for the run.
