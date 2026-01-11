from enum import Enum
from .base import Command
from typing import List

class DataFormat(Enum):
    JSON = "json"
    HDF5 = "hdf5"
    CSV = "csv"
    TSV = "tsv"

class CreateLegalReference(Command):
    agent_id: int
    description: str | None = None
    
    text: str

class CreateExternalReference(Command):
    agent_id: int
    description: str | None = None
    
    url: str
    external_id: str | None = None

class CreateExternalDataReference(Command):
    agent_id: int
    description: str | None = None
    
    url: str
    external_id: str | None = None

    format: DataFormat | None = None
    json_schema: str | None = None

class CreateFileReference(Command):
    agent_id: int
    description: str | None = None

    filename: str
    uuid: str | None
    
class CreateDataFileReference(Command):
    agent_id: int
    description: str | None = None

    filename: str
    uuid: str | None

    format: DataFormat | None = None
    json_schema: str | None = None


class UpdateLegalReference(Command):
    agent_id: int
    reference_id: int

    description: str | None = None

    text: str | None = None


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


class UpdateFileReference(Command):
    agent_id: int
    reference_id: int

    description: str | None = None

    filename: str | None = None
    uuid: str | None = None

class UpdateDataFileReference(Command):
    agent_id: int
    reference_id: int

    description: str | None = None

    filename: str | None = None
    uuid: str | None = None

    format: DataFormat | None = None
    json_schema: str | None = None


class DeleteReferences(Command):
    agent_id: int
    reference_ids: List[int]
