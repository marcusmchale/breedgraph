from ariadne import ObjectType, UnionType, InterfaceType, EnumType
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime, timedelta

from breedgraph.adapters.redis.state_store import SubmissionStatus

from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import get_context_views, get_context_lock


from breedgraph.domain.model.references import (
    ReferenceType,
    ReferenceStoredBase,
    LegalReferenceStored,
    ExternalReferenceStored,
    ExternalDataStored,
    FileReferenceStored,
    DataFileStored
)
from breedgraph.domain.model.archive import FileArchivalRecord, LocalState, ArchiveState

from breedgraph.custom_exceptions import UnauthorisedOperationError, NoResultFoundError

from breedgraph.config import SECRET_KEY, FILE_DOWNLOAD_EXPIRES, FILE_DOWNLOAD_SALT, get_download_endpoint


from typing import List

import logging
logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers

legal_reference = ObjectType("LegalReference")
external_reference = ObjectType("ExternalReference")
external_data_reference = ObjectType("ExternalDataReference")
file_reference = ObjectType("FileReference")
data_file_reference = ObjectType("DataFileReference")

reference_union = UnionType("ReferenceUnion")
reference_interface = InterfaceType("ReferenceInterface")

file_submission = ObjectType("FileSubmission")
file_download = ObjectType("FileDownload")

graphql_resolvers.register_type_resolvers(
    legal_reference, external_reference, external_data_reference, file_reference, data_file_reference,
    reference_union, reference_interface,
    file_submission, file_download
)
graphql_resolvers.register_enums(
    EnumType("SubmissionStatus", SubmissionStatus),
    EnumType("ReferenceType", ReferenceType)
)

def resolve_type(obj) -> str:
    if hasattr(obj, 'text'):
        return "LegalReference"
    elif hasattr(obj, 'url'):
        if hasattr(obj, 'format'):
            return "ExternalDataReference"
        else:
            return "ExternalReference"
    elif hasattr(obj, 'filename'):
        if hasattr(obj, 'format'):
            return "DataFileReference"
        else:
            return "FileReference"
    else:
        raise ValueError(f"Could not determine type for object: {obj}")

@reference_union.type_resolver
def resolve_reference_type(obj, *_):
    return resolve_type(obj)

@reference_interface.type_resolver
def resolve_reference_interface_type(obj, *_):
    return resolve_type(obj)

"""References by id: a placeholder for those the user cannot read (see docs/read-access.md)"""
@graphql_query.field("references")
@graphql_payload
async def get_references(_, info, ids: List[int]) -> List[ReferenceStoredBase]:
    async with get_context_lock(info.context):
        views = await get_context_views(info.context)
        return await views.references.get_references(ids)


"""References whose description matches: only those the user can read"""
@graphql_query.field("referencesSearch")
@graphql_payload
async def find_references(
        _,
        info,
        description: str,
        reference_types: list[ReferenceType]|None = None
) -> List[ReferenceStoredBase]:
    async with get_context_lock(info.context):
        views = await get_context_views(info.context)
        return await views.references.search_references(description, reference_types)


@external_data_reference.field("format")
async def resolve_data_format(obj, *_):
    return obj.format.value

@data_file_reference.field("format")
async def resolve_data_format(obj, *_):
    return obj.format.value

"""Resolve recently uploaded file/data-file references for use in dataset submission workflows"""
@graphql_query.field("referencesRecentFiles")
@graphql_payload
@require_authentication
async def get_recent_file_references(
        _,
        info,
        reference_types: list[ReferenceType]|None = None
) -> List[ReferenceStoredBase]:
    bus = info.context['bus']
    reference_ids = await bus.state_store.get_user_file_reference_ids(user_id=info.context['user_id'])
    async with get_context_lock(info.context):
        views = await get_context_views(info.context)
        references = await views.references.get_references(reference_ids)
    return [reference for reference in references if not reference_types or reference.type in reference_types]

@graphql_query.field("referencesFileSubmission")
@graphql_payload
@require_authentication
async def get_file_submission(_, info, file_id: str) -> str:
    user_id = info.context.get('user_id')
    bus = info.context['bus']
    await bus.state_store.verify_agent(agent_id=user_id, key=file_id)
    return file_id

@file_submission.field("referenceId")
async def get_file_reference_id(file_id, info) -> int:
    bus = info.context['bus']
    reference_id = await bus.state_store.get_file_reference_id(file_id)
    return reference_id

@file_submission.field("status")
async def get_file_status(file_id, info) -> SubmissionStatus:
    bus = info.context['bus']
    status = await bus.state_store._get_status(file_id)
    return status

@file_submission.field("progress")
async def get_file_progress(file_id, info) -> int:
    bus = info.context['bus']
    progress = await bus.state_store._get_file_progress(file_id)
    return progress

@file_submission.field("errors")
async def get_file_errors(file_id, info) -> List[str]:
    bus = info.context['bus']
    errors = await bus.state_store._get_errors(file_id)
    return errors

async def _readable_file_reference(info, file_id: str) -> FileReferenceStored | DataFileStored | None:
    """
    The file reference for a stored file, None when there is none, refused when the user cannot read it: a file is
    downloadable by anyone who can read its reference, anonymous users included for public ones
    """
    async with get_context_lock(info.context):
        views = await get_context_views(info.context)
        reference = await views.references.get_file_reference(file_id)
    if reference is not None and reference.file_id is None:
        # a placeholder, which never carries the file id
        raise UnauthorisedOperationError("You do not have access to read this file")
    return reference

@graphql_query.field("referencesFileDownloadState")
@graphql_payload
async def get_file_download_state(_, info, file_id: str):
    """
     Check if the file download request is registered
     Return a FileDownloadRequest object
    """
    user_id = info.context.get('user_id')
    logger.debug(f'User {user_id} requesting download of file {file_id}')
    if await _readable_file_reference(info, file_id) is None:
        raise NoResultFoundError(f"Reference with file ID {file_id} not found")
    bus = info.context['bus']
    archival_service = bus.archival_service
    record: FileArchivalRecord = await archival_service.get(file_id)
    if record.local_state == LocalState.LOCAL:
        status = "AVAILABLE"
        recovery = None
    else:
        if record.archive_state == ArchiveState.ARCHIVED:
            status = "ARCHIVED"
            recovery = {
                "startedAt": datetime.now(),
                "progress": 0
            }
        elif record.archive_state == ArchiveState.RETRIEVAL_PENDING:
            status = "RETRIEVING"
            recovery = {
                "startedAt": datetime.now(),
                "progress": 0
            }
        elif record.archive_state == ArchiveState.RETRIEVING:
            status = "RETRIEVING"
            recovery = {
                "startedAt": record.last_attempt_at,
                "progress": record.local_completion
            }
        else:
            status = "FAILED"
            recovery = {
                "startedAt": record.last_attempt_at,
                "progress": record.local_completion
            }

    return {
        "status": status,
        "recovery": recovery
    }


@graphql_query.field("referencesFileDownload")
@graphql_payload
async def get_file_download(_, info, file_id: str):
    user_id = info.context.get('user_id')
    bus = info.context['bus']
    reference = await _readable_file_reference(info, file_id)
    if reference is None:
        # Check if the user's own upload is still in progress
        status = await bus.state_store.get_status(agent_id=user_id, key=file_id) if user_id is not None else None
        if status and status is not SubmissionStatus.COMPLETED:
            if status in [SubmissionStatus.PENDING, SubmissionStatus.PROCESSING]:
                raise NoResultFoundError("The file upload is still in progress")
            elif status == SubmissionStatus.FAILED:
                raise NoResultFoundError("The requested file failed to upload successfully")
            else:
                raise ValueError("Unexpected error. The file reference is in an unknown state")
        raise ValueError(f"Reference with file ID {file_id} not found")

    file_details = {
        'uuid': reference.file_id,
        'filename': reference.filename,
        'contentType': reference.content_type
    }

    token = URLSafeTimedSerializer(SECRET_KEY).dumps(
        file_details,
        salt=FILE_DOWNLOAD_SALT
    )

    return {
        'expires_at': datetime.now() + timedelta(minutes=FILE_DOWNLOAD_EXPIRES),
        'url': f'{get_download_endpoint()}{token}'
    }
