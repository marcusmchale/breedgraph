"""
The ontology entries every deployment starts with, created by scripts/setup_initial_data.py as the system user.
"""
from breedgraph.domain.model.ontology import (
    OntologyEntryLabel, LocationTypeInput, RoleInput, credit_roles, CREDIT_ATTRIBUTION
)
from breedgraph.service_layer.application.ontology_service import OntologyApplicationService

import logging
logger = logging.getLogger(__name__)


async def seed_ontology(ontology: OntologyApplicationService) -> None:
    """
    Create what is missing, by name: the Country location type, which root locations use,
    and the CRediT roles, locked, with their source (docs/contributions.md §3).
    The caller commits a version, so the entries are active.
    """
    if await ontology.get_entry(name='Country', label=OntologyEntryLabel.LOCATION_TYPE) is None:
        logger.info("Creating the Country location type")
        await ontology.create_entry(LocationTypeInput(
            name='Country',
            description='Country and three digit code according to ISO 3166-1 alpha-3'
        ))
    to_lock = []
    for role in credit_roles():
        if await ontology.get_entry(name=role.name, label=OntologyEntryLabel.ROLE) is None:
            logger.info(f"Creating the CRediT role {role.name}")
            entry = await ontology.create_entry(RoleInput(
                name=role.name,
                description=role.definition,
                source_url=role.url,
                source_attribution=CREDIT_ATTRIBUTION
            ))
            to_lock.append(entry.id)
    if to_lock:
        await ontology.lock_entries(to_lock)
