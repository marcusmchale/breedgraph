import asyncio
from datetime import datetime

from fastapi import UploadFile

from breedgraph.config import LEGAL_FILE_SIZE_LIMIT
from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.archive import FileArchivalRecord, LocalState, ArchiveState
from breedgraph.service_layer.infrastructure.legal_files import LegalText, LegalFileInvalid, read_legal_file
from breedgraph.service_layer.messagebus import MessageBus
from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from breedgraph.domain.commands.references import (
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
from breedgraph.domain.commands.archive import RequestFileRestore
from breedgraph.domain.events.references import (
    UploadFailed,
    UploadCompleted
)


from typing import List

import logging
logger = logging.getLogger(__name__)

from . import graphql_mutation

# We don't want to pass the UploadFile to the bus,
# so just pass in callbacks to raise events and create a new task on the process
def start_creating_file(user_id:int, bus: MessageBus, key: str, reference_id: int, file: UploadFile):
    async def on_complete(file_size: int, file_hash: str, *args, **kwargs):
        logger.debug(f'file saving complete for uuid: {key}')
        await bus.handle(
            UploadCompleted(
                user_id=user_id,
                uuid=key,
                reference_id=reference_id,
                file_size=file_size,
                file_hash=file_hash
            )
        )

    async def on_failed(*args, **kwargs):
        logger.error(f'file saving failed for uuid: {key}')
        await bus.handle(
            UploadFailed(
                user_id=user_id,
                uuid=key,
                reference_id=reference_id
            )
        )

    asyncio.create_task(bus.file_management.save_file(
        uuid=key,
        file=file,
        on_complete=on_complete,
        on_failed=on_failed
    ))

def start_updating_file(
        user_id: int,
        bus: MessageBus,
        key: str,
        reference_id: int,
        file: UploadFile,
        cmd: UpdateFileReference | UpdateDataFileReference | UpdateLegalReference
):
    # if there is a file, then don't perform the update until after the file is saved
    # otherwise the reference may be in an inconsistent state,
    # e.g. filename would be updated but points to the old file

    fail_event = UploadFailed(user_id=user_id, uuid=key, reference_id=reference_id)

    async def on_complete(file_size:int, file_hash:str, *args, **kwargs):
        try:
            await bus.handle(cmd)
            await bus.handle(
                UploadCompleted(
                    user_id=user_id,
                    uuid=key,
                    reference_id=reference_id,
                    file_size=file_size,
                    file_hash=file_hash
                )
            )
        except Exception as e:
            logger.error(f"Failed to update file reference: {e}")
            await bus.handle(fail_event)

    async def on_failed(*args, **kwargs):
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
        cmd: UpdateFileReference | UpdateDataFileReference | UpdateLegalReference
):
    if not file:
        await bus.handle(cmd)
        return None
    else:
        if not file.filename:
            raise ValueError("File must have a name")

        bus.file_management.require_capacity()
        key = await bus.state_store.store_file(
            agent_id=user_id,
            filename=file.filename,
            reference_id=reference_id
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
        reference: dict,
        control_team_id: int | None = None,
        release: ReadRelease = ReadRelease.PRIVATE
) -> int:
    user_id = info.context.get('user_id')
    logger.debug(f'User {user_id} creates legal reference')
    cmd = CreateLegalReference(agent_id=user_id, write_team=control_team_id, release=release, **reference)
    reference_id: int = await info.context['bus'].handle(cmd)
    return reference_id


# Reading a legal file is quick unless it is made to be slow, which the request should not wait out
LEGAL_FILE_READ_SECONDS = 30

async def read_legal_upload(file: UploadFile | None) -> LegalText:
    """
    A legal file's text, checked before anything is stored, so a wrong file is refused at once. The upload is read
    from the start again afterwards, to be saved as other files are.
    """
    if not file or not file.filename:
        raise LegalFileInvalid("A legal reference's file is required, with its name")
    data = await file.read(LEGAL_FILE_SIZE_LIMIT + 1)
    await file.seek(0)
    try:
        return await asyncio.wait_for(asyncio.to_thread(read_legal_file, file.filename, data), LEGAL_FILE_READ_SECONDS)
    except asyncio.TimeoutError:
        raise LegalFileInvalid(f"{file.filename} took too long to read: give its text as a .txt or .md file")


@graphql_mutation.field("referencesCreateLegalFile")
@graphql_payload
@require_authentication
async def create_legal_file_reference(
        _,
        info,
        reference: dict,
        control_team_id: int | None = None,
        release: ReadRelease = ReadRelease.PRIVATE
) -> str:
    """A legal reference with the text of a .txt, .md or .pdf file; the file is saved and archived as others are"""
    user_id = info.context.get('user_id')
    bus: MessageBus = info.context.get('bus')
    logger.debug(f'User {user_id} creates legal reference from a file')
    file: UploadFile | None = reference.get('file')
    bus.file_management.require_capacity()
    legal_text = await read_legal_upload(file)
    key = await bus.state_store.store_file(agent_id=user_id, filename=file.filename)
    await bus.handle(CreateLegalReference(
        agent_id=user_id,
        write_team=control_team_id,
        release=release,
        description=reference.get('description') or file.filename,
        text=legal_text.text,
        text_format=legal_text.text_format,
        content_hash=legal_text.content_hash,
        filename=file.filename,
        content_type=legal_text.content_type,
        uuid=key
    ))
    reference_id = await bus.state_store.get_file_reference_id(key)
    if not reference_id:
        raise ValueError("File reference id is invalid")
    start_creating_file(user_id=user_id, bus=bus, key=key, reference_id=reference_id, file=file)
    return key


@graphql_mutation.field("referencesCreateExternal")
@graphql_payload
@require_authentication
async def create_external_reference(
        _,
        info,
        reference: dict,
        control_team_id: int | None = None,
        release: ReadRelease = ReadRelease.PRIVATE
) -> int:
    user_id = info.context.get('user_id')
    logger.debug(f'User {user_id} creates external reference')
    cmd = CreateExternalReference(agent_id=user_id, write_team=control_team_id, release=release, **reference)
    reference_id: int = await info.context['bus'].handle(cmd)
    return reference_id

@graphql_mutation.field("referencesCreateExternalData")
@graphql_payload
@require_authentication
async def create_external_data_reference(
        _,
        info,
        reference: dict,
        control_team_id: int | None = None,
        release: ReadRelease = ReadRelease.PRIVATE
) -> int:
    user_id = info.context.get('user_id')
    logger.debug(f'User {user_id} creates external data reference')
    json_schema = reference.pop('schema')
    cmd = CreateExternalDataReference(
        agent_id=user_id,
        write_team=control_team_id,
        release=release,
        json_schema=json_schema,
        **reference
    )
    reference_id: int = await info.context['bus'].handle(cmd)
    return reference_id


@graphql_mutation.field("referencesCreateFile")
@graphql_payload
@require_authentication
async def create_file_reference(
        _,
        info,
        reference: dict,
        control_team_id: int | None = None,
        release: ReadRelease = ReadRelease.PRIVATE
) -> str:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    logger.debug(f'User {user_id} creating file reference')

    file: UploadFile | None = reference.get('file')
    if not file:
        raise ValueError("File upload is required for creating a file reference")
    if not file.filename:
        raise ValueError("File must have name")
    if not file.content_type:
        raise ValueError("File must have content type")

    bus.file_management.require_capacity()
    key = await bus.state_store.store_file(
        agent_id=user_id,
        filename=file.filename
    )

    cmd = CreateFileReference(
        agent_id=user_id,
        write_team=control_team_id,
        release=release,
        description=reference.get('description'),
        filename=file.filename,
        content_type=file.content_type,
        uuid=key,
        contributions=reference.get('contributions')
    )
    await bus.handle(cmd)
    # get the reference id from the state store
    bus: MessageBus = info.context.get('bus')
    reference_id = await bus.state_store.get_file_reference_id(key)
    if not reference_id:
        raise ValueError("File reference id is invalid")

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
        reference: dict,
        control_team_id: int | None = None,
        release: ReadRelease = ReadRelease.PRIVATE
) -> str:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    logger.debug(f'User {user_id} creates data file reference')

    file: UploadFile | None = reference.get('file')
    if not file:
        raise ValueError("File upload is required for creating a data file reference")
    if not file.filename:
        raise ValueError("File must have name")
    if not file.content_type:
        raise ValueError("File must have content type")

    bus.file_management.require_capacity()
    key = await bus.state_store.store_file(
        agent_id=user_id,
        filename=file.filename
    )
    cmd = CreateDataFileReference(
        agent_id=user_id,
        write_team=control_team_id,
        release=release,
        description=reference.get('description'),
        filename=file.filename,
        content_type=file.content_type,
        format=reference.get('format'),
        json_schema=reference.get('schema'),
        uuid=key,
        contributions=reference.get('contributions')
    )

    await bus.handle(cmd)
    bus: MessageBus = info.context.get('bus')
    reference_id = await bus.state_store.get_file_reference_id(key)
    if not reference_id:
        raise ValueError("File reference id is invalid")

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
    reference['reference_id'] = reference.pop('id')
    cmd = UpdateLegalReference(agent_id=user_id, **reference)
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("referencesUpdateLegalFile")
@graphql_payload
@require_authentication
async def update_legal_file_reference(
        _,
        info,
        reference: dict
) -> str:
    """New text from a .txt, .md or .pdf file, applied with the file once it is saved"""
    user_id = info.context.get('user_id')
    bus: MessageBus = info.context.get('bus')
    logger.debug(f'User {user_id} updates legal reference from a file')
    file: UploadFile | None = reference.get('file')
    legal_text = await read_legal_upload(file)
    cmd = UpdateLegalReference(
        agent_id=user_id,
        reference_id=reference.get('id'),
        description=reference.get('description'),
        text=legal_text.text,
        text_format=legal_text.text_format,
        content_hash=legal_text.content_hash,
        filename=file.filename,
        content_type=legal_text.content_type
    )
    return await start_file_ref_update(user_id=user_id, bus=bus, reference_id=reference.get('id'), file=file, cmd=cmd)


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
    reference['reference_id'] = reference.pop('id')
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
    reference['reference_id'] = reference.pop('id')
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
        reference_id=reference.get('id'),
        description=reference.get('description'),
        filename=file.filename if file else None,
        content_type = file.content_type if file else None,
        contributions=reference.get('contributions')
    )
    key = await start_file_ref_update(
        user_id=user_id,
        bus=bus,
        reference_id=reference.get('id'),
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
        reference_id=reference.get('id'),
        description=reference.get('description'),
        filename=file.filename if file else None,
        content_type=file.content_type if file else None,
        format=reference.get('format'),
        json_schema=reference.get('schema'),
        contributions=reference.get('contributions')
    )
    key = await start_file_ref_update(
        user_id=user_id,
        bus=bus,
        reference_id=reference.get('id'),
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
        ids: List[int]
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f'User {user_id} deletes references {ids}')
    cmd = DeleteReferences(agent_id=user_id, reference_ids=ids)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("referencesRequestFileRetrieval")
@graphql_payload
@require_authentication
async def request_file_retrieval(
        _,
        info,
        file_id: str
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f'User {user_id} requesting retrieval of file {file_id}')
    cmd = RequestFileRestore(file_id=file_id, agent_id=user_id)
    await info.context['bus'].handle(cmd)
    return True
