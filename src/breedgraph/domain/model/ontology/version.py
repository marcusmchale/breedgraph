from numpy import datetime64
from dataclasses import dataclass, field, replace
from typing import ClassVar, Dict, Any, Self

from src.breedgraph.domain.model.base import LabeledModel, StoredModel
from src.breedgraph.domain.model.ontology.enums import VersionChange

@dataclass
class Version:
    """ Ontology commit version and metadata """
    major: int = 0  # 16 bits
    minor: int = 0  # 16 bits
    patch: int = 0  # 32 bits

    def __post_init__(self):
        if not (0 <= self.major <= 65535):
            raise ValueError(f"major must be between 0 and 65535, got {self.major}")
        if not (0 <= self.minor <= 65535):
            raise ValueError(f"minor must be between 0 and 65535, got {self.minor}")
        if not (0 <= self.patch <= 4294967295):
            raise ValueError(f"patch must be between 0 and 4294967295, got {self.patch}")

    @property
    def id(self) -> int:
        """Use packed version as the natural identifier"""
        return self.packed_version

    @property
    def packed_version(self) -> int:
        """Pack version into 64-bit integer: major(16) | minor(16) | patch(32)"""
        return (self.major << 48) | (self.minor << 32) | self.patch

    @property
    def version_string(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @classmethod
    def from_packed(cls, packed_version: int) -> Self:
        """Unpack 64-bit integer into version components"""
        if packed_version is None:
            return None

        major = (packed_version >> 48) & 0xFFFF
        minor = (packed_version >> 32) & 0xFFFF
        patch = packed_version & 0xFFFFFFFF
        return cls(major=major, minor=minor, patch=patch)

    def __str__(self) -> str:
        return self.version_string

    def __hash__(self) -> int:
        return hash(self.packed_version)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Version):
            return False
        return self.packed_version == other.packed_version

    def __lt__(self, other) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self.packed_version < other.packed_version

    def __le__(self, other) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self.packed_version <= other.packed_version

    def __gt__(self, other) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self.packed_version > other.packed_version

    def __ge__(self, other) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self.packed_version >= other.packed_version

    def increment(self, change: VersionChange) -> Self:
        if change is VersionChange.MAJOR:
            return Version(
                major=self.major + 1,
                minor=0,
                patch=0
            )
        elif change is VersionChange.MINOR:
            return Version(
                major=self.major,
                minor=self.minor + 1,
                patch=0
            )
        else:
            return Version(
                major=self.major,
                minor=self.minor,
                patch=self.patch + 1
            )

@dataclass
class OntologyCommit(LabeledModel):
    label: ClassVar[str] = "OntologyCommit"
    plural: ClassVar[str] = "OntologyCommits"

    version: Version
    comment: str

    licence: int | None = None
    copyright: int | None = None

    # set by the server
    time: datetime64 | None = None
    user: int = None

    @property
    def id(self) -> int:
        return self.version.packed_version

    def model_dump(self) -> Dict[str, Any]:
        pass
