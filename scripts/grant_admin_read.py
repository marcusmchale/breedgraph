"""
Give every authorised admin an authorised read affiliation on the same team, to the same heritable extent.

Admin access now includes read access, as curate access already did. Teams and affiliations created before this
change have admins without read affiliations; run this once after deploying it. It is idempotent.

Usage, with the instance env files sourced:  python scripts/grant_admin_read.py
"""
import asyncio
import logging

from neo4j import AsyncGraphDatabase

from breedgraph.config import get_bolt_url, get_graphdb_auth, DATABASE_NAME

logger = logging.getLogger(__name__)

QUERY = """
MATCH (user:User)-[admin:ADMIN {authorisation: 'AUTHORISED'}]->(team:Team)
MERGE (user)-[read:READ]->(team)
ON CREATE SET read.authorisation = 'AUTHORISED', read.heritable = admin.heritable
ON MATCH SET read.authorisation = 'AUTHORISED', read.heritable = read.heritable OR admin.heritable
RETURN count(read) AS affiliations
"""

async def main():
    driver = AsyncGraphDatabase.driver(get_bolt_url(), auth=get_graphdb_auth())
    async with driver.session(database=DATABASE_NAME) as session:
        result = await session.run(QUERY)
        record = await result.single()
        print(f"Read affiliations set for {record['affiliations']} admin affiliations")
    await driver.close()

if __name__ == '__main__':
    asyncio.run(main())
