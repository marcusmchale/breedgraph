from abc import abstractmethod
from pydantic import UUID4, field_serializer
from src.breedgraph.domain.model.base import LabeledModel, StoredModel
from src.breedgraph.domain.model.controls import ControlledModel, ControlledAggregate, Access, Controller

from typing import ClassVar, Set, List, Dict

class ReferenceBase(LabeledModel):
    label: ClassVar[str] = 'Reference'
    plural: ClassVar[str] = 'References'
    description: None|str = None

class ReferenceStoredBase(ControlledModel, ControlledAggregate):

    @property
    @abstractmethod
    def label(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def plural(self) -> str:
        raise NotImplementedError

    @property
    def controlled_models(self) -> List[ControlledModel]:
        return [self]

    @property
    def root(self) -> StoredModel:
        return self

    @property
    def protected(self) -> str | None:
        return None

    def redacted(self, controllers: Dict[str, Dict[int, Controller]], user_id = None, read_teams = None):
        if read_teams is None:
            read_teams = set()

        if controllers[self.label][self.id].has_access(Access.READ, user_id, read_teams):
            return self
        else:
            if user_id is None:
                return None

            redacted: ControlledModel = self.model_copy(
                deep=True,
                update = {
                    'description': self.redacted_str,
                    'data_format': self.redacted_str,
                    'file_format': self.redacted_str,
                    'filename': self.redacted_str,
                    'url': self.redacted_str,
                    'external_id': self.redacted_str,
                    'text': self.redacted_str

                }
            )
            # freeze so it is obvious that changes won't be propagated to a redacted form of the model
            redacted.model_config['frozen'] = True
            return redacted

"""
External reference
"""
class ExternalReferenceBase(ReferenceBase):
    url: str
    external_id: str | None = None


class ExternalReferenceInput(ExternalReferenceBase):
    pass


class ExternalReferenceStored(ExternalReferenceBase, ReferenceStoredBase):
    pass

"""
File reference
"""
class FileReferenceBase(ReferenceBase):
    filename: str  # filename
    uuid: UUID4  # for file datastore.

    # UUID is generated when file is uploaded.
    # Currently just storing files in a directory with this UUID as the name
    @field_serializer('uuid')
    def serialize_uuid(self, uuid):
        return str(uuid)


class FileReferenceInput(FileReferenceBase):
    pass

class FileReferenceStored(FileReferenceBase, ReferenceStoredBase):
    pass


"""
Data references (external references and local files)

Note: should consider describing data format and file format in Ontology.
"""
class DataReferenceBase(ReferenceBase):
    data_format: str
    file_format: str

class DataExternalBase(DataReferenceBase, ExternalReferenceBase):
    pass

class DataExternalInput(DataExternalBase):
    pass

class DataExternalStored(DataExternalBase, ExternalReferenceStored):
    pass


class DataFileBase(DataReferenceBase, FileReferenceBase):
    pass

class DataFileInput(DataFileBase):
    pass

class DataFileStored(DataFileBase, ExternalReferenceStored):
    pass

"""
Legal reference
"""
class LegalReference(ReferenceBase):
    text: str

class LegalReferenceInput(LegalReference):
    pass

class LegalReferenceStored(LegalReference, ReferenceStoredBase):
    pass