# BreedGraph API
A package to manage data in breeding projects by aggregation into a knowledge graph.

## Background and design
BreedGraph was developed with the experience of developing and using the [breedcafs database tools](https://github.com/marcusmchale/breedcafs).
The largely monolithic design of this tool made it difficult to adapt to new situations. 
So, in BreedGraph we have sought to separate concerns, in particular by applying domain driven design
to better isolate domain logic from other concerns.

Established API specifications (e.g. BrAPI), ontologies (e.g. Planteome, CropOntology) and standards (e.g. MIAPPE)
all informed domain modeling. Although BreedGraph extends and adapts these plant-centric models
with more flexible definition of the "subject" of the study.
These changes were required to more appropriately model microbial data for the BOLERO project.
Further detail on domain models is outlined below.

BreedGraph currently relies on the Neo4j graph database management system (DBMS) for persistence, 
with transactions and the unit-of-work pattern ensuring ACID compliance
(Atomicity, Consistency, Isolation, and Durability).
However, all interactions with this DBMS are contained within a repository layer,
providing the opportunity to adapt to alternative database technologies in the future.
Repositories retrieve and compose domain model objects with change tracking using object proxy wrappers.
This isolates the domain from persistence concerns, allows repositories to operate efficiently 
and preserves records for audit purposes. 

Surrounding the inner persistence layer, in an outer-repository layer, 
is a combined group- and role-based access control. 
Groups are flexibly defined as hierarchical organisations, with optional inheritance of roles (read/write/admin/curate).
Domain aggregates composed of controlled domain models
are redacted prior to presentation to the service layer.

This service layer employs a messaging bus with commands to trigger changes and events
to asynchronously issue other responses such as emails.
Command and query responsibility segregation (CQRS) is further implemented
with read-only views and an in memory cache (Redis) improving the efficiency of simple queries. 

A graphql entry-point is provided (Ariadne) to access views and issue service commands.
The GraphQL standard is well suited to querying the knowledge graph, 
allowing efficient navigation and complex nested queries that return only the required information.
This can be accessed through in-browser applications like GraphQL playground, 
where documentation is presented to assist in schema interpretation.
This interface will guide front-end development for customised tools in data entry and analysis.   

Refs.  [Architecture patterns with Python](https://www.cosmicpython.com/book/preface.html). 

## Domain

### Ontology
A central feature of BreedGraph is the adaptive ontology.

All 
 
This ontology is represented by a graph, with nodes corresponding to:


The ontology graph has nodes representing traits, conditions, exposures etc.

Ontologies are version controlled.

Access control, users, organisations...

== Programs ==
A common entry into this knowledge graph is via the Program interface.
A program is astudy




    - 
  - Experimental data
    - Molecular/Qualitative/Phenotypic
    - Microbiome
    - Environmental conditions
    - Locations
  - Genetic data
    - SNP
    - Pedigree
  - Traceability

Handles GraphQL requests and commits to a Neo4j database.

Maintains a read model in Redis for fast queries in basic navigation.

Accessible through a separate VueJS web-interface (breedview).


- Async
    - emails (aiosmtplib)
    - graphql (Ariadne)
    - Implemented repositories using blocking calls on a thread pool for db responses.
      while waiting for the [neo4j python driver to support async](
      https://github.com/neo4j/neo4j-python-driver/issues/180).
    - Unit of Work, using asyncio.Lock to prevent concurrency issues with shared repositories.
      The alternative is to allow concurrent units of work and handle a lot more conflict resolution. 
      This might be worth it if we wanted to go multi-threaded.
- GraphQL
    - The [neo4j database has a lot of potential for use with GraphQL](https://pypi.org/project/neo4j-graphql-py/).
      This would be useful, but it isn't very mature. 
      The standard python driver for the bolt protocol has been used here.
- FastAPI
  - Not used much, mostly GraphQL endpoints, but still central to the functionality.
- Tests
    - in progress...

    
Data access control:
- Users are agents that submit records on behalf of teams for which they have a "write" affiliation. 
  and may retrieve records from any of their affiliated teams.
    - When a user registers they select a team, and a "write" affiliation is created to this team.
      - Affiliations are provided in 3 ranked levels.
          - Level 2: Admin
          - Level 1: User
          - Level 0: Unconfirmed
      - If the team does not exist, the user is provided a level 2 affiliation (Admin).
      - If the team exists, and the user was invited to join (email added by an Admin level affiliate
        of this same team), the new user is provided a level 1 affiliation (User).
      - If the team exists, and the user joins without invitation,
        the new user is provided a level 0 affiliation (Unconfirmed), 
        and a request is sent to the corresponding Admin to elevate this affiliation.
    - Users may create affiliations with any team.
      - Secondary affiliations default to level 0 (Unconfirmed) and can only be deleted if never raised to a higher level.
        - This allows a reconstruction of the history of data access according to timestamps for affiliation level change.
    - The level of each affiliation to a given team can be changed by any user with an Admin level affiliation to this team.
  - All records are associated with the submitting user and their current "write" team.
  - Each user can retrieve records from teams with which they hold a User (or greater) level affiliation. 
- Users have an additional property "global_admin", set to true for the first registrant automatically.
  - If set to true:
    - This user can change the level of any affiliation.
    - This user can set any users "Global Admin" property.
  - There must always be at least one User with "global_admin" = True

## Setup neo4j
get the key, add the source and apt install

    wget -O - https://debian.neo4j.com/neotechnology.gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/neo4j.gpg
    deb [signed-by=/usr/share/keyrings/neo4j.gpg] https://debian.neo4j.com stable latest
    sudo apt install neo4j=1:5.1.0

set initial password for neo4j user (only works if run before starting for the first time)

    neo4j-admin dbms set-initial-password <password-here> 

enable systemd to start the neo4j service

    sudo systemctl enable neo4j    
    sudo systemctl start neo4j

## Set up redis
    sudo apt install redis-server

change /etc/redis/redis.conf "supervised no" to "supervised systemd" to allow systemd to manage startup
restart to load config

    sudo systemctl restart redis.service



Development notes:
  - for testing on community we can only have one active db
  - change the /etc/neo4j/neo4j.conf line to specify which to run, e.g.
    - initial.dbms.default_database=test

