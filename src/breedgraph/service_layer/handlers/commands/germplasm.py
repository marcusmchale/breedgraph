from src.breedgraph.service_layer.infrastructure import AbstractUnitOfWork

from src.breedgraph.domain import commands
from src.breedgraph.domain.model.germplasm import GermplasmInput, GermplasmStored, GermplasmSourceType, GermplasmRelationship

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

@handlers.command_handler()
async def create_germplasm_entry(
        cmd: commands.germplasm.CreateGermplasm,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        germplasm_service = uow.germplasm
        entry = GermplasmInput(
            name=cmd.name,
            description=cmd.description,
            synonyms=cmd.synonyms or [],
            authors=cmd.author_ids or [],
            references=cmd.reference_ids or [],
            origin=cmd.origin_id,
            time=cmd.time,
            reproduction=cmd.reproduction,
            control_methods=cmd.control_method_ids
        )
        entry = await germplasm_service.create_entry(entry)
        if cmd.sources or cmd.sinks:
            relationships = []
            if cmd.sources:
                relationships += [
                    GermplasmRelationship(
                        **source.model_dump(),
                        sink_id=entry.id
                    ) for source in cmd.sources
                ]
            if cmd.sinks:
                relationships += [
                    GermplasmRelationship(
                        **sink.model_dump(),
                        source_id=entry.id
                    ) for sink in cmd.sinks
                ]
            await germplasm_service.create_relationships(relationships)
        await uow.commit()


@handlers.command_handler()
async def update_germplasm_entry(
        cmd: commands.germplasm.UpdateGermplasm,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        germplasm_service = uow.germplasm
        entry = await germplasm_service.get_entry(cmd.id)

        if cmd.name and not cmd.name == entry.name:
            entry.name = cmd.name
        if cmd.description and not cmd.description == entry.description:
            entry.description = cmd.description
        if cmd.synonyms and not set(cmd.synonyms) == set(entry.synonyms):
            entry.synonyms = cmd.synonyms
        if cmd.author_ids and not set(cmd.author_ids) == set(entry.authors):
            entry.authors = cmd.authors
        if cmd.reference_ids and not set(cmd.reference_ids) == set(entry.references):
            entry.references = cmd.reference_ids
        if cmd.origin_id and not cmd.origin_id == entry.origin:
            entry.origin = cmd.origin_id
        if cmd.time and not cmd.time == entry.time:
            entry.time = cmd.time
        if cmd.reproduction and not cmd.reproduction == entry.reproduction:
            entry.reproduction = cmd.reproduction
        if cmd.control_method_ids and not set(cmd.control_method_ids) == set(entry.control_method_ids):
            entry.control_methods = cmd.control_method_ds

        await germplasm_service.update_entry(entry)
        await germplasm_service.update_entry_relationships(
            entry_id= cmd.id,
            sources=[GermplasmRelationship(**source_rel.model_dump(), sink_id=cmd.id) for source_rel in cmd.sources] if cmd.sources else None,
            sinks=[GermplasmRelationship(**sink_rel.model_dump(), source_id=cmd.id) for sink_rel in cmd.sinks] if cmd.sinks else None
        )
        await uow.commit()



@handlers.command_handler()
async def delete_germplasm_entry(
        cmd: commands.germplasm.DeleteGermplasm,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        germplasm_service = uow.germplasm
        await germplasm_service.delete_entry(cmd.id)
        await uow.commit()