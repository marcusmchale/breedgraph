import pytest
import pytest_asyncio
from typing import AsyncGenerator

from src.breedgraph.service_layer.application.germplasm_service import GermplasmApplicationService
from src.breedgraph.domain.model.controls import Access, ReadRelease
from tests.integration.conftest import neo4j_access_control_service


@pytest_asyncio.fixture(scope='session')
async def read_only_germplasm_service(
    germplasm_persistence_service,
    neo4j_access_control_service,
    stored_account,
    stored_organisation
) -> AsyncGenerator[GermplasmApplicationService, None]:
    """
    Integration test fixture for a read-only germplasm service.
    """
    yield GermplasmApplicationService(
        persistence_service=germplasm_persistence_service,
        access_control_service=neo4j_access_control_service,
        user_id=stored_account.user.id,
        access_teams={
            Access.READ: {stored_organisation.root.id},
            Access.WRITE: set(),
            Access.CURATE: set(),
            Access.ADMIN: set()
        },
        release=ReadRelease.REGISTERED
    )

@pytest_asyncio.fixture(scope='session')
async def no_read_germplasm_service(
    germplasm_persistence_service,
    neo4j_access_control_service,
    stored_account
) -> AsyncGenerator[GermplasmApplicationService, None]:
    """
    Integration test fixture for a read-only germplasm service.
    """
    yield GermplasmApplicationService(
        persistence_service=germplasm_persistence_service,
        access_control_service=neo4j_access_control_service,
        user_id=stored_account.user.id,
        access_teams={
            Access.READ: set(),
            Access.WRITE: set(),
            Access.CURATE: set(),
            Access.ADMIN: set()
        },
        release=ReadRelease.REGISTERED
    )

@pytest_asyncio.fixture(scope='session')
async def unregistered_germplasm_service(
    germplasm_persistence_service,
    neo4j_access_control_service
) -> AsyncGenerator[GermplasmApplicationService, None]:
    """
    Integration test fixture for a read-only germplasm service.
    """
    yield GermplasmApplicationService(
        persistence_service=germplasm_persistence_service,
        access_control_service=neo4j_access_control_service,
        user_id=None,
        access_teams={
            Access.READ: set(),
            Access.WRITE: set(),
            Access.CURATE: set(),
            Access.ADMIN: set()
        },
        release=ReadRelease.REGISTERED
    )