import json
from zipfile import compressor_names

from breedgraph.custom_exceptions import IllegalOperationError
from breedgraph.domain.model.contributions import Contribution, contributions_from
from breedgraph.service_layer.application.contributions import verify_contributions
from breedgraph.service_layer.infrastructure import AbstractUnitOfWorkFactory, AbstractUnitHolder, AbstractStateStore
from breedgraph.service_layer.application.aggregate_restructuring import AbstractAggregateRestructuringService

from breedgraph.domain import commands, events

from breedgraph.domain.model.references import (
    ReferenceType, text_hash,
    LegalReferenceInput, LegalReferenceStored,
    ExternalReferenceInput, ExternalReferenceStored,
    ExternalDataInput, ExternalDataStored,
    FileReferenceInput, FileReferenceStored,
    DataFileInput, DataFileStored
)
from breedgraph.service_layer.infrastructure import FileManagementService, AbstractFileArchivalService
from breedgraph.service_layer.application.file_deletion import delete_file_and_archive

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

def _contributions(cmd) -> list[Contribution] | None:
    if cmd.contributions is None:
        return None
    return contributions_from(contribution.to_contribution() for contribution in cmd.contributions)

@handlers.command_handler(commands.references.CreateLegalReference)
async def create_legal_reference(
    cmd: commands.references.CreateLegalReference,
    uow_factory: AbstractUnitOfWorkFactory,
    state_store: AbstractStateStore
) -> int:
    logger.debug(f'f"Creating legal reference for user {cmd.agent_id}')
    async with uow_factory.get_uow(user_id=cmd.agent_id, write_team=cmd.write_team, release=cmd.release) as uow:
        reference = LegalReferenceInput(
            description=cmd.description,
            text=cmd.text,
            text_format=cmd.text_format,
            content_hash=cmd.content_hash or text_hash(cmd.text),
            filename=cmd.filename,
            content_type=cmd.content_type
        )
        stored_reference: LegalReferenceStored = await uow.repositories.references.create(reference)
        if cmd.uuid is not None:
            # read from a file, which UploadCompleted links to the reference once it is saved, as for file references
            await state_store.set_file_reference_id(cmd.uuid, stored_reference.id)
        await uow.commit()
        return stored_reference.id

@handlers.command_handler(commands.references.CreateExternalReference)
async def create_external_reference(
    cmd: commands.references.CreateExternalReference,
    uow_factory: AbstractUnitOfWorkFactory
) -> int:
    logger.debug(f'f"Creating external reference for user {cmd.agent_id}')
    async with uow_factory.get_uow(user_id=cmd.agent_id, write_team=cmd.write_team, release=cmd.release) as uow:
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
    uow_factory: AbstractUnitOfWorkFactory
) -> int:
    logger.debug(f'f"Creating external data reference for user {cmd.agent_id}')
    schema = parse_json_schema(cmd.json_schema)
    async with uow_factory.get_uow(user_id=cmd.agent_id, write_team=cmd.write_team, release=cmd.release) as uow:
        contributions = _contributions(cmd)
        await verify_contributions(uow, contributions or [])
        reference = ExternalDataInput(
            description=cmd.description,
            url=cmd.url,
            external_id=cmd.external_id,
            format=cmd.format,
            schema=schema,
            contributions=contributions or []
        )
        stored_reference: ExternalDataStored = await uow.repositories.references.create(reference)
        await uow.commit()
        return stored_reference.id

@handlers.command_handler(commands.references.CreateFileReference)
async def create_file_reference(
    cmd: commands.references.CreateFileReference,
    uow_factory: AbstractUnitOfWorkFactory,
    state_store: AbstractStateStore
) -> int:
    logger.debug(f'f"Creating local data reference for user {cmd.agent_id}')
    async with uow_factory.get_uow(user_id=cmd.agent_id, write_team=cmd.write_team, release=cmd.release) as uow:
        contributions = _contributions(cmd)
        await verify_contributions(uow, contributions or [])
        reference_input = FileReferenceInput(
            description=cmd.description,
            filename=cmd.filename,
            content_type=cmd.content_type,
            #uuid=cmd.uuid
            # don't set the uuid yet, wait for the file management service to complete the upload,
            contributions=contributions or []
        )
        stored_reference: FileReferenceStored = await uow.repositories.references.create(reference_input)
        await state_store.set_file_reference_id(cmd.uuid, stored_reference.id)
        await uow.commit()
        return stored_reference.id

@handlers.command_handler(commands.references.CreateDataFileReference)
async def create_data_file_reference(
    cmd: commands.references.CreateDataFileReference,
    uow_factory: AbstractUnitOfWorkFactory,
    state_store: AbstractStateStore
) -> int:
    logger.debug(f'f"Creating local data reference for user {cmd.agent_id}')
    schema = parse_json_schema(cmd.json_schema)
    async with uow_factory.get_uow(user_id=cmd.agent_id, write_team=cmd.write_team, release=cmd.release) as uow:
        contributions = _contributions(cmd)
        await verify_contributions(uow, contributions or [])
        reference_input = DataFileInput(
            description=cmd.description,
            filename=cmd.filename,
            content_type=cmd.content_type,
            #uuid=cmd.uuid,
            format=cmd.format,
            schema=schema,
            contributions=contributions or []
        )
        stored_reference: DataFileStored = await uow.repositories.references.create(reference_input)
        await state_store.set_file_reference_id(cmd.uuid, stored_reference.id)
        await uow.commit()
        return stored_reference.id

@handlers.command_handler(commands.references.UpdateLegalReference)
async def update_legal_reference(
    cmd: commands.references.UpdateLegalReference,
    uow_factory: AbstractUnitOfWorkFactory,
    file_management: FileManagementService,
    archival_service: AbstractFileArchivalService
) -> None:
    """
    New text changes the content hash, so acceptances of the reference no longer hold and are asked for again.
    Read from a new file, it is applied once the file is saved, and UploadCompleted then puts the file in place of the
    old one; typed, it replaces any file the reference was given as. The same text again changes nothing.
    """
    logger.debug(f'f"Updating legal reference for user {cmd.agent_id}')
    replaced_file_id = None
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        reference: LegalReferenceStored = await uow.repositories.references.get(reference_id = cmd.reference_id)
        if reference.type != ReferenceType.LEGAL:
            raise IllegalOperationError(f"Reference {cmd.reference_id} is not a legal reference")
        reference.description = cmd.description or reference.description
        if cmd.text_format is not None:
            reference.text_format = cmd.text_format
        if cmd.filename is not None:
            reference.text = cmd.text
            reference.content_hash = cmd.content_hash
            reference.filename = cmd.filename
            reference.content_type = cmd.content_type
        elif cmd.text is not None and cmd.text != reference.text:
            replaced_file_id = reference.file_id
            reference.text = cmd.text
            reference.content_hash = text_hash(cmd.text)
            reference.filename = None
            reference.content_type = None
            reference.file_id = None
        await uow.commit()

    if replaced_file_id:
        # deleted once the reference no longer points to it
        await delete_file_and_archive(replaced_file_id, file_management, archival_service)

@handlers.command_handler(commands.references.UpdateExternalReference)
async def update_external_reference(
    cmd: commands.references.UpdateExternalReference,
    uow_factory: AbstractUnitOfWorkFactory
) -> None:
    logger.debug(f'f"Updating external reference for user {cmd.agent_id}')
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        reference: ExternalReferenceStored = await uow.repositories.references.get(reference_id = cmd.reference_id)
        reference.description = cmd.description or reference.description
        reference.url = cmd.url or reference.url
        reference.external_id = cmd.external_id or reference.external_id
        await uow.commit()

@handlers.command_handler(commands.references.UpdateExternalDataReference)
async def update_external_data(
    cmd: commands.references.UpdateExternalDataReference,
    uow_factory: AbstractUnitOfWorkFactory
) -> None:
    logger.debug(f'f"Updating external data reference for user {cmd.agent_id}')
    schema = parse_json_schema(cmd.json_schema)
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        reference: ExternalDataStored = await uow.repositories.references.get(reference_id = cmd.reference_id)
        reference.description = cmd.description or reference.description
        reference.url = cmd.url or reference.url
        reference.external_id = cmd.external_id or reference.external_id
        reference.schema = schema or reference.schema
        reference.format = cmd.format or reference.format
        if cmd.contributions is not None:
            contributions = _contributions(cmd)
            await verify_contributions(uow, contributions, stored=reference.contributions)
            reference.contributions = contributions
        await uow.commit()

@handlers.command_handler(commands.references.UpdateFileReference)
async def update_file_reference(
    cmd: commands.references.UpdateFileReference,
    uow_factory: AbstractUnitOfWorkFactory
) -> None:
    logger.debug(f'f"Updating local data reference for user {cmd.agent_id}')
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        reference: FileReferenceStored = await uow.repositories.references.get(reference_id = cmd.reference_id)
        reference.description = cmd.description or reference.description
        reference.filename = cmd.filename or reference.filename
        reference.content_type = cmd.content_type or reference.content_type
        reference.file_id = cmd.uuid or reference.file_id
        if cmd.contributions is not None:
            contributions = _contributions(cmd)
            await verify_contributions(uow, contributions, stored=reference.contributions)
            reference.contributions = contributions
        await uow.commit()

@handlers.command_handler(commands.references.UpdateDataFileReference)
async def update_data_file_reference(
    cmd: commands.references.UpdateDataFileReference,
    uow_factory: AbstractUnitOfWorkFactory
) -> None:
    logger.debug(f'f"Updating local data reference for user {cmd.agent_id}')
    schema = parse_json_schema(cmd.json_schema)
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        reference: DataFileStored = await uow.repositories.references.get(reference_id = cmd.reference_id)
        reference.description = cmd.description or reference.description
        reference.filename = cmd.filename or reference.filename
        reference.content_type = cmd.content_type or reference.content_type
        reference.file_id = cmd.uuid or reference.file_id
        reference.schema = schema or reference.schema
        reference.format = cmd.format or reference.format
        if cmd.contributions is not None:
            contributions = _contributions(cmd)
            await verify_contributions(uow, contributions, stored=reference.contributions)
            reference.contributions = contributions
        await uow.commit()

@handlers.command_handler(commands.references.DeleteReferences)
async def delete_reference(
    cmd: commands.references.DeleteReferences,
    uow_factory: AbstractUnitOfWorkFactory
) -> None:
    logger.debug(f'f"Deleting references {cmd.reference_ids}')
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        repo = uow.repositories.references
        async for reference in repo.get_all(reference_ids=cmd.reference_ids):
            if await uow.guards.reference_in_use(reference.id):
                raise IllegalOperationError(f"Reference {reference.id} is in use")

            if isinstance(reference, FileReferenceStored) and reference.file_id is not None:
                event = events.references.FileReferenceDeleted(
                    uuid=reference.file_id
                )
                reference.events.append(event)

            await repo.remove(reference)
        await uow.commit()
