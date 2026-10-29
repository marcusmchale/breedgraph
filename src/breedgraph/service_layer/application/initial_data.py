"""
What every deployment starts with, created as the system user by scripts/setup_initial_data.py, the database builds
(scripts/database_builds.py) and the test setup alike.
"""
from breedgraph.domain.model.ontology import OntologyCommit
from breedgraph.service_layer.application.licence_seed import seed_licences, CC_BY
from breedgraph.service_layer.application.ontology_seed import seed_ontology


async def seed_initial_data(uow) -> OntologyCommit:
    """
    The standard licences, the seeded ontology entries, and the ontology's first version, under CC BY 4.0: the CRediT
    roles in it are NISO's under CC BY 4.0, and later versions keep the licence unless an ontology admin names another
    (docs/licences.md §6). The caller commits the unit of work.
    """
    licences = await seed_licences(uow.repositories.references)
    await seed_ontology(uow.ontology)
    return await uow.ontology.commit_version(
        version_change=None,
        comment="Initial system commit",
        licence_reference=licences[CC_BY]
    )
