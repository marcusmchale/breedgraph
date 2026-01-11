import asyncio
from fastapi import UploadFile

from src.breedgraph.service_layer.messagebus import MessageBus
from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.domain.commands.references import (
    CreateLegalReference,
    CreateExternalReference,
    CreateExternalDataReference,
    CreateFileReference,
    CreateDataFileReference,
    UpdateLegalReference,
    UpdateExternalReference,
    UpdateExternalDataReference,
    UpdateFileReference,
    UpdateDataFileReference,
    DeleteReferences
)
from src.breedgraph.domain.events.references import (
    UploadFailed,
    UploadCompleted
)

from typing import List

import logging
logger = logging.getLogger(__name__)

from . import graphql_mutation


def start_creating_file(user_id:int, bus: MessageBus, key: str, reference_id: int, file: UploadFile):
    # sets the uuid and notifies user
    success_event = UploadCompleted(user_id=user_id, uuid=key, reference_id=reference_id)
    async def on_complete():
        logger.debug(f'file saving complete for uuid: {key}')
        await bus.handle(success_event)
    # removes the file and notifies user
    fail_event = UploadFailed(user_id=user_id, uuid=key, reference_id=reference_id)
    async def on_failed():
        logger.debug(f'file saving failed for uuid: {key}')
        await bus.handle(fail_event)

    asyncio.create_task(bus.file_management.save_file(
        uuid=key,
        file = file,
        on_complete=on_complete,
        on_failed=on_failed
    ))

def start_updating_file(
        user_id: int,
        bus: MessageBus,
        key: str,
        reference_id: int,
        file: UploadFile,
        cmd: UpdateFileReference | UpdateDataFileReference
):
    # if there is a file, then don't perform the update until after the file is saved
    # otherwise the reference may be in an inconsistent state,
    # e.g. filename would be updated but points to the old file
    success_event = UploadCompleted(user_id=user_id, uuid=key, reference_id=reference_id)
    fail_event = UploadFailed(user_id=user_id, uuid=key, reference_id=reference_id)

    async def on_complete():
        try:
            await bus.handle(cmd)
            await bus.handle(success_event)
        except Exception as e:
            logger.error(f"Failed to update file reference: {e}")
            await bus.handle(fail_event)

    async def on_failed():
        await bus.handle(fail_event)

    asyncio.create_task(bus.file_management.save_file(
        uuid=key,
        file=file,
        on_complete=on_complete,
        on_failed=on_failed
    ))

async def start_file_ref_update(
        user_id: int,
        bus: MessageBus,
        reference_id: int,
        file: UploadFile,
        cmd: UpdateFileReference | UpdateDataFileReference
):
    if not file:
        await bus.handle(cmd)
        return None
    else:
        key = await bus.state_store.store_file(
            agent_id=user_id,
            filename=file.filename
        )
        start_updating_file(
            user_id=user_id,
            bus=bus,
            key=key,
            reference_id=reference_id,
            file=file,
            cmd=cmd
        )
        return key


@graphql_mutation.field("referencesCreateLegal")
@graphql_payload
@require_authentication
async def create_legal_reference(
        _,
        info,
        reference: dict
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f'User {user_id} creates legal reference')
    cmd = CreateLegalReference(agent_id=user_id, **reference)
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("referencesCreateExternal")
@graphql_payload
@require_authentication
async def create_external_reference(
        _,
        info,
        reference: dict
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f'User {user_id} creates external reference')
    cmd = CreateExternalReference(agent_id=user_id, **reference)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("referencesCreateExternalData")
@graphql_payload
@require_authentication
async def create_external_data_reference(
        _,
        info,
        reference: dict
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f'User {user_id} creates external data reference')
    json_schema = reference.pop('schema')
    cmd = CreateExternalDataReference(agent_id=user_id, **reference, json_schema=json_schema)
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("referencesCreateFile")
@graphql_payload
@require_authentication
async def create_file_reference(
        _,
        info,
        reference: dict
) -> str:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    logger.debug(f'User {user_id} creating file reference')

    file: UploadFile = reference.get('file')

    key = await bus.state_store.store_file(
        agent_id=user_id,
        filename=file.filename
    )
    cmd = CreateFileReference(
        agent_id=user_id,
        description=reference.get('description'),
        filename=file.filename,
        uuid=key
    )
    await bus.handle(cmd)
    # get the reference id from the state store
    bus: MessageBus = info.context.get('bus')
    reference_id = await bus.state_store.get_file_reference_id(key)
    start_creating_file(
        user_id=user_id,
        bus=bus,
        key=key,
        reference_id=reference_id,
        file=file
    )
    return key

@graphql_mutation.field("referencesCreateDataFile")
@graphql_payload
@require_authentication
async def create_data_file_reference(
        _,
        info,
        reference: dict
) -> str:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    logger.debug(f'User {user_id} creates data file reference')

    file = reference.get('file')
    key = await bus.state_store.store_file(
        agent_id=user_id,
        filename=file.filename
    )
    cmd = CreateDataFileReference(
        agent_id=user_id,
        description=reference.get('description'),
        filename=file.filename,
        format=reference.get('format'),
        json_schema=reference.get('schema'),
        uuid=key
    )
    await bus.handle(cmd)
    bus: MessageBus = info.context.get('bus')
    reference_id = await bus.state_store.get_file_reference_id(key)
    start_creating_file(
        user_id=user_id,
        bus=bus,
        key=key,
        reference_id=reference_id,
        file=file
    )
    return key

@graphql_mutation.field("referencesUpdateLegal")
@graphql_payload
@require_authentication
async def update_legal_reference(
        _,
        info,
        reference: dict
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f'User {user_id} updates legal reference')
    cmd = UpdateLegalReference(agent_id=user_id, **reference)
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("referencesUpdateExternal")
@graphql_payload
@require_authentication
async def update_external_reference(
        _,
        info,
        reference: dict
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f'User {user_id} updates external reference')
    cmd = UpdateExternalReference(agent_id=user_id, **reference)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("referencesUpdateExternalData")
@graphql_payload
@require_authentication
async def update_external_data_reference(
        _,
        info,
        reference: dict
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f'User {user_id} updates external data reference')
    json_schema = reference.pop('schema')
    cmd = UpdateExternalDataReference(agent_id=user_id, **reference, json_schema=json_schema)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("referencesUpdateFile")
@graphql_payload
@require_authentication
async def update_file_reference(
        _,
        info,
        reference: dict
) -> str | None:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    logger.debug(f"User {user_id} updates file reference")
    file = reference.get('file')
    cmd = UpdateFileReference(
        agent_id=user_id,
        reference_id=reference.get('reference_id'),
        description=reference.get('description'),
        filename=file.filename if file else None
    )
    key = await start_file_ref_update(
        user_id=user_id,
        bus=bus,
        reference_id=reference.get('reference_id'),
        file=file,
        cmd=cmd
    )
    return key

@graphql_mutation.field("referencesUpdateDataFile")
@graphql_payload
@require_authentication
async def update_file_data_reference(
        _,
        info,
        reference: dict
) -> str | None:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    logger.debug(f"User {user_id} updates data file reference")
    file = reference.get('file')
    cmd = UpdateDataFileReference(
        agent_id=user_id,
        reference_id=reference.get('reference_id'),
        description=reference.get('description'),
        filename=file.filename if file else None,
        format=reference.get('format'),
        json_schema=reference.get('schema')
    )
    key = await start_file_ref_update(
        user_id=user_id,
        bus=bus,
        reference_id=reference.get('reference_id'),
        file=file,
        cmd=cmd
    )
    return key

@graphql_mutation.field("referencesDelete")
@graphql_payload
@require_authentication
async def delete_references(
        _,
        info,
        reference_ids: List[int]
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f'User {user_id} updates legal reference')
    cmd = DeleteReferences(agent_id=user_id, reference_ids=reference_ids)
    await info.context['bus'].handle(cmd)
    return True
