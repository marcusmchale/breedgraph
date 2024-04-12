# BreedGraph API

A package to manage data aggregation in breeding projects.
  - Sampling strategies
    - Field, Block, Tree, Sample in a useful pseudo-hierarchy 
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

Built on the experience of developing and using the [breedcafs database tools](https://github.com/marcusmchale/breedcafs)

Applying the principles of domain driven design and event-driven architecture
e.g.  [Architecture patterns with Python](https://www.cosmicpython.com/book/preface.html)

Development notes:
# for testing on community we can only have one active db
# change the /etc/neo4j/neo4j.conf line to specify which to run, e.g.
initial.dbms.default_database=test



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


