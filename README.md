# BreedGraph API

A package to manage data aggregation in breeding projects. 
  - Experimental data
    - Molecular/Qualitative/Phenotypic
  - Genetic data
    - SNP
  - Traceability

Handles GraphQL requests and commits to a Neo4j database.

Accessible through a separate VueJS web-interface (breedview).

Built following the experience of developing and using the [breedcafs database tools](https://github.com/marcusmchale/breedcafs)


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
  - I am using this framework I don't actually need it for much, mostly GraphQL endpoints.
- Tests
    - no testing has yet been included, this is a big "todo"
