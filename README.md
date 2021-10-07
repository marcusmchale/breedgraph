# BreedGraph API

A package to manage data aggregation in breeding projects.
  - Sampling strategies
    - Field, Block, Tree, Sample in a useful pseudo-hierarchy 
  - Experimental data
    - Molecular/Qualitative/Phenotypic
    - Environmental conditions
    - Locations
  - Genetic data
    - SNP
  - Traceability

Handles GraphQL requests and commits to a Neo4j database.

Maintains a read model in Redis for fast queries in basic navigation.

Accessible through a separate VueJS web-interface (breedview).

Built on the experience of developing and using the [breedcafs database tools](https://github.com/marcusmchale/breedcafs)

Applying the principles of domain driven design and event-driven architecture
e.g.  [Architecture patterns with Python](https://www.oreilly.com/library/view/architecture-patterns-with/9781492052197/)

Development notes:

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
      This should be useful in the future, but it isn't very mature. 
      The standard python driver for the bolt protocol has been used here.
- FastAPI
  - Not used much, mostly GraphQL endpoints, but still central to the functionality.
- Tests
    - in progress...

    
Data access control:
- Users are agents that submit records on behalf of their primary team 
  and may retrieve records from any of their affiliated teams.
    - When a user registers they select their primary team, and an affiliation is created to this team.
      - Affiliations are provided in 3 ranked levels.
          - Level 2: Admin
          - Level 1: User
          - Level 0: Unconfirmed
      - If the team does not yet exist, the user is provided a level 2 affiliation (Admin).
      - If the team does exist, and the new user was invited to join (email added) by an Admin level affiliate
        of this same team, the new user is provided a level 1 affiliation (User).
      - If the team exists, and the new user was invited to join by an unaffiliated user, 
        the new user is provided a level 0 affiliation (Unconfirmed).
    - Users may create secondary affiliations with any other team.
      - Secondary affiliations default to level 0 (Unconfirmed) and can only be deleted if never raised to a higher level.
        - This allows a reconstruction of the history of data access according to timestamps for each level change.
    - The level of each affiliation to a given team can be changed by any user with an Admin level affiliation to this team.
  - All records are associated with the submitting user and their primary team.
  - Each user can retrieve records from teams with which they hold a User (or greater) level affiliation. 
    
  - Notes:
    - The primary team cannot change.
      - In this model the user is defined as an agent of the team. 
        As such, if a person changes teams, they are no longer the same user. 
        In such cases a new user must be registered which will result in multiple "User" accounts 
        sharing details like email address, fullname etc.
    - Users have an additional property "global_admin", set to true for the first registrant automatically.
      - If set to true:
        - This user can change the level of any affiliation.
        - This user can set any users "Global Admin" property.
      - There must always be at least one User with "global_admin" = True
