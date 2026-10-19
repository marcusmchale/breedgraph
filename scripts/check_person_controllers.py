"""
Check the controls of Persons (docs/person.md §2). Read only: it reports, and changes nothing.

Persons without current controls would be readable by anyone under the general read rule; the people view treats them
as hidden unless linked. Persons are released at most to registered users, so none should be released to the public.
Run it before deploying, and after migrations.

Usage, with the instance env files sourced:  python scripts/check_person_controllers.py
Exits non-zero when anything is reported.
"""
import asyncio
import sys

from neo4j import AsyncGraphDatabase

from breedgraph.config import get_bolt_url, get_graphdb_auth, DATABASE_NAME
from breedgraph.domain.model.controls import ReadRelease

# a team's current control of a Person is its latest, while not ended (as query_builders.access.readable decides it)
CURRENT_CONTROLS = """
    MATCH (person: Person)<-[:CONTROLS]-(control: Control)<-[:CONTROLS]-(team_people: TeamPeople)<-[:CONTROLS]-(team: Team)
    WHERE NOT coalesce(control.ended, false)
      AND NOT EXISTS { MATCH (person)<-[:CONTROLS]-(newer: Control)<-[:CONTROLS]-(team_people) WHERE newer.sequence > control.sequence }
"""

CHECKS = {
    'Persons without current controls': """
        MATCH (person: Person)
        WHERE NOT EXISTS {
          MATCH (person)<-[:CONTROLS]-(control: Control)<-[:CONTROLS]-(team_people: TeamPeople)
          WHERE NOT coalesce(control.ended, false)
            AND NOT EXISTS { MATCH (person)<-[:CONTROLS]-(newer: Control)<-[:CONTROLS]-(team_people) WHERE newer.sequence > control.sequence }
        }
        RETURN person.id AS person, person.erased_at IS NOT NULL AS erased
        ORDER BY person
    """,
    'Persons released to the public': f"""
        {CURRENT_CONTROLS}
        WITH person, control, team
        WHERE control.release > {int(ReadRelease.REGISTERED)}
        RETURN person.id AS person, collect(team.id) AS teams
        ORDER BY person
    """,
}


async def main() -> int:
    reported = 0
    driver = AsyncGraphDatabase.driver(get_bolt_url(), auth=get_graphdb_auth())
    try:
        async with driver.session(database=DATABASE_NAME) as session:
            for title, query in CHECKS.items():
                result = await session.run(query)
                rows = [dict(record) async for record in result]
                print(f"{title}: {len(rows)}")
                for row in rows:
                    print(f"  {row}")
                reported += len(rows)
    finally:
        await driver.close()
    return 1 if reported else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
