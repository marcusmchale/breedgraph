from typing import Dict, Set

from neo4j import AsyncTransaction

from src.breedgraph.service_layer.application.access_control import AbstractAccessControlService

from src.breedgraph.adapters.neo4j.repositories.accounts import Neo4jAccountRepository
from src.breedgraph.adapters.neo4j.repositories.arrangements import Neo4jArrangementsRepository
from src.breedgraph.adapters.neo4j.repositories.blocks import Neo4jBlocksRepository
from src.breedgraph.adapters.neo4j.repositories.datasets import Neo4jDatasetsRepository
from src.breedgraph.adapters.neo4j.repositories.organisations import Neo4jOrganisationsRepository
from src.breedgraph.adapters.neo4j.repositories.people import Neo4jPeopleRepository
from src.breedgraph.adapters.neo4j.repositories.programs import Neo4jProgramsRepository
from src.breedgraph.adapters.neo4j.repositories.references import Neo4jReferencesRepository
from src.breedgraph.adapters.neo4j.repositories.regions import Neo4jRegionsRepository

from src.breedgraph.domain.model.controls import ReadRelease
from src.breedgraph.domain.model.organisations import Access

import logging

from src.breedgraph.service_layer.repositories.holder import AbstractRepoHolder

logger = logging.getLogger(__name__)


class Neo4jRepoHolder(AbstractRepoHolder):
    def __init__(
            self,
            tx: AsyncTransaction,
            access_control_service: AbstractAccessControlService,
            redacted: bool = True,
            release: ReadRelease = ReadRelease.PRIVATE
    ):
        self.tx = tx
        self.user_id = access_control_service.user_id
        self.access_teams = access_control_service.access_teams

        # Access control for account security
        self.accounts = Neo4jAccountRepository(self.tx)
        # Similarly, the access control for organisations is via internally described affiliations

        self.organisations = Neo4jOrganisationsRepository(self.tx, user_id=self.user_id, redacted=redacted)
        """
        The below repositories are controlled in a common pattern that determine access
         to the values of models within an aggregate
         - controllers load the controlling teams and their determined release level (private/registered/public)
         - if a user is registered they have a user_id
         - authorised read/write/curate/admin affiliations to each team (access teams) are determined 
         by the affiliations in the organisations repo
         - Read access is determined by the release status (set by the admins for controlling teams)
           - Private = only with read affiliation
           - Registered = has user_id
           - Public = anyone can read
         - Other access write/curate/admin requires the relevant affiliation to the controlling team
        """
        repo_params = {
            'tx': self.tx,
            'access_control_service': access_control_service,
            'release': release
        }
        self.arrangements = Neo4jArrangementsRepository(**repo_params)
        self.datasets = Neo4jDatasetsRepository(**repo_params)
        self.people = Neo4jPeopleRepository(**repo_params)
        self.programs = Neo4jProgramsRepository(**repo_params)
        self.references = Neo4jReferencesRepository(**repo_params)
        self.regions = Neo4jRegionsRepository(**repo_params)
        self.blocks = Neo4jBlocksRepository(**repo_params)

    async def update_all_seen(self):
        logger.debug("Update seen by all repositories")
        await self.accounts.update_seen()
        await self.organisations.update_seen()
        await self.arrangements.update_seen()
        await self.datasets.update_seen()
        await self.people.update_seen()
        await self.programs.update_seen()
        await self.references.update_seen()
        await self.regions.update_seen()
        await self.blocks.update_seen()
