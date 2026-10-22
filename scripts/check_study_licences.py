"""
Check the licences of studies (docs/read-access.md, rule 10). Read only: it reports, and changes nothing.

A study's licence is a legal reference released at least as widely as the study, every dataset of the study, and every
file reference they or their records cite (a reference with a file, which holds data). The rule is checked as changes
commit, on the studies they touch, so data written before it, or by other means, may break it; while a study does,
changes to its releases, its datasets, its licence and the files they cite are refused until one change sets it right.
Run it before deploying, and after migrations.

Usage, with the instance env files sourced:  python scripts/check_study_licences.py
Exits non-zero when anything is reported.
"""
import asyncio
import sys

from neo4j import AsyncGraphDatabase

from breedgraph.config import get_bolt_url, get_graphdb_auth, DATABASE_NAME
from breedgraph.adapters.neo4j.cypher.query_builders.controls import licence_release_violations
from breedgraph.domain.model.references import ReferenceType

LICENSED_STUDIES = """
    MATCH (study: Study)-[:USES_LICENCE]->(:Reference)
    RETURN collect(study.id) AS study_ids
"""

NOT_LEGAL = f"""
    MATCH (study: Study)-[:USES_LICENCE]->(licence: Reference)
    WHERE licence.type <> '{ReferenceType.LEGAL.value}'
    RETURN study.id AS study, licence.id AS licence, licence.type AS type
    ORDER BY study
"""


async def main() -> int:
    reported = 0
    driver = AsyncGraphDatabase.driver(get_bolt_url(), auth=get_graphdb_auth())
    try:
        async with driver.session(database=DATABASE_NAME) as session:
            study_ids = (await (await session.run(LICENSED_STUDIES)).single())['study_ids']
            checks = {
                'Study licences released less widely than the study, its datasets or the files they cite': (
                    licence_release_violations(),
                    {'study_ids': study_ids, 'dataset_ids': [], 'reference_ids': []}
                ),
                'Study licences that are not legal references': (NOT_LEGAL, {}),
            }
            for title, (query, parameters) in checks.items():
                result = await session.run(query, parameters)
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
