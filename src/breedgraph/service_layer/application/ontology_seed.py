"""
The ontology entries every deployment starts with, created by scripts/setup_initial_data.py as the system user.

Each is locked, and keyed: code finds it by its seed key, whatever its name, as an admin may unlock and edit it.
Once found, it is referred to by id, so the referential view resolves it in any phase.
"""
from breedgraph.domain.model.ontology import (
    LocationTypeInput, RoleInput, CreditRole, credit_roles, CREDIT_ATTRIBUTION
)
from breedgraph.service_layer.application.ontology_service import OntologyApplicationService

import logging
logger = logging.getLogger(__name__)

# the location type of root locations, which are countries
COUNTRY = 'country'


def credit_seed_key(role: CreditRole) -> str:
    return f'credit:{role.external_id}'


def credit_seed_key_for(name: str) -> str:
    """The seed key of the CRediT role with this name as published, e.g. Data curation"""
    for role in credit_roles():
        if role.name == name:
            return credit_seed_key(role)
    raise ValueError(f"No CRediT role named {name}")


async def seed_ontology(ontology: OntologyApplicationService) -> None:
    """
    Create what is missing, by seed key: the Country location type, which root locations use,
    and the CRediT roles with their source (docs/contributions.md §3).
    The caller commits a version, so the entries are active.
    """
    if await ontology.get_seeded_entry(COUNTRY) is None:
        logger.info("Creating the Country location type")
        await ontology.seed_entry(LocationTypeInput(
            name='Country',
            description='Country and three digit code according to ISO 3166-1 alpha-3'
        ), COUNTRY)
    for role in credit_roles():
        if await ontology.get_seeded_entry(credit_seed_key(role)) is None:
            logger.info(f"Creating the CRediT role {role.name}")
            await ontology.seed_entry(RoleInput(
                name=role.name,
                description=role.definition,
                source_url=role.url,
                source_attribution=CREDIT_ATTRIBUTION
            ), credit_seed_key(role))
