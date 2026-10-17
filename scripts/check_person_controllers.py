"""
Check that every Person has one data controller (docs/person.md §2): current controls, by teams of one team tree,
whose root has one current legal entity declaration. Read only: it reports, and changes nothing.

Persons without current controls would be readable by anyone under the general read rule, and their data controller
would be unknown; the people view treats them as hidden unless linked. A Person controlled across team trees, or
under a root without a declaration, shows no data controller. Run it before deploying, and after migrations.

Usage, with the instance env files sourced:  python scripts/check_person_controllers.py
Exits non-zero when anything is reported.
"""
import asyncio
import sys

from neo4j import AsyncGraphDatabase

from breedgraph.config import get_bolt_url, get_graphdb_auth, DATABASE_NAME

# a team's current control of a Person is its latest, while not ended (as query_builders.access.readable decides it)
CURRENT_CONTROL_TEAMS = """
    MATCH (person: Person)<-[:CONTROLS]-(control: Control)<-[:CONTROLS]-(team_people: TeamPeople)<-[:CONTROLS]-(team: Team)
    WHERE NOT coalesce(control.ended, false)
      AND NOT EXISTS { MATCH (person)<-[:CONTROLS]-(newer: Control)<-[:CONTROLS]-(team_people) WHERE newer.sequence > control.sequence }
"""

ROOTS = """
    MATCH (team)<-[:INCLUDES_TEAM*0..]-(root: Team) WHERE NOT (root)<-[:INCLUDES_TEAM]-(:Team)
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
    'Persons controlled by teams of more than one team tree': f"""
        {CURRENT_CONTROL_TEAMS}
        {ROOTS}
        WITH person, collect(DISTINCT root.id) AS roots
        WHERE size(roots) > 1
        RETURN person.id AS person, roots
        ORDER BY person
    """,
    'Persons whose team tree has no current legal entity declaration': f"""
        {CURRENT_CONTROL_TEAMS}
        {ROOTS}
        WITH person, collect(DISTINCT root) AS roots
        WHERE size(roots) = 1
        WITH person, roots[0] AS root
        WHERE NOT EXISTS {{ MATCH (root)-[:DECLARED {{current: true}}]->(:LegalEntityDeclaration) }}
        RETURN person.id AS person, root.id AS root, person.erased_at IS NOT NULL AS erased
        ORDER BY person
    """,
    'Roots with more than one current legal entity declaration': """
        MATCH (root: Team)-[:DECLARED {current: true}]->(declaration: LegalEntityDeclaration)
        WITH root, count(declaration) AS declarations
        WHERE declarations > 1
        RETURN root.id AS root, declarations
        ORDER BY root
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
