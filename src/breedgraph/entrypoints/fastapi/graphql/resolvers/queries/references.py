from ariadne import ObjectType, UnionType, InterfaceType
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime, timedelta

from src.breedgraph.service_layer.application.access_control import AbstractAccessControlService

from src.breedgraph.adapters.redis.state_store import SubmissionStatus

from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication


from src.breedgraph.domain.model.controls import (
    Controller, ReadRelease, Access, ControlledModelLabel
)

from src.breedgraph.domain.model.references import (
    ReferenceStoredBase,
    LegalReferenceStored,
    ExternalReferenceStored,
    ExternalDataStored,
    FileReferenceStored,
    DataFileStored
)

from src.breedgraph.custom_exceptions import UnauthorisedOperationError, NoResultFoundError

from src.breedgraph.config import SECRET_KEY, FILE_DOWNLOAD_EXPIRES, FILE_DOWNLOAD_SALT, get_download_endpoint

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
graphql_resolvers.register_enums(SubmissionStatus)

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

"""References resolver by ID list"""
@graphql_query.field("references")
@graphql_payload
@require_authentication
async def get_references(_, info, reference_ids: List[int]) -> List[ReferenceStoredBase]:
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    async with bus.uow.get_uow(user_id=user_id) as uow:
        references = [reference async for reference in uow.repositories.references.get_all(reference_ids=reference_ids)]
        return references


"""References resolver by query string"""
@graphql_query.field("referencesDescription")
@graphql_payload
@require_authentication
async def get_references_by_description(_, info, description: str) -> List[ReferenceStoredBase]:
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    async with bus.uow.get_uow(user_id=user_id) as uow:
        references = [reference async for reference in uow.repositories.references.get_all(description=description)]
        return references


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
async def get_recent_file_references(_, info) -> List[ReferenceStoredBase]:
    bus = info.context['bus']
    reference_ids = await bus.state_store.get_user_file_reference_ids(user_id=info.context['user_id'])
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    async with bus.uow.get_uow(user_id=user_id) as uow:
        references = [reference async for reference in uow.repositories.references.get_all(reference_ids=reference_ids)]
        return references

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
    status = await bus.state_store._get_file_status(file_id)
    return status

@file_submission.field("progress")
async def get_file_progress(file_id, info) -> int:
    bus = info.context['bus']
    progress = await bus.state_store._get_file_progress(file_id)
    return progress

@file_submission.field("errors")
async def get_file_errors(file_id, info) -> List[str]:
    bus = info.context['bus']
    errors = await bus.state_store._get_file_errors(file_id)
    return errors

@graphql_query.field("referencesFileDownload")
@graphql_payload
@require_authentication
async def get_file_download(_, info, file_id: str):
    user_id = info.context.get('user_id')
    bus = info.context['bus']
    async with bus.uow.get_uow(user_id) as uow:
        reference: FileReferenceStored | DataFileStored = await uow.repositories.references.get(file_id=file_id)
        if not reference:
            # Check if the upload is still in progress
            status = await bus.state_store.get_file_status(agent_id=user_id, file_id=file_id)
            if status and status is not SubmissionStatus.COMPLETED:
                if status in [SubmissionStatus.PENDING, SubmissionStatus.PROCESSING]:
                    raise NoResultFoundError("The file upload is still in progress")
                elif status == SubmissionStatus.FAILED:
                    raise NoResultFoundError("The requested file failed to upload successfully")
                else:
                    raise ValueError("Unexpected error. The file reference is in an unknown state")
            raise ValueError(f"Reference with file ID {file_id} not found")

        if not reference.file_id:
            # The user has probably requested a file that they do not have access to
            # The query allows to see that the reference exists and get the reference ID, but not see other details
            # Confirm the user does not have access before returning the error message.
            controls: AbstractAccessControlService = uow.controls
            controller: Controller = await controls.get_controller(
                label=ControlledModelLabel.REFERENCE,
                model_id=reference.id
            )
            has_access = controller.has_access(
                access=Access.READ,
                user_id=user_id,
                access_teams=controls.access_teams.get(Access.READ)
            )
            if not has_access:
                raise UnauthorisedOperationError("The requesting user does not have access to read this reference")
            else:
                raise ValueError("Unexpected error. The file reference is missing a UUID")


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
            'filename': reference.filename,
            'content_type': reference.content_type,
            'token': token,
            'expires_at': datetime.now() + timedelta(minutes=FILE_DOWNLOAD_EXPIRES),
            'url': f'{get_download_endpoint()}{token}'
        }
