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

To contribute to these aggregates, users must have a WRITE affiliation with a [team](#organisation).
Access to READ and CURATE these contributions is then controlled 
by users with an ADMIN affiliation to that team.

These ADMIN affiliates set the read RELEASE status to one of three levels:
- PRIVATE models are only accessible to users with a READ affiliation to a controlling team
- REGISTERED models are accessible only to registered users.
- PUBLIC models are accessible to anyone.

Users may request READ/WRITE/CURATE/ADMIN affiliations from a team
which are then approved by ADMIN affiliates for that team. 
READ/CURATE and ADMIN affiliations may be heritable,
meaning that the same authorisation is applied to all teams in that branch of the [organisation](#organisation). 

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
and representation of observation units in flexible [blocks](#block) 
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
Subject entries describe the [units](#block) being observed in a study.
These also provide context for the relevance of [traits](#trait) in the ontology.
Examples: "Leaf", "Tree", "Field", "Rhizosphere Soil"
##### Scale
Scale entries describe the measurement unit or classes used in a:
- [variable](#variable), 
- [parameter](#parameter), or
- [event](#eventtype)
Scale entries require a ScaleType, one of:
- date,
- duration,
- numerical,
- nominal,
- ordinal,
- text,
- germplasm
For nominal and ordinal types, additional category references may be provided.
For germplasm type, [germplasm](#germplasm) identifiers must be used,
with composite material (i.e. grafted) represented as integers using the scion/rootstock code, e.g. "11/3".
Examples:
"Centimeters", "Counts per million", "Micro-Einsteins" are all ScaleType numerical.
"Genetic Material" is ScaleType germplasm.
##### ScaleCategory
Category entries describe classes for [scale](#scale) entries with type Nominal or Ordinal.
Ordinal scales require an additional "rank" parameter (integer value) for each category.
Examples: "High", "Medium", "Low" with ranks 2, 1 and 0, respectively.
##### ObservationMethod
Observation method entries describe the way a value is determined for:
 - [variable](#variable) or
 - [event](#eventtype).
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
Control method entries describe the way a value is maintained for a [parameter](#parameter) or [event](#eventtype).
Examples: "Fluorescent Lighting", "Fertilizer application", "Germplasm selection"
##### Condition
Condition entries describe the quantities/qualities that are fixed/controlled 
for a [parameter](#parameter).
Examples: "Light level", "Controlled Grafting", "Water availability"
##### Parameter
Parameter entries link a [condition](#condition), [method](#controlmethod) and [scale](#scale)
to form a single entry for a [dataset](#dataset).
Examples:
- "Controlled lighting" where condition = "Light level", method = "Fluorescent lighting", scale = "Micro Einsteins"
- "Controlled water availability" where condition = "Water availability", method = "Controlled water application", scale = "L/m2/day"
- "Grafted Material" where condition = "Genetic material", method = "controlled Grafting", scale = "Plant Genetic Material"
##### Exposure
Exposure entries describe temporary occurrences within an experimental setting for an [event](#eventtype) 
Examples: "Fertilizer application", "Rainfall"
##### EventType
EventType entries link an [exposure](#exposure), 
method (either [observation](#observationmethod) or [control](#controlmethod)) and a [scale](#scale).
to form a single entry for a [dataset](#dataset).
Examples:
- "Pellet Fertilizer Application" where exposure = "Fertilizer application", method = "Pellet Dispersion", scale = "kg/ha"
##### GermplasmMethod
Germplasm method entries describe maintenance or sourcing of 
an [entry](#germplasmentry) within a [germplasm](#germplasm) pool.
Examples: "Controlled cross", "Mutagenesis", "Ecological survey"
##### LocationType
Location entries describe types of locations within a [region](#region).
Examples: "Country", "State", "Field"
##### LayoutType
Layout entries describe types of [layout](#layout) within an [arrangement](#arrangement).
Examples: "Grid", "Row"
##### Design
Design entries describe statistical designs for a [study](#study) in a [program](#program).
Examples: "Split-plot", "Randomized block"
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

### Organisation
Organisations are directed acyclic graphs of teams with a single root node. 
These form the foundation of [access control](#access-control) logic.

In the GraphQL interface, the add_team mutation will create a team.
If the optional "parent" parameter is not supplied then the created team 
becomes the root of a new organisation. When more teams are required for an organisation, 
this parameter results in the new team being a child of the parent.
The user that creates a team is automatically given a heritable ADMIN affiliation to that team, 
allowing them to approve further affiliations. 

All root teams are visible to all users,
though child teams are visible only to affiliates in that branch.
Other users may request READ,WRITE,ADMIN or CURATE affiliations,
with ADMIN affiliates receiving an email to approve this request. 
Such requests are heritable, such that a user may request an affiliation to the root of an organisation, 
and ADMIN affiliates may approve the affiliation only to a chosen child team.
#### Team
Teams have name and fullname attributes.
### Arrangement
Arrangements are directed acyclic graphs with a single root, composed of layouts.
These are used to describe positions for [units](#unit) within [blocks](#block).
#### Layout
Layouts have attributes for:
  - type, an ID for [layout type](#layouttype) in the ontology
  - location: an ID for a [location](#location) within a [region](#region)
  - axes: labels for the axes (a list of strings). 
    - The order of axes must be preserved when describing positions for a [unit](#unit).
  - Optional:
    - name: a string to describe this specific layout

### Block
Blocks are directed acyclic graphs with a single root, composed of [units](#unit)
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
- location: an ID for a [location](#location) within a [region](#region)
- start: a start date and time for this position
- Optional:
  - layout: an ID for a [layout](#layout) within an [arrangement](#arrangement)
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
- origin: an ID for a [location](#location) within a [region](#region)
- time: to describe when this germplasm was sourced from origin.
- reproduction: one of CLONAL, ASEXUAL or APOMIXIS used to describe the maintainence of this germplasm
- methods: a list of [germplasm methods](#germplasmmethod) in the ontology, describing the protocol for the generation of this germplasm
  - e.g. clonal propagation via tissue culture, controlled self-fertilisation, uncontrolled pollination
### People
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
### Region
A region is a directed acyclic graph with a single root node, composed of [locations](#location). 
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
    sudo apt install neo4j=1:5.1.0

set initial password for neo4j user (only works if run before starting for the first time)

    neo4j-admin dbms set-initial-password <password-here> 

enable systemd to start the neo4j service

    sudo systemctl enable neo4j    
    sudo systemctl start neo4j

### redis
    sudo apt install redis-server

change /etc/redis/redis.conf "supervised no" to "supervised systemd" to allow systemd to manage startup
restart to load config

    sudo systemctl restart redis.service

### Run with uvicorn
To test with the uvicorn server, go to the root of the project, import the envars from instance directory and run, e.g.
  
    . ./instace/envars.sh
    pip install uvicorn
    uvicorn src.breedgraph.main:app --log-level debug

If you are cloning this project you won't have all the envars provided
and will need to modify the ./instance/envars_public.sh file 
to include the required values for neo4j connection, mail hosting and log file creation

### Notes for developers
  - for testing on community we can only have one active db
  - change the /etc/neo4j/neo4j.conf line to specify which to run, e.g.
    - initial.dbms.default_database=test

