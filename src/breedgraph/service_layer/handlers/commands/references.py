import json

from src.breedgraph.custom_exceptions import IllegalOperationError
from src.breedgraph.service_layer.infrastructure import AbstractUnitOfWorkFactory, AbstractUnitHolder, AbstractStateStore
from src.breedgraph.service_layer.application.extra_aggregate import AbstractExtraAggregateService

from src.breedgraph.domain import commands, events

from src.breedgraph.domain.model.references import (
    LegalReferenceInput, LegalReferenceStored,
    ExternalReferenceInput, ExternalReferenceStored,
    ExternalDataInput, ExternalDataStored,
    FileReferenceInput, FileReferenceStored,
    DataFileInput, DataFileStored
)

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

from typing import Dict

def parse_json_schema(schema: str | None) -> Dict:
    if not schema:
        return {}
    else:
        try:
            return json.loads(schema)
        except:
            raise ValueError("Invalid JSON schema provided for external data reference")

@handlers.command_handler(commands.references.CreateLegalReference)
async def create_legal_reference(
    cmd: commands.references.CreateLegalReference,
    uow: AbstractUnitOfWorkFactory
) -> int:
    logger.debug(f'f"Creating legal reference for user {cmd.agent_id}')
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        reference = LegalReferenceInput(
            description=cmd.description,
            text=cmd.text
        )
        stored_reference: LegalReferenceStored = await uow.repositories.references.create(reference)
        await uow.commit()
        return stored_reference.id

@handlers.command_handler(commands.references.CreateExternalReference)
async def create_external_reference(
    cmd: commands.references.CreateExternalReference,
    uow: AbstractUnitOfWorkFactory
) -> int:
    logger.debug(f'f"Creating external reference for user {cmd.agent_id}')
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        reference = ExternalReferenceInput(
            description=cmd.description,
            url=cmd.url,
            external_id=cmd.external_id
        )
        stored_reference: ExternalReferenceStored = await uow.repositories.references.create(reference)
        await uow.commit()
        return stored_reference.id

@handlers.command_handler(commands.references.CreateExternalDataReference)
async def create_external_data(
    cmd: commands.references.CreateExternalDataReference,
    uow: AbstractUnitOfWorkFactory
) -> int:
    logger.debug(f'f"Creating external data reference for user {cmd.agent_id}')
    schema = parse_json_schema(cmd.json_schema)
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        reference = ExternalDataInput(
            description=cmd.description,
            url=cmd.url,
            external_id=cmd.external_id,
            format=cmd.format,
            schema=schema
        )
        stored_reference: ExternalDataStored = await uow.repositories.references.create(reference)
        await uow.commit()
        return stored_reference.id

@handlers.command_handler(commands.references.CreateFileReference)
async def create_file_reference(
    cmd: commands.references.CreateFileReference,
    uow: AbstractUnitOfWorkFactory,
    state_store: AbstractStateStore
) -> int:
    logger.debug(f'f"Creating local data reference for user {cmd.agent_id}')
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        reference_input = FileReferenceInput(
            description=cmd.description,
            filename=cmd.filename,
            content_type=cmd.content_type
            #uuid=cmd.uuid
            # don't set the uuid yet, wait for the file management service to complete the upload
        )
        stored_reference: FileReferenceStored = await uow.repositories.references.create(reference_input)
        await state_store.set_file_reference_id(cmd.uuid, stored_reference.id)
        await uow.commit()
        return stored_reference.id

@handlers.command_handler(commands.references.CreateDataFileReference)
async def create_data_file_reference(
    cmd: commands.references.CreateDataFileReference,
    uow: AbstractUnitOfWorkFactory,
    state_store: AbstractStateStore
) -> int:
    logger.debug(f'f"Creating local data reference for user {cmd.agent_id}')
    schema = parse_json_schema(cmd.json_schema)
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        reference_input = DataFileInput(
            description=cmd.description,
            filename=cmd.filename,
            content_type=cmd.content_type,
            #uuid=cmd.uuid,
            format=cmd.format,
            schema=schema
        )
        stored_reference: DataFileStored = await uow.repositories.references.create(reference_input)
        await state_store.set_file_reference_id(cmd.uuid, stored_reference.id)
        await uow.commit()
        return stored_reference.id

@handlers.command_handler(commands.references.UpdateLegalReference)
async def update_legal_reference(
    cmd: commands.references.UpdateLegalReference,
    uow: AbstractUnitOfWorkFactory
) -> None:
    logger.debug(f'f"Updating legal reference for user {cmd.agent_id}')
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        reference: LegalReferenceStored = await uow.repositories.references.get(reference_id = cmd.reference_id)
        reference.description = cmd.description or reference.description
        reference.text = cmd.text or reference.text
        await uow.commit()

@handlers.command_handler(commands.references.UpdateExternalReference)
async def update_external_reference(
    cmd: commands.references.UpdateExternalReference,
    uow: AbstractUnitOfWorkFactory
) -> None:
    logger.debug(f'f"Updating external reference for user {cmd.agent_id}')
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        reference: ExternalReferenceStored = await uow.repositories.references.get(reference_id = cmd.reference_id)
        reference.description = cmd.description or reference.description
        reference.url = cmd.url or reference.url
        reference.external_id = cmd.external_id or reference.external_id
        await uow.commit()

@handlers.command_handler(commands.references.UpdateExternalDataReference)
async def update_external_data(
    cmd: commands.references.UpdateExternalDataReference,
    uow: AbstractUnitOfWorkFactory
) -> None:
    logger.debug(f'f"Updating external data reference for user {cmd.agent_id}')
    schema = parse_json_schema(cmd.json_schema)
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        reference: ExternalDataStored = await uow.repositories.references.get(reference_id = cmd.reference_id)
        reference.description = cmd.description or reference.description
        reference.url = cmd.url or reference.url
        reference.external_id = cmd.external_id or reference.external_id
        reference.schema = schema or reference.schema
        reference.format = cmd.format or reference.format
        await uow.commit()

@handlers.command_handler(commands.references.UpdateFileReference)
async def update_file_reference(
    cmd: commands.references.UpdateFileReference,
    uow: AbstractUnitOfWorkFactory
) -> None:
    logger.debug(f'f"Updating local data reference for user {cmd.agent_id}')
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        reference: FileReferenceStored = await uow.repositories.references.get(reference_id = cmd.reference_id)
        reference.description = cmd.description or reference.description
        reference.filename = cmd.filename or reference.filename
        reference.content_type = cmd.content_type or reference.content_type
        reference.file_id = cmd.uuid or reference.file_id
        await uow.commit()

@handlers.command_handler(commands.references.UpdateDataFileReference)
async def update_data_file_reference(
    cmd: commands.references.UpdateDataFileReference,
    uow: AbstractUnitOfWorkFactory
) -> None:
    logger.debug(f'f"Updating local data reference for user {cmd.agent_id}')
    schema = parse_json_schema(cmd.json_schema)
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        reference: DataFileStored = await uow.repositories.references.get(reference_id = cmd.reference_id)
        reference.description = cmd.description or reference.description
        reference.filename = cmd.filename or reference.filename
        reference.content_type = cmd.content_type or reference.content_type
        reference.file_id = cmd.uuid or reference.file_id
        reference.schema = schema or reference.schema
        reference.format = cmd.format or reference.format
        await uow.commit()

@handlers.command_handler(commands.references.DeleteReferences)
async def delete_reference(
    cmd: commands.references.DeleteReferences,
    uow: AbstractUnitOfWorkFactory,
    extra: AbstractExtraAggregateService
) -> None:
    logger.debug(f'f"Deleting references {cmd.reference_ids}')
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        repo = uow.repositories.references
        async for reference in repo.get_all(reference_ids=cmd.reference_ids):
            if await extra.reference_in_use(reference):
                raise IllegalOperationError(f"Reference {reference.id} is in use")

            if isinstance(reference, FileReferenceStored):
                event = events.references.FileReferenceDeleted(
                    uuid=reference.file_id
                )
                reference.events.append(event)

            await repo.remove(reference)
        await uow.commit()
