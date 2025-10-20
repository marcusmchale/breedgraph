from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from uuid import UUID, uuid4
from enum import Enum

from src.breedgraph.service_layer.tracking.wrappers import asdict
from src.breedgraph.domain.model.base import StoredModel, EnumLabeledModel, LabeledModel
from src.breedgraph.domain.model.controls import ControlledModel, ControlledAggregate, Access, Controller, ControlledModelLabel

from typing import ClassVar, Set, List, Dict, Any

class DataFormat(str, Enum):  # For complex types, this describes the format
    # todo implement handlers for these types
    JSON = "JSON"
    HDF5 = "HDF5"
    CSV = "CSV"
    TSV = "TSV"

@dataclass(eq=False)
class ReferenceBase(ABC):
    label: ClassVar[ControlledModelLabel] = ControlledModelLabel.REFERENCE
    description: None|str = None

    def model_dump(self) -> Dict[str, Any]:
        return asdict(self)

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
External reference
"""
@dataclass(eq=False)
class ExternalReferenceBase(ReferenceBase):
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
    filename: str = None  # filename
    uuid: UUID | None = uuid4()  # for file datastore. # normally required, but allow none for redacted return

    def model_dump(self) -> Dict[str, Any]:
        dump = asdict(self)
        dump.update(uuid = str(self.uuid))
        return dump

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
                uuid = None
            )

"""
Data references (external references and local files)

Note: should consider describing data format and file format in Ontology.
"""
@dataclass(eq=False)
class DataReferenceBase(ReferenceBase):
    format: DataFormat = None
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
    schema: Dict[str, Any] = None


@dataclass(eq=False)
class DataExternalBase(DataReferenceBase, ExternalReferenceBase):
    pass

@dataclass
class DataExternalInput(DataExternalBase, EnumLabeledModel):
    pass

@dataclass(eq=False)
class DataExternalStored(DataExternalBase, ExternalReferenceStored):
    pass

@dataclass(eq=False)
class DataFileBase(DataReferenceBase, FileReferenceBase):
    pass

@dataclass
class DataFileInput(DataFileBase, EnumLabeledModel):
    pass

@dataclass(eq=False)
class DataFileStored(DataFileBase, ExternalReferenceStored):
    pass

"""
Legal reference
"""
@dataclass(eq=False)
class LegalReference(ReferenceBase):
    text: str = None

@dataclass
class LegalReferenceInput(LegalReference, EnumLabeledModel):
    pass

@dataclass(eq=False)
class LegalReferenceStored(LegalReference, ReferenceStoredBase):

    def _redacted(self):
        return replace(
            self,
            description=self.redacted_str,
            text=self.redacted_str
        )
