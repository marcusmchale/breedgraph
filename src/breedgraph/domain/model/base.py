from dataclasses import dataclass, field
from abc import abstractmethod, ABC, ABCMeta
from enum import Enum, EnumMeta
from functools import lru_cache

from src.breedgraph.service_layer.tracking.wrappers import asdict
from src.breedgraph.domain.events.accounts import Event

from typing import List, Dict, Any, ClassVar

import logging

logger = logging.getLogger(__name__)

class SerializableMixin(ABC):
    """Mixin for objects that need to be serialized for persistence or data transfer"""

    @abstractmethod
    def model_dump(self) -> Dict[str, Any]:
        """
        Return a dictionary mapping all the attributes for serialization
        :return: dict
        """
        raise NotImplementedError


@dataclass
class LabeledModel(SerializableMixin, ABC):
    """Base class for models with labels"""

    @property
    @abstractmethod
    def label(self) -> str:
        """The label for this class of model"""
        raise NotImplementedError

    @property
    @abstractmethod
    def plural(self) -> str:
        """The plural of the label for this class of model"""
        raise NotImplementedError

    def model_dump(self) -> Dict[str, Any]:
        return asdict(self)

class ABCEnumMeta(EnumMeta, ABCMeta):
    pass

class EnumLabel(str, Enum, metaclass=ABCEnumMeta):

    @classmethod
    @abstractmethod
    @lru_cache(maxsize=1)
    def _enum_to_plural_map(cls) -> dict[Enum, str]:
        return {}

    @property
    @abstractmethod
    def label(self) -> str:
        ...

    @property
    @abstractmethod
    def plural(self) -> str:
        return self._enum_to_plural_map()[self]


@dataclass
class EnumLabeledModel(LabeledModel, ABC):
    label: ClassVar[EnumLabel]

    @property
    def plural(self) -> str:
        """The plural for this class of model"""
        return self.label.plural


@dataclass
class StoredModel(LabeledModel, ABC):
    """Base class for stored models with ID"""
    id: int = None

    def __hash__(self):
        return hash(self.id)

@dataclass(eq=False)
class Aggregate(ABC):
    """Base aggregate class"""
    events: List[Event] = field(default_factory=list)

    @property
    @abstractmethod
    def root(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def protected(self) -> str|None:
        # Return a string describing why this aggregate is protected
        # or None/empty string if safe to delete
        raise NotImplementedError

    def __hash__(self) -> int:
        return hash(self.root.id)

    def __eq__(self, other) -> bool:
        """Aggregates are equal if they have the same class and root ID"""
        if not isinstance(other, Aggregate):
            return False
        return self.__class__.__name__ == other.__class__.__name__ and self.root.id == other.root.id
