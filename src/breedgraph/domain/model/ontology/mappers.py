import re
from functools import lru_cache
from typing import Dict, Type, List, Tuple, FrozenSet, Set

from src.breedgraph.domain.model.ontology.enums import OntologyEntryLabel, OntologyRelationshipLabel
from src.breedgraph.domain.model.ontology import OntologyEntryStored, OntologyEntryOutput


class OntologyMapper:
    """Class to map attributes to relationship types and back again."""
    snake_case_pattern = re.compile(r'(?<!^)(?=[A-Z])')

    @lru_cache(maxsize=1)
    def get_stored_class_mapping(self) -> Dict[OntologyEntryLabel, Type[OntologyEntryStored]]:
        return {
            subclass().label: subclass
            for subclass in OntologyEntryStored.__subclasses__()
        }

    @lru_cache(maxsize=1)
    def get_output_class_mapping(self) -> Dict[OntologyEntryLabel, Type[OntologyEntryOutput]]:
        return {
            subclass().label: subclass
            for subclass in OntologyEntryOutput.__subclasses__()
        }

    @lru_cache(maxsize=1)
    def relationship_to_valid_source_and_target(self) -> Dict[
        OntologyRelationshipLabel,
        Tuple[
            FrozenSet[OntologyEntryLabel],
            FrozenSet[OntologyEntryLabel]
        ]
    ]:
        base_mapping: Dict[
            OntologyRelationshipLabel,
            Tuple[
                FrozenSet[OntologyEntryLabel],
                FrozenSet[OntologyEntryLabel]
            ]
        ] = {
            OntologyRelationshipLabel.HAS_CATEGORY: (
                frozenset({OntologyEntryLabel.SCALE}),
                frozenset({OntologyEntryLabel.CATEGORY})
            ),
            OntologyRelationshipLabel.DESCRIBES_SUBJECT: (
                frozenset({OntologyEntryLabel.TRAIT, OntologyEntryLabel.CONDITION}),
                frozenset({OntologyEntryLabel.SUBJECT})
            ),
            OntologyRelationshipLabel.DESCRIBES_TRAIT: (
                frozenset({OntologyEntryLabel.VARIABLE}),
                frozenset({OntologyEntryLabel.TRAIT})
            ),
            OntologyRelationshipLabel.DESCRIBES_CONDITION: (
                frozenset({OntologyEntryLabel.FACTOR}),
                frozenset({OntologyEntryLabel.CONDITION})
            ),
            OntologyRelationshipLabel.USES_CONTROL_METHOD: (
                frozenset({OntologyEntryLabel.FACTOR}),
                frozenset({OntologyEntryLabel.CONTROL_METHOD})
            ),
            OntologyRelationshipLabel.USES_OBSERVATION_METHOD: (
                frozenset({OntologyEntryLabel.VARIABLE}),
                frozenset({OntologyEntryLabel.OBSERVATION_METHOD})
            ),
            OntologyRelationshipLabel.USES_SCALE: (
                frozenset({OntologyEntryLabel.VARIABLE, OntologyEntryLabel.FACTOR}),
                frozenset({OntologyEntryLabel.SCALE})
            ),
            OntologyRelationshipLabel.DESCRIBES_FACTOR: (
                frozenset({OntologyEntryLabel.EVENT}),
                frozenset({OntologyEntryLabel.FACTOR})
            ),
            OntologyRelationshipLabel.DESCRIBES_VARIABLE: (
                frozenset({OntologyEntryLabel.EVENT}),
                frozenset({OntologyEntryLabel.VARIABLE})
            ),
        }

        # Special cases for HAS_TERM and PARENT_OF
        base_mapping.update({
            OntologyRelationshipLabel.HAS_TERM: (
                frozenset(label for label in OntologyEntryLabel if label != OntologyEntryLabel.TERM),
                frozenset({OntologyEntryLabel.TERM})
            )#,
            #OntologyRelationshipLabel.PARENT_OF: (
            #    frozenset(OntologyEntryLabel),  # Any ontology entry label
            #    frozenset(OntologyEntryLabel)  # Can be the same label
            #)
        })

        return base_mapping

    @lru_cache(maxsize=1)
    def relationship_from_labels(self) -> Dict[FrozenSet[OntologyEntryLabel], OntologyRelationshipLabel]:
        def _create_mapping():
            mapping = {}
            for label, (sources, targets) in self.relationship_to_valid_source_and_target().items():
                for source in sources:
                    for target in targets:
                        mapping[frozenset({source, target})] = label
            return mapping
        return _create_mapping()

    def get_attribute_name_and_type(
            self,
            source_label: OntologyEntryLabel,
            target_label: OntologyEntryLabel,
            attr_for_source: bool = True  # returns either the attribute name for the source or target entity
    ) -> Tuple[str, Type[int|List[int]]]:
        output_class_mapping = self.get_output_class_mapping()
        source_cls = output_class_mapping[source_label]
        target_cls = output_class_mapping[target_label]

        if source_cls == target_cls:  # PARENT_OF relationship
            if attr_for_source:
                return 'children', List[int]
            else:
                return 'parents', List[int]

        entity_cls = source_cls if attr_for_source else target_cls
        other_cls = target_cls if attr_for_source else source_cls

        # most cases are dataclasses
        # for these, the attribute may not be present until an instance is created
        attr_other_singular = self.snake_case_pattern.sub('_', str(other_cls.label.value)).casefold()
        attr_other_plural = self.snake_case_pattern.sub('_', str(other_cls.label.plural)).casefold()
        if hasattr(entity_cls, '__dataclass_fields__'):
            if attr_other_singular in entity_cls.__dataclass_fields__.keys():
                return attr_other_singular, int
            elif attr_other_plural in entity_cls.__dataclass_fields__.keys():
                return attr_other_plural, List[int]
        else:
            if hasattr(entity_cls, attr_other_singular):
                return attr_other_singular, int
            if hasattr(entity_cls, attr_other_plural):
                return attr_other_plural, List[int]

        raise ValueError(f'Attribute for {other_cls} not found on {entity_cls}')

    def get_other_label_from_attribute(
            self,
            s: str
    ):
        if s[-4:] == '_ids':
            s = s[:-4]
        elif s[-3:] == '_id':
            s = s[:-3]
        else:
            raise ValueError(f"Attribute name {s} should end with '_ids' or '_id'")
        parts = s.split('_')
        camel = ''.join(part.capitalize() for part in parts)
        label = OntologyEntryLabel(camel)
        return label

    def get_relationship_label(
            self,
            entry_label: OntologyEntryLabel,
            other_label: OntologyEntryLabel
    ) -> OntologyRelationshipLabel:
        if entry_label == other_label:
            return OntologyRelationshipLabel.PARENT_OF
        else:
            labels = frozenset({entry_label, other_label})
            if OntologyEntryLabel.TERM in labels:
                return OntologyRelationshipLabel.HAS_TERM
            else:
                mapping = self.relationship_from_labels()
                if labels in mapping:
                    return mapping[labels]

            raise ValueError(f"Relationship label not found for {entry_label} and {other_label}")


ontology_mapper = OntologyMapper()