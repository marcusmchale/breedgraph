from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Tuple, TypeVar, Type, Self


from src.breedgraph.domain.model.ontology.enums import OntologyRelationshipLabel, OntologyEntryLabel

@dataclass
class OntologyRelationshipBase(ABC):
    """Relationship between OntologyEntries"""
    # Core relationship identity (composite key)
    source_id: int
    target_id: int
    source_label: OntologyEntryLabel
    target_label: OntologyEntryLabel
    label: OntologyRelationshipLabel  # Type of relationship
    id: int = None

    @property
    def key(self) -> Tuple[int, int, OntologyRelationshipLabel]:
        """Unique key identifying this relationship"""
        return self.source_id, self.target_id, self.label

    def __str__(self) -> str:
        return f"{self.source_id} --[{self.label.value}]--> {self.target_id}"

    def __hash__(self) -> int:
        """Hash based on relationship key for set operations"""
        return hash(self.key)

    def __eq__(self, other) -> bool:
        """Equality based on relationship key"""
        return isinstance(other, OntologyRelationshipBase) and self.key == other.key

    def model_dump(self):
        dump = asdict(self)
        dump['label'] = self.label.value
        return dump

    @classmethod
    @abstractmethod
    def build(
            cls,
            *,
            source_id: int,
            target_id: int,
            source_label:
            OntologyEntryLabel,
            target_label: OntologyEntryLabel,
            **kwargs
    ) -> Self:
        ...

    @classmethod
    @abstractmethod
    def load(
            cls,
            *,
            source_id: int,
            target_id: int,
            source_label: OntologyEntryLabel,
            target_label: OntologyEntryLabel,
            relationship_id: int,
            **kwargs
    ) -> Self:
        ...

    @staticmethod
    def relationship_from_label(
            source_id: int,
            target_id: int,
            source_label: OntologyEntryLabel,
            target_label: OntologyEntryLabel,
            label: OntologyRelationshipLabel,
            relationship_id: int = None,
            rank: int = None
    ):
        if label == OntologyRelationshipLabel.PARENT_OF:
            if relationship_id is None:
                return ParentRelationship.build(
                    parent_id=source_id,
                    child_id=target_id,
                    source_label=source_label,
                    target_label=target_label
                )
            else:
                return ParentRelationship.load(
                    parent_id=source_id,
                    child_id=target_id,
                    source_label=source_label,
                    target_label=target_label,
                    relationship_id=relationship_id
                )
        elif label == OntologyRelationshipLabel.HAS_TERM:
            if relationship_id is None:
                return TermRelationship.build(
                    source_id=source_id,
                    term_id=target_id,
                    source_label=source_label,
                    target_label=target_label
                )
            else:
                return TermRelationship.load(
                    source_id=source_id,
                    term_id=target_id,
                    source_label=source_label,
                    target_label=target_label,
                    relationship_id=relationship_id
                )
        elif label == OntologyRelationshipLabel.HAS_CATEGORY:
            if relationship_id is None:
                return CategoryRelationship.build(
                    scale_id=source_id,
                    category_id=target_id,
                    source_label=source_label,
                    target_label=target_label,
                    rank=rank
                )
            else:
                return CategoryRelationship.load(
                    scale_id=source_id,
                    category_id=target_id,
                    source_label=source_label,
                    target_label=target_label,
                    relationship_id=relationship_id,
                    rank=rank
                )
        elif label == OntologyRelationshipLabel.DESCRIBES_SUBJECT:
            if relationship_id is None:
                return SubjectRelationship.build(
                    source_id=source_id,
                    subject_id=target_id,
                    source_label=source_label,
                    target_label=target_label
                )
            else:
                return SubjectRelationship.load(
                    source_id=source_id,
                    subject_id=target_id,
                    source_label=source_label,
                    target_label=target_label,
                    relationship_id=relationship_id
                )
        elif label == OntologyRelationshipLabel.DESCRIBES_TRAIT:
            if relationship_id is None:
                return VariableComponentRelationship.TraitRelationship.build(
                    variable_id=source_id,
                    trait_id=target_id,
                    source_label=source_label,
                    target_label=target_label
                )
            else:
                return VariableComponentRelationship.TraitRelationship.load(
                    variable_id=source_id,
                    trait_id=target_id,
                    source_label=source_label,
                    target_label=target_label,
                    relationship_id=relationship_id
                )
        elif label == OntologyRelationshipLabel.USES_OBSERVATION_METHOD:
            if relationship_id is None:
                return VariableComponentRelationship.ObservationMethodRelationship.build(
                    variable_id=source_id,
                    observation_method_id=target_id,
                    source_label=source_label,
                    target_label=target_label
                )
            else:
                return VariableComponentRelationship.ObservationMethodRelationship.load(
                    variable_id=source_id,
                    observation_method_id=target_id,
                    relationship_id=relationship_id,
                    source_label=source_label,
                    target_label=target_label
                )
        elif label == OntologyRelationshipLabel.USES_SCALE:
            if relationship_id is None:
                return ScaleRelationship.build(
                    source_id=source_id,
                    scale_id=target_id,
                    source_label=source_label,
                    target_label=target_label
                )
            else:
                return ScaleRelationship.load(
                    source_id=source_id,
                    scale_id=target_id,
                    source_label=source_label,
                    target_label=target_label,
                    relationship_id=relationship_id
                )
        elif label == OntologyRelationshipLabel.DESCRIBES_CONDITION:
            if relationship_id is None:
                return FactorComponentRelationship.ConditionRelationship.build(
                    factor_id=source_id,
                    condition_id=target_id,
                    source_label=source_label,
                    target_label=target_label
                )
            else:
                return FactorComponentRelationship.ConditionRelationship.load(
                    factor_id=source_id,
                    condition_id=target_id,
                    source_label=source_label,
                    target_label=target_label,
                    relationship_id=relationship_id
                )
        elif label == OntologyRelationshipLabel.USES_CONTROL_METHOD:
            if relationship_id is None:
                return FactorComponentRelationship.ControlMethodRelationship.build(
                    factor_id=source_id,
                    control_method_id=target_id,
                    source_label=source_label,
                    target_label=target_label
                )
            else:
                return FactorComponentRelationship.ControlMethodRelationship.load(
                    factor_id=source_id,
                    control_method_id=target_id,
                    relationship_id=relationship_id,
                    source_label=source_label,
                    target_label=target_label
                )
        elif label == OntologyRelationshipLabel.DESCRIBES_FACTOR:
            if relationship_id is None:
                return EventTypeComponentRelationship.FactorRelationship.build(
                    event_type_id=source_id,
                    factor_id=target_id,
                    source_label=source_label,
                    target_label=target_label
                )
            else:
                return EventTypeComponentRelationship.FactorRelationship.load(
                    event_type_id=source_id,
                    factor_id=target_id,
                    relationship_id=relationship_id,
                    source_label=source_label,
                    target_label=target_label
                )
        elif label == OntologyRelationshipLabel.DESCRIBES_VARIABLE:
            if relationship_id is None:
                return EventTypeComponentRelationship.VariableRelationship.build(
                    event_type_id=source_id,
                    variable_id=target_id,
                    source_label=source_label,
                    target_label=target_label
                )
            else:
                return EventTypeComponentRelationship.VariableRelationship.load(
                    event_type_id=source_id,
                    variable_id=target_id,
                    relationship_id=relationship_id,
                    source_label=source_label,
                    target_label=target_label
                )
        else:
            raise ValueError(f"Unsupported relationship label: {label}")

@dataclass
class ParentRelationship(OntologyRelationshipBase):
    """Parent-child relationship used to describe hierarchical relationships within a given label"""

    @classmethod
    def build(
            cls,
            *,
            parent_id: int,
            child_id: int,
            source_label: OntologyEntryLabel,
            target_label: OntologyEntryLabel,
            **kwargs
    ) -> Self:
        if not source_label == target_label:
            raise ValueError(
                f"{cls.__name__} must be between the same label: {source_label} != {target_label}"
            )
        if kwargs:
            raise ValueError(f"No other parameters are allowed for {cls.__name__}")
        return cls(
            source_id=parent_id,
            target_id=child_id,
            source_label=source_label,
            target_label=target_label,
            label=OntologyRelationshipLabel.PARENT_OF
        )

    @classmethod
    def load(
            cls,
            *,
            parent_id: int,
            child_id: int,
            source_label: OntologyEntryLabel,
            target_label: OntologyEntryLabel,
            relationship_id: int,
            **kwargs
    ) -> Self:
        if kwargs:
            raise ValueError(f"No other parameters are allowed for {cls.__name__}")
        return cls(
            source_id=parent_id,
            target_id=child_id,
            source_label=source_label,
            target_label=target_label,
            label=OntologyRelationshipLabel.PARENT_OF,
            id=relationship_id
        )

@dataclass
class TermRelationship(OntologyRelationshipBase):
    """
    Generic relationship TO a Term (Term as target).
    Used to bridge other entities to general ontological concepts.
    """
    @classmethod
    def build(
            cls,
            *,
            source_id: int,
            term_id: int,
            source_label: OntologyEntryLabel,
            target_label: OntologyEntryLabel = OntologyEntryLabel.TERM,
            **kwargs
    ) -> Self:
        if not target_label == OntologyEntryLabel.TERM:
            raise ValueError(
                f"{cls.__name__} must target a {OntologyEntryLabel.TERM}, not {target_label}"
            )
        if source_label == OntologyEntryLabel.TERM:
            raise ValueError(
                f"{cls.__name__} must not relate from a {OntologyEntryLabel.TERM}, "
                f"use {OntologyRelationshipLabel.PARENT_OF} instead"
            )
        if kwargs:
            raise ValueError(f"No other parameters are allowed for {cls.__name__}")
        return cls(
            source_id=source_id,
            target_id=term_id,  # Term is always the target
            source_label=source_label,
            target_label=target_label,
            label=OntologyRelationshipLabel.HAS_TERM
        )

    @classmethod
    def load(
            cls,
            *,
            source_id: int,
            term_id: int,
            source_label: OntologyEntryLabel,
            target_label: OntologyEntryLabel,
            relationship_id: int,
            **kwargs
    ) -> Self:
        if kwargs:
            raise ValueError(f"No other parameters are allowed for {cls.__name__}")
        return cls(
            source_id=source_id,
            target_id=term_id,  # Term is always the target
            source_label=source_label,
            target_label=target_label,
            label=OntologyRelationshipLabel.HAS_TERM,
            id=relationship_id
        )

@dataclass
class SubjectRelationship(OntologyRelationshipBase):
    """Subject has trait relationship"""

    @classmethod
    def build(
            cls,
            *,
            source_id: int,
            subject_id: int,
            source_label: OntologyEntryLabel,
            target_label: OntologyEntryLabel = OntologyEntryLabel.SUBJECT,
            **kwargs
    ) -> Self:
        if kwargs:
            raise ValueError(f"No other parameters are allowed for {cls.__name__}")
        if not target_label == OntologyEntryLabel.SUBJECT:
            raise ValueError(
                f"{cls.__name__} must relate to {OntologyEntryLabel.SUBJECT}, not {target_label}"
            )
        if not source_label in [OntologyEntryLabel.TRAIT, OntologyEntryLabel.CONDITION]:
            raise ValueError(
                f"{cls.__name__} must relate from {OntologyEntryLabel.TRAIT} or {OntologyEntryLabel.CONTROL_METHOD}, not {source_label}"
            )
        return cls(
            source_id=source_id,
            target_id=subject_id,
            source_label=source_label,
            target_label=target_label,
            label=OntologyRelationshipLabel.DESCRIBES_SUBJECT
        )

    @classmethod
    def load(
            cls,
            *,
            source_id: int,
            subject_id: int,
            source_label: OntologyEntryLabel,
            target_label: OntologyEntryLabel,
            relationship_id: int,
            **kwargs
    ) -> Self:
        if kwargs:
            raise ValueError(f"No other parameters are allowed for {cls.__name__}")
        return cls(
            source_id=source_id,
            target_id=subject_id,
            source_label=source_label,
            target_label=target_label,
            label=OntologyRelationshipLabel.DESCRIBES_SUBJECT,
            id=relationship_id
        )

@dataclass
class CategoryRelationship(OntologyRelationshipBase):
    """Scale has category relationship with rank"""
    rank: int = None

    @classmethod
    def build(
            cls,
            *,
            scale_id: int,
            category_id: int,
            source_label: OntologyEntryLabel = OntologyEntryLabel.SCALE,
            target_label: OntologyEntryLabel = OntologyEntryLabel.CATEGORY,
            rank: Optional[int] = None,
            **kwargs
    ) -> Self:
        if not target_label == OntologyEntryLabel.CATEGORY:
            raise ValueError(
                f"{cls.__name__} must relate to {OntologyEntryLabel.CATEGORY}, not {target_label}"
            )
        if not source_label == OntologyEntryLabel.SCALE:
            raise ValueError(
                f"{cls.__name__} must relate from {OntologyEntryLabel.SCALE}, not {source_label}"
            )
        if kwargs:
            raise ValueError(f"No other parameters are allowed for {cls.__name__}")
        return cls(
            source_id=scale_id,
            target_id=category_id,
            source_label=source_label,
            target_label=target_label,
            label=OntologyRelationshipLabel.HAS_CATEGORY,
            rank = rank
        )

    @classmethod
    def load(
            cls,
            *,
            scale_id: int,
            category_id: int,
            source_label: OntologyEntryLabel,
            target_label: OntologyEntryLabel,
            relationship_id: int,
            rank: Optional[int] = None,
            **kwargs
    ) -> Self:
        if kwargs:
            raise ValueError(f"No other parameters are allowed for {cls.__name__}")
        return cls(
            source_id=scale_id,
            target_id=category_id,
            source_label=source_label,
            target_label=target_label,
            label=OntologyRelationshipLabel.HAS_CATEGORY,
            id=relationship_id,
            rank = rank
        )

@dataclass
class ScaleRelationship(OntologyRelationshipBase):
    """Common relationship for entities that use a scale (Variables and Factors)"""

    @classmethod
    def build(
            cls,
            *,
            source_id: int,
            scale_id: int,
            source_label: OntologyEntryLabel,
            target_label: OntologyEntryLabel = OntologyEntryLabel.SCALE,
            **kwargs
    ) -> Self:
        if not source_label in [OntologyEntryLabel.VARIABLE, OntologyEntryLabel.FACTOR]:
            raise ValueError(
                f"{cls.__name__} must relate from {OntologyEntryLabel.VARIABLE} or {OntologyEntryLabel.FACTOR}, not {source_label}"
            )
        if not target_label == OntologyEntryLabel.SCALE:
            raise ValueError(
                f"{cls.__name__} must relate to {OntologyEntryLabel.SCALE}, not {target_label}"
            )
        if kwargs:
            raise ValueError(f"No other parameters are allowed for {cls.__name__}")
        return cls(
            source_id=source_id,
            target_id=scale_id,
            source_label=source_label,
            target_label=target_label,
            label=OntologyRelationshipLabel.USES_SCALE
        )

    @classmethod
    def load(
            cls,
            *,
            source_id: int,
            scale_id: int,
            source_label: OntologyEntryLabel,
            target_label: OntologyEntryLabel,
            relationship_id: int,
            **kwargs
    ) -> Self:
        if kwargs:
            raise ValueError(f"No other parameters are allowed for {cls.__name__}")
        return cls(
            source_id=source_id,
            target_id=scale_id,
            source_label=source_label,
            target_label=target_label,
            label=OntologyRelationshipLabel.USES_SCALE,
            id=relationship_id
        )


class VariableComponentRelationship:
    """Variable describes trait, uses method, uses scale"""

    @dataclass
    class TraitRelationship(OntologyRelationshipBase):

        @classmethod
        def build(
                cls,
                *,
                variable_id: int,
                trait_id: int,
                source_label: OntologyEntryLabel = OntologyEntryLabel.VARIABLE,
                target_label: OntologyEntryLabel = OntologyEntryLabel.TRAIT,
                **kwargs
        ) -> Self:
            if not target_label == OntologyEntryLabel.TRAIT:
                raise ValueError(
                    f"{cls.__name__} must relate to {OntologyEntryLabel.TRAIT}, not {target_label}"
                )
            if not source_label == OntologyEntryLabel.VARIABLE:
                raise ValueError(
                    f"{cls.__name__} must relate from {OntologyEntryLabel.VARIABLE}, not {source_label}"
                )
            if kwargs:
                raise ValueError(f"No other parameters are allowed for {cls.__name__}")
            return cls(
                source_id=variable_id,
                target_id=trait_id,
                source_label=source_label,
                target_label=target_label,
                label=OntologyRelationshipLabel.DESCRIBES_TRAIT
            )

        @classmethod
        def load(
                cls,
                *,
                variable_id: int,
                trait_id: int,
                source_label: OntologyEntryLabel,
                target_label: OntologyEntryLabel,
                relationship_id: int,
                **kwargs
        ) -> Self:
            if kwargs:
                raise ValueError(f"No other parameters are allowed for {cls.__name__}")
            return cls(
                source_id=variable_id,
                target_id=trait_id,
                source_label=source_label,
                target_label=target_label,
                label=OntologyRelationshipLabel.DESCRIBES_TRAIT,
                id=relationship_id
            )

    @dataclass
    class ObservationMethodRelationship(OntologyRelationshipBase):

        @classmethod
        def build(
                cls,
                *,
                variable_id: int,
                observation_method_id: int,
                source_label: OntologyEntryLabel = OntologyEntryLabel.VARIABLE,
                target_label: OntologyEntryLabel = OntologyEntryLabel.OBSERVATION_METHOD,
                **kwargs
        ) -> Self:
            if not target_label == OntologyEntryLabel.OBSERVATION_METHOD:
                raise ValueError(
                    f"{cls.__name__} must relate to {OntologyEntryLabel.OBSERVATION_METHOD}, not {target_label}"
                )
            if not source_label == OntologyEntryLabel.VARIABLE:
                raise ValueError(
                    f"{cls.__name__} must relate from {OntologyEntryLabel.VARIABLE}, not {source_label}"
                )
            if kwargs:
                raise ValueError(f"No other parameters are allowed for {cls.__name__}")
            return cls(
                source_id=variable_id,
                target_id=observation_method_id,
                source_label=source_label,
                target_label=target_label,
                label=OntologyRelationshipLabel.USES_OBSERVATION_METHOD
            )

        @classmethod
        def load(
                cls,
                *,
                variable_id: int,
                observation_method_id: int,
                source_label: OntologyEntryLabel,
                target_label: OntologyEntryLabel,
                relationship_id: int,
                **kwargs
        ) -> Self:
            if kwargs:
                raise ValueError(f"No other parameters are allowed for {cls.__name__}")
            return cls(
                source_id=variable_id,
                target_id=observation_method_id,
                source_label=source_label,
                target_label=target_label,
                label=OntologyRelationshipLabel.USES_OBSERVATION_METHOD,
                id=relationship_id
            )

    class ScaleRelationship:
        """Factory for Variable -> Scale relationships"""

        @classmethod
        def build(
                cls,
                *,
                variable_id: int,
                scale_id: int,
                source_label: OntologyEntryLabel = OntologyEntryLabel.VARIABLE,
                target_label: OntologyEntryLabel = OntologyEntryLabel.SCALE,
                **kwargs
        ) -> ScaleRelationship:
            if not source_label in [OntologyEntryLabel.VARIABLE, OntologyEntryLabel.FACTOR]:
                raise ValueError(
                    f"{cls.__name__} must relate from {OntologyEntryLabel.VARIABLE} or {OntologyEntryLabel.FACTOR}, not {source_label}"
                )
            if not target_label == OntologyEntryLabel.SCALE:
                raise ValueError(
                    f"{cls.__name__} must relate to {OntologyEntryLabel.SCALE}, not {target_label}"
                )
            if kwargs:
                raise ValueError(f"No other parameters are allowed for {cls.__name__}")
            return ScaleRelationship.build(
                source_id=variable_id,
                scale_id=scale_id,
                source_label=source_label,
                target_label=target_label,
            )

        @classmethod
        def load(
                cls,
                *,
                variable_id: int,
                scale_id: int,
                source_label: OntologyEntryLabel,
                target_label: OntologyEntryLabel,
                relationship_id: int,
                **kwargs
        ) -> ScaleRelationship:
            if kwargs:
                raise ValueError(f"No other parameters are allowed for {cls.__name__}")
            return ScaleRelationship.load(
                source_id=variable_id,
                scale_id=scale_id,
                source_label=source_label,
                target_label=target_label,
                relationship_id=relationship_id,
            )


class FactorComponentRelationship:
    """Factor describes condition, uses method, uses scale"""

    @dataclass
    class ConditionRelationship(OntologyRelationshipBase):

        @classmethod
        def build(
                cls,
                factor_id: int,
                condition_id: int,
                source_label: OntologyEntryLabel = OntologyEntryLabel.FACTOR,
                target_label: OntologyEntryLabel = OntologyEntryLabel.CONDITION,
                **kwargs
        ) -> Self:
            if not target_label == OntologyEntryLabel.CONDITION:
                raise ValueError(
                    f"{cls.__name__} must relate to {OntologyEntryLabel.CONDITION}, not {target_label}"
                )
            if not source_label == OntologyEntryLabel.FACTOR:
                raise ValueError(
                    f"{cls.__name__} must relate from {OntologyEntryLabel.FACTOR}, not {source_label}"
                )
            if kwargs:
                raise ValueError(f"No other parameters are allowed for {cls.__name__}")
            return cls(
                source_id=factor_id,
                target_id=condition_id,
                source_label=source_label,
                target_label=target_label,
                label=OntologyRelationshipLabel.DESCRIBES_CONDITION
            )

        @classmethod
        def load(
                cls,
                factor_id: int,
                condition_id: int,
                source_label: OntologyEntryLabel,
                target_label: OntologyEntryLabel,
                relationship_id: int,
                **kwargs
        ) -> Self:
            if kwargs:
                raise ValueError(f"No other parameters are allowed for {cls.__name__}")
            return cls(
                source_id=factor_id,
                target_id=condition_id,
                source_label=source_label,
                target_label=target_label,
                label=OntologyRelationshipLabel.DESCRIBES_CONDITION,
                id=relationship_id
            )

    @dataclass
    class ControlMethodRelationship(OntologyRelationshipBase):

        @classmethod
        def build(
                cls,
                factor_id: int,
                control_method_id: int,
                source_label: OntologyEntryLabel = OntologyEntryLabel.FACTOR,
                target_label: OntologyEntryLabel = OntologyEntryLabel.CONTROL_METHOD,
                **kwargs
        ) -> Self:
            if not target_label == OntologyEntryLabel.CONTROL_METHOD:
                raise ValueError(
                    f"{cls.__name__} must relate to {OntologyEntryLabel.CONTROL_METHOD}, not {target_label}"
                )
            if not source_label == OntologyEntryLabel.FACTOR:
                raise ValueError(
                    f"{cls.__name__} must relate from {OntologyEntryLabel.FACTOR}, not {source_label}"
                )
            if kwargs:
                raise ValueError(f"No other parameters are allowed for {cls.__name__}")
            return cls(
                source_id=factor_id,
                target_id=control_method_id,
                source_label=source_label,
                target_label=target_label,
                label=OntologyRelationshipLabel.USES_CONTROL_METHOD
            )

        @classmethod
        def load(
                cls,
                factor_id: int,
                control_method_id: int,
                source_label: OntologyEntryLabel,
                target_label: OntologyEntryLabel,
                relationship_id: int,
                **kwargs
        ) -> Self:
            if kwargs:
                raise ValueError(f"No other parameters are allowed for {cls.__name__}")
            return cls(
                source_id=factor_id,
                target_id=control_method_id,
                source_label=source_label,
                target_label=target_label,
                label=OntologyRelationshipLabel.USES_CONTROL_METHOD,
                id=relationship_id
            )

    class ScaleRelationship:
        """Factory for Factor -> Scale relationships"""

        @classmethod
        def build(
                cls,
                *,
                factor_id: int,
                scale_id: int,
                source_label: OntologyEntryLabel = OntologyEntryLabel.FACTOR,
                target_label: OntologyEntryLabel = OntologyEntryLabel.SCALE,
                **kwargs
        ) -> ScaleRelationship:
            if not source_label in [OntologyEntryLabel.VARIABLE, OntologyEntryLabel.FACTOR]:
                raise ValueError(
                    f"{cls.__name__} must relate from {OntologyEntryLabel.VARIABLE} or {OntologyEntryLabel.FACTOR}, not {source_label}"
                )
            if not target_label == OntologyEntryLabel.SCALE:
                raise ValueError(
                    f"{cls.__name__} must relate to {OntologyEntryLabel.SCALE}, not {target_label}"
                )
            if kwargs:
                raise ValueError(f"No other parameters are allowed for {cls.__name__}")
            return ScaleRelationship.build(
                source_id=factor_id,
                scale_id=scale_id,
                source_label=source_label,
                target_label=target_label
            )

        @classmethod
        def load(
                cls,
                *,
                factor_id: int,
                scale_id: int,
                source_label: OntologyEntryLabel,
                target_label: OntologyEntryLabel,
                relationship_id: int,
                **kwargs
        ) -> ScaleRelationship:
            if kwargs:
                raise ValueError(f"No other parameters are allowed for {cls.__name__}")
            return ScaleRelationship.load(
                source_id=factor_id,
                scale_id=scale_id,
                source_label=source_label,
                target_label=target_label,
                relationship_id=relationship_id
            )


class EventTypeComponentRelationship:
    """
    Event type describes the confluence of multiple variables and factors
    """

    @dataclass
    class FactorRelationship(OntologyRelationshipBase):

        @classmethod
        def build(
                cls,
                *,
                event_type_id: int,
                factor_id: int,
                source_label: OntologyEntryLabel = OntologyEntryLabel.EVENT,
                target_label: OntologyEntryLabel = OntologyEntryLabel.FACTOR,
                **kwargs
        ) -> Self:
            if not target_label == OntologyEntryLabel.FACTOR:
                raise ValueError(
                    f"{cls.__name__} must relate to {OntologyEntryLabel.FACTOR}, not {target_label}"
                )
            if not source_label == OntologyEntryLabel.EVENT:
                raise ValueError(
                    f"{cls.__name__} must relate from {OntologyEntryLabel.EVENT}, not {source_label}"
                )
            if kwargs:
                raise ValueError(f"No other parameters are allowed for {cls.__name__}")
            return cls(
                source_id=event_type_id,
                target_id=factor_id,
                source_label=source_label,
                target_label=target_label,
                label=OntologyRelationshipLabel.DESCRIBES_FACTOR
            )

        @classmethod
        def load(
                cls,
                *,
                event_type_id: int,
                factor_id: int,
                source_label: OntologyEntryLabel,
                target_label: OntologyEntryLabel,
                relationship_id: int,
                **kwargs
        ) -> Self:
            if kwargs:
                raise ValueError(f"No other parameters are allowed for {cls.__name__}")
            return cls(
                source_id=event_type_id,
                target_id=factor_id,
                source_label=source_label,
                target_label=target_label,
                label=OntologyRelationshipLabel.DESCRIBES_FACTOR,
                id=relationship_id
            )

    @dataclass
    class VariableRelationship(OntologyRelationshipBase):

        @classmethod
        def build(
                cls,
                *,
                event_type_id: int,
                variable_id: int,
                source_label: OntologyEntryLabel = OntologyEntryLabel.EVENT,
                target_label: OntologyEntryLabel = OntologyEntryLabel.VARIABLE,
                **kwargs
        ) -> Self:
            if not target_label == OntologyEntryLabel.VARIABLE:
                raise ValueError(f"{cls.__name__} must relate to {OntologyEntryLabel.VARIABLE}, not {target_label}")
            if not source_label == OntologyEntryLabel.EVENT:
                raise ValueError(f"{cls.__name__} must relate from {OntologyEntryLabel.EVENT}, not {source_label}")
            if kwargs:
                raise ValueError(f"No other parameters are allowed for {cls.__name__}")
            return cls(
                source_id=event_type_id,
                target_id=variable_id,
                source_label=source_label,
                target_label=target_label,
                label=OntologyRelationshipLabel.DESCRIBES_VARIABLE
            )

        @classmethod
        def load(
                cls,
                *,
                event_type_id: int,
                variable_id: int,
                source_label: OntologyEntryLabel,
                target_label: OntologyEntryLabel,
                relationship_id: int,
                **kwargs
        ) -> Self:
            if kwargs:
                raise ValueError(f"No other parameters are allowed for {cls.__name__}")
            return cls(
                source_id=event_type_id,
                target_id=variable_id,
                source_label=source_label,
                target_label=target_label,
                label=OntologyRelationshipLabel.DESCRIBES_VARIABLE,
                id=relationship_id
            )

