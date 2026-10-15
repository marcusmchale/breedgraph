"""
Write stamps of the migration (README §14).

BreedGraph stamps each write to a controlled model with the user and transaction time (a CONTRIBUTED relationship,
read as the model's writes, created and updated). The migration writes a model in several transactions (records in
batches, then contributors; units, then positions), which leaves many stamps by the migration user for what is one act
of migration. This keeps only the earliest of the migration user's stamps on each model, so `created` stays the time
it was migrated and `updated` equals it. Stamps by other users are kept, e.g. on production germplasm the migration
linked to. Running it again changes nothing.
"""
from breedgraph.adapters.neo4j import Neo4jUnitOfWorkFactory
from breedgraph.domain.model.controls import ControlledModelLabel

import logging
logger = logging.getLogger(__name__)


def stamps_query(label: ControlledModelLabel) -> str:
    """The migration user's stamps on each model of a label, earliest first"""
    return f"""
        MATCH (:User {{id: $user_id}})-[:CONTRIBUTED]->(:User{label.plural})-[write:CONTRIBUTED]->(entity:{label.label})
        WITH entity, write ORDER BY write.time
        WITH entity, collect(write) AS writes
    """


def consolidate_query(label: ControlledModelLabel) -> str:
    return stamps_query(label) + """
        WHERE size(writes) > 1
        CALL (writes) {
            UNWIND writes[1..] AS extra
            DELETE extra
            RETURN count(*) AS deleted
        } IN TRANSACTIONS OF 1000 ROWS
        RETURN sum(deleted) AS deleted
    """


def count_query(label: ControlledModelLabel) -> str:
    """Models with more than one stamp by the migration user"""
    return stamps_query(label) + """
        WHERE size(writes) > 1
        RETURN count(entity) AS models
    """


async def consolidate_write_stamps(uow_factory: Neo4jUnitOfWorkFactory, user_id: int) -> int:
    """Keeps the earliest of the migration user's write stamps on each model. Returns the number of stamps removed."""
    removed = 0
    for label in ControlledModelLabel:
        # CALL ... IN TRANSACTIONS needs an implicit transaction
        async with uow_factory.driver.session() as session:
            result = await session.run(consolidate_query(label), user_id=user_id)
            record = await result.single()
            deleted = (record['deleted'] or 0) if record else 0
        if deleted:
            logger.info(f"Removed {deleted} extra write stamps of the migration user on {label.plural}")
        removed += deleted
    return removed


async def models_with_extra_stamps(uow_factory: Neo4jUnitOfWorkFactory, user_id: int) -> dict[ControlledModelLabel, int]:
    """For validation: per label, the models with more than one write stamp by the migration user"""
    found = {}
    for label in ControlledModelLabel:
        async with uow_factory.driver.session() as session:
            result = await session.run(count_query(label), user_id=user_id)
            found[label] = (await result.single())['models']
    return found
