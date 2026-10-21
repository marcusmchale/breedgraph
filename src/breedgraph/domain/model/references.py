from abc import ABC, abstractmethod
from dataclasses import dataclass, replace, field
from enum import Enum
import hashlib
import json

from breedgraph.service_layer.tracking.wrappers import asdict
from breedgraph.domain.model.base import StoredModel, EnumLabeledModel, LabeledModel
from breedgraph.domain.model.contributions import Contribution
from breedgraph.domain.model.controls import (
    ControlledModel, ControlledAggregate, Controller, ControlledModelLabel, Access
)

from typing import ClassVar, Set, List, Dict, Any

class ReferenceType(str, Enum):
    LEGAL="LEGAL"
    EXTERNAL = "EXTERNAL"
    FILE = "FILE"
    EXTERNAL_DATA = "EXTERNAL_DATA"
    DATA_FILE = "DATA_FILE"

class DataFormat(str, Enum):  # For complex types, this describes the format
    # todo implement handlers and json schema templates for these types
    FASTA = "FASTA"
    FASTQ = "FASTQ"
    ODGI = "ODGI"
    HDF5 = "HDF5"
    CSV = "CSV"
    TSV = "TSV"

@dataclass(eq=False)
class ReferenceBase(ABC):
    label: ClassVar[ControlledModelLabel] = ControlledModelLabel.REFERENCE
    description: None|str = None

    def model_dump(self) -> Dict[str, Any]:
        d = asdict(self)
        if 'format' in d:
            d['format'] = d['format'].value
        if 'text_format' in d:
            d['text_format'] = d['text_format'].value
        if 'schema' in d and d['schema'] is not None:
            d['schema'] = json.dumps(d['schema'])
        if isinstance(d['type'], ReferenceType):
            d['type'] = d['type'].value
        return d

    def to_output(self) -> Dict[str, Any]:
        d = self.model_dump()
        d.pop('events')
        return d


@dataclass(eq=False)
class ReferenceStoredBase(ControlledModel, ControlledAggregate, ABC):

    @property
    def controlled_models(self) -> List[ControlledModel]:
        return [self]

    @property
    def root(self) -> StoredModel:
        return self

    @property
    def protected(self) -> str | None:
        return None

    @abstractmethod
    def _redacted(self):
        raise NotImplementedError

    def redacted(self, controllers: Dict[str, Dict[int, Controller]], user_id = None, read_teams = None):
        if read_teams is None:
            read_teams = set()

        if controllers[self.label][self.id].has_access(Access.READ, user_id, read_teams):
            return self
        else:
            if user_id is None:
                return None
            return self._redacted()


"""
Legal reference
"""
class TextFormat(str, Enum):
    """How a legal reference's text is written: shown as it is, or rendered as markdown"""
    PLAIN = "PLAIN"
    MARKDOWN = "MARKDOWN"


def text_hash(text: str) -> str:
    """The content hash of typed text: the SHA-256 of its UTF-8, as a file's is of its bytes"""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


@dataclass(eq=False)
class LegalReference(ReferenceBase):
    """
    Legal text, such as a study's licence: typed, or read from a .txt, .md or .pdf file, which is kept for download.
    Its content hash names the text an acceptance of it agrees to (docs/licences.md).
    """
    type: ReferenceType = ReferenceType.LEGAL
    text: str = None
    # text_format, as format is a data reference's (DataFormat), and GraphQL selects both on the same interface
    text_format: TextFormat = TextFormat.PLAIN
    # the SHA-256 of the file the text was read from, or of the typed text
    content_hash: str | None = None
    # given as a file: its name and type, and its name in the file store once saved
    filename: str | None = None
    content_type: str | None = None
    file_id: str | None = None

@dataclass
class LegalReferenceInput(LegalReference, EnumLabeledModel):
    pass

@dataclass(eq=False)
class LegalReferenceStored(LegalReference, ReferenceStoredBase):

    def _redacted(self):
        return replace(
            self,
            description=self.redacted_str,
            text=self.redacted_str,
            content_hash=None,
            filename=None,
            content_type=None,
            file_id=None
        )


"""
External reference
"""
@dataclass(eq=False)
class ExternalReferenceBase(ReferenceBase):
    type: ReferenceType = ReferenceType.EXTERNAL
    url: str = None
    external_id: str | None = None

@dataclass
class ExternalReferenceInput(ExternalReferenceBase, EnumLabeledModel):
    pass

@dataclass(eq=False)
class ExternalReferenceStored(ExternalReferenceBase, ReferenceStoredBase):

    def _redacted(self):
        return replace(
            self,
            url = self.redacted_str,
            external_id = self.redacted_str
        )

"""
File reference
"""
@dataclass(eq=False)
class FileReferenceBase(ReferenceBase):
    type: ReferenceType = ReferenceType.FILE
    filename: str = None  # filename
    file_id: str | None = None # name in file datastore.
    content_type: str | None = None
    # the Persons credited for the file, with the roles they had (docs/contributions.md)
    contributions: List[Contribution] = field(default_factory=list)


@dataclass
class FileReferenceInput(FileReferenceBase, EnumLabeledModel):
    pass

@dataclass(eq=False)
class FileReferenceStored(FileReferenceBase, ReferenceStoredBase):

    def _redacted(self):
        return replace(
                self,
                description = self.redacted_str,
                filename = self.redacted_str,
                content_type = self.redacted_str,
                file_id = None,
                contributions = []
            )

"""
Data references (external references and local files)

Note: should consider describing data format and file format in Ontology.
"""
@dataclass(eq=False)
class DataReferenceBase(ReferenceBase):
    format: DataFormat | None = None
    #todo Needs further refinement and details about requirements for specification
    """
    Schema for parsing the data, 
    e.g.
    "schema": {
      "shape": [300, 50],
      "dtype": "float32",
      "taxa": "rows",
      "units": "columns"
    }
    """
    schema: Dict[str, Any] | None = None


@dataclass(eq=False)
class ExternalDataBase(DataReferenceBase, ExternalReferenceBase):
    type: ReferenceType = ReferenceType.EXTERNAL_DATA
    # the Persons credited for the data, e.g. the project's own data deposited elsewhere, with the roles they had
    contributions: List[Contribution] = field(default_factory=list)

@dataclass
class ExternalDataInput(ExternalDataBase, EnumLabeledModel):
    pass

@dataclass(eq=False)
class ExternalDataStored(ExternalDataBase, ExternalReferenceStored):

    def _redacted(self):
        return replace(super()._redacted(), contributions=[])

@dataclass(eq=False)
class DataFileBase(DataReferenceBase, FileReferenceBase):
    type: ReferenceType = ReferenceType.DATA_FILE

@dataclass
class DataFileInput(DataFileBase, EnumLabeledModel):
    pass

@dataclass(eq=False)
class DataFileStored(DataFileBase, FileReferenceStored):
    pass

