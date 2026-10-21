from breedgraph.domain.model.contributions import ContributionInput
from breedgraph.domain.model.references import DataFormat, TextFormat
from breedgraph.domain.model.controls import ReadRelease

from .base import Command

class CreateLegalReference(Command):
    agent_id: int
    write_team: int
    release: ReadRelease = ReadRelease.PRIVATE

    description: str | None = None

    text: str
    text_format: TextFormat = TextFormat.PLAIN

    # read from a file: its hash, name and content type, and its key in the state store, which UploadCompleted links
    # to the reference once the file is saved. Typed text is hashed itself.
    content_hash: str | None = None
    filename: str | None = None
    content_type: str | None = None
    uuid: str | None = None

class CreateExternalReference(Command):
    agent_id: int
    write_team: int
    release: ReadRelease = ReadRelease.PRIVATE

    description: str | None = None
    
    url: str
    external_id: str | None = None

class CreateExternalDataReference(Command):
    agent_id: int
    write_team: int
    release: ReadRelease = ReadRelease.PRIVATE

    description: str | None = None
    
    url: str
    external_id: str | None = None

    format: DataFormat | None = None
    json_schema: str | None = None

    # the Persons credited, with the roles they had; on update, replaces them all
    contributions: list[ContributionInput] | None = None


class CreateFileReference(Command):
    agent_id: int
    write_team: int
    release: ReadRelease = ReadRelease.PRIVATE

    description: str | None = None

    filename: str
    content_type: str
    uuid: str
    

    # the Persons credited, with the roles they had; on update, replaces them all
    contributions: list[ContributionInput] | None = None


class CreateDataFileReference(Command):
    agent_id: int
    write_team: int
    release: ReadRelease = ReadRelease.PRIVATE

    description: str | None = None

    filename: str
    content_type: str
    uuid: str | None

    format: DataFormat | None = None
    json_schema: str | None = None

    # the Persons credited, with the roles they had; on update, replaces them all
    contributions: list[ContributionInput] | None = None


class UpdateLegalReference(Command):
    agent_id: int
    reference_id: int

    description: str | None = None

    # typed text replaces a file the reference was given as; with a filename, it was read from a new file
    text: str | None = None
    text_format: TextFormat | None = None
    content_hash: str | None = None
    filename: str | None = None
    content_type: str | None = None


class UpdateExternalReference(Command):
    agent_id: int
    reference_id: int

    description: str | None = None

    url: str | None = None
    external_id: str | None = None


class UpdateExternalDataReference(Command):
    agent_id: int
    reference_id: int

    description: str | None = None

    url: str | None = None
    external_id: str | None = None

    format: DataFormat | None = None
    json_schema: str | None = None

    # the Persons credited, with the roles they had; on update, replaces them all
    contributions: list[ContributionInput] | None = None


class UpdateFileReference(Command):
    agent_id: int
    reference_id: int

    description: str | None = None

    filename: str | None = None
    content_type: str | None = None
    uuid: str | None = None

    # the Persons credited, with the roles they had; on update, replaces them all
    contributions: list[ContributionInput] | None = None


class UpdateDataFileReference(Command):
    agent_id: int
    reference_id: int

    description: str | None = None

    filename: str | None = None
    content_type: str | None = None
    uuid: str | None = None

    format: DataFormat | None = None
    json_schema: str | None = None

    # the Persons credited, with the roles they had; on update, replaces them all
    contributions: list[ContributionInput] | None = None


class DeleteReferences(Command):
    agent_id: int
    reference_ids: list[int]
