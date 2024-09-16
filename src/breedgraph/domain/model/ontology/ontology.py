import bisect
import networkx as nx

from pydantic import BaseModel, computed_field, Field

from src.breedgraph.domain.model.base import StoredModel, DiGraphAggregate

from .subjects import Subject
from .entries import OntologyEntry, OntologyRelationshipLabel, Term
from .variables import Scale, ScaleType, ScaleCategory, ObservationMethod, Trait, Variable
from .germplasm import GermplasmMethod
from .parameters import Condition, Parameter
from .event_type import Exposure, EventType
from .designs import Design
from .layout_type import LayoutType
from .people import Role, Title
from .location_type import LocationType

from functools import total_ordering
from typing import List, Tuple, ClassVar, Generator

@total_ordering
class Version(BaseModel):
    major: int = 0
    minor: int = 0
    patch: int = 0
    comment: str = ''

    @property
    def name(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}-{self.comment}"

    def as_tuple(self):
        return tuple([self.major, self.minor, self.patch])

    def __gt__(self, other):
        return self.as_tuple() > other.as_tuple()

    def __eq__(self, other):
        return self.as_tuple() == other.as_tuple()


class VersionStored(Version, StoredModel):
    label: ClassVar[str] = 'OntologyVersion'
    plural: ClassVar[str] = 'OntologyVersions'
    """
        Ontology version is associated with it's respective entries.
        When a new term is added, this means a new version, but may be a minor/patch version
        Major version changes should reflect a curated commit.
    """

class Ontology(DiGraphAggregate):
    version: Version|VersionStored

    licence: int | None = None  # id for internal LegalReference
    copyright: int | None = None  # id for internal LegalReference

    @computed_field
    @property
    def root(self) -> StoredModel:
        return self.version

    @property
    def protected(self) -> [str|bool]:
        if isinstance(self.version, VersionStored):
            return "Stored ontology is protected"
        else:
            return False

    def get_entries(
            self,
            entry: int | str | None = None,
            label: str | None= None
    ) -> Generator[Tuple[int,OntologyEntry], None, None]:
        if isinstance(entry, int) and entry in self.graph:
            model = self.graph.nodes[entry].get('model')
            if label is None or model.label == label:
                yield entry, model
        else:
            for i, d in self.graph.nodes(data=True):
                if all([
                    label is None or d['label'] == label,
                    entry is None or entry.casefold() in d['model'].names_lower
                ]):
                    yield i, d['model']

    def get_entry(self, entry: int|str|None = None, label:str = None) -> Tuple[int, OntologyEntry]|None:
        """
        :param entry: Integer ID or str for name or synonym lookup
        :param label: Label for label lookup
        :return: Returns a tuple, with the integer reference then the entry or None
        """
        try:
            return next(self.get_entries(entry=entry, label=label))
        except StopIteration:
            return None

    def _add_entry(
            self,
            entry: OntologyEntry,
            parents: List[int] = None,
            children: List[int] = None
    ) -> int:
        # ensure same class doesn't exist with the given name/synonym
        if self.get_entry(entry.name, label=entry.label):
            raise ValueError("This name already used for this class")
        if entry.abbreviation is not None and self.get_entry(entry.abbreviation, label=entry.label):
            raise ValueError("This abbreviation already used for this class")
        for s in entry.synonyms:
            if self.get_entry(s, label=entry.label):
                raise ValueError("A synonym for this entry is already described for this class")

        temp_id = self._add_node(entry)
        parents = [(p, temp_id, {'label': OntologyRelationshipLabel.RELATES_TO}) for p in parents] if parents else None
        children = [(temp_id, c, {'label': OntologyRelationshipLabel.RELATES_TO}) for c in children] if children else None
        if parents is not None:
            self._add_edges(parents)
        if children is not None:
            self._add_edges(children)
        return temp_id

    def add_relationship(
            self,
            source_id: int,
            sink_id: int,
            label: OntologyRelationshipLabel,
            **kwargs
    ):
        self._add_edge(source_id, sink_id, label=label, **kwargs)

    def add_term(
            self,
            term: Term,
            parents: List[int] = None,
            children: List[int] = None
    ) -> int:
        return self._add_entry(term, parents, children)

    def add_observation_method(self, method: ObservationMethod, parents: List[int] = None, children: List[int] = None) -> int:
        return self._add_entry(method, parents, children)

    def add_subject(self, subject: Subject, parents: List[int] = None, children: List[int] = None) -> int:
        return self._add_entry(subject, parents, children)

    def increment_edge_rank(self, source_id, sink_id):
        self.graph.edges[source_id, sink_id]['rank'] += 1

    def add_category(
            self,
            category: ScaleCategory|int,
            scale: int|None = None,
            rank: int|None = None,
            parents: List[int] = None,
            children: List[int] = None
    ):
        if isinstance(category, ScaleCategory):
            category_id = self._add_entry(category, parents, children)
        elif isinstance(category, int):
            if self.get_entry(category, label=ScaleCategory.label) is None:
                raise ValueError("Category does not exist")
            category_id = category
        else:
            raise ValueError("Category must be of type ScaleCategory or an integer reference to such in the graph")

        if rank is not None and scale is None:
            raise ValueError("Rank can only be set in relation to a given scale, expected a scale ID")
        if scale is not None:
            scale_tuple = self.get_entry(scale, label=Scale.label)
            if scale_tuple is None:
                raise ValueError("Provided scale not found")

            scale_id, scale_model = scale_tuple
            if scale_model.type == ScaleType.NOMINAL:
                self.add_relationship(
                    source_id=scale,
                    sink_id=category_id,
                    label=OntologyRelationshipLabel.HAS_CATEGORY
                )
            elif scale_model.type == ScaleType.ORDINAL:
                indices, existing_categories, ranks = self.get_scale_categories(scale)
                if rank is None:
                    if ranks:
                        # just adding one to the highest current rank (sorted already)
                        rank = ranks[-1] + 1
                    else:
                        rank = 0
                else:
                    if rank <= ranks[-1]:
                        insertion_point = bisect.bisect_left(ranks, rank)
                        for category_index in indices[insertion_point:]:
                            self.increment_edge_rank(scale, category_index)
                self.add_relationship(
                    source_id=scale,
                    sink_id=category_id,
                    label=OntologyRelationshipLabel.HAS_CATEGORY,
                    rank=rank
                )
            else:
                raise ValueError("Only ordinal and nominal scale types can have categories")
        return category_id

    def add_scale(
            self,
            scale: Scale,
            categories: List[ScaleCategory|int] = None,
            parents: List[int] = None,
            children: List[int] = None
    ) -> int:
        scale_id = self._add_entry(scale, parents, children)
        if categories is not None:
            for rank, category in enumerate(categories):
                if isinstance(category, int):
                    category_id = category
                elif isinstance(category, ScaleCategory):
                    if category.id is not None:
                        category_id = category.id
                    else:
                        category_id = self.add_category(category)
                else:
                    raise ValueError(
                        'Expected a list of ScaleCategories'
                        ' or integer reference to one in the graph'
                        ' for argument categories'
                    )
                self._add_edge(
                    source_id=scale_id,
                    sink_id=category_id,
                    label=OntologyRelationshipLabel.HAS_CATEGORY,
                    rank=rank
                )
        return scale_id

    def get_scale_categories(self, scale_id: int) -> Tuple[List[int], List[ScaleCategory], List[int]|None]:
        """
        :param scale_id: Integer reference for Scale entry
        :return: Returns a tuple,
            first element is the list of category indices in the graph
            second element is a list of ScaleCategory instances,
            If the scale type is Nominal the third element is None
            If the scale type is Ordinal the third element is a list of ranks stored for these elements
                # todo this may be unnecessary but would be needed to support incomplete or possibly weighted? ranking systems
                #   todo: consider if this type be float in that case.
        """
        _, scale = self.get_entry(scale_id)
        if not isinstance(scale, Scale):
            raise ValueError("The provided entry id does not correspond to a scale")

        if scale.type == ScaleType.NOMINAL:
            category_indices = []
            for u, v, d in self.graph.out_edges(scale_id, data=True):
                if d['label'] == OntologyRelationshipLabel.HAS_CATEGORY:
                    category_indices.append(v)
            entry_tuples = [self.get_entry(c) for c in category_indices]
            indices: List[int] = [i[0] for i in entry_tuples]
            categories: List[ScaleCategory] = [i[1] for i in entry_tuples]
            return indices, categories, None
        elif scale.type == ScaleType.ORDINAL:
            category_index_rank = []
            for u, v, d in self.graph.out_edges(scale_id, data=True):
                if d['label'] == OntologyRelationshipLabel.HAS_CATEGORY:
                    category_index_rank.append((v, d['rank']))
            category_index_rank.sort(key=lambda x: x[1])
            ranks: List[int] = [c[1] for c in category_index_rank]
            entry_tuples = [self.get_entry(c[0]) for c in category_index_rank]
            indices: List[int] = [i[0] for i in entry_tuples]
            categories: List[ScaleCategory] = [i[1] for i in entry_tuples]
            return indices, categories, ranks
        else:
            raise ValueError("The provided scale reference is not ordinal or nominal and so does not have scales")

    def add_trait(
            self,
            trait: Trait,
            subjects: List[int],
            parents: List[int] = None,
            children: List[int] = None
    ) -> int:
        if not subjects:
            raise ValueError("No subjects specified")

        trait_id = self._add_entry(trait, parents, children)
        for subject in subjects:
            self._add_edge(
                source_id=subject,
                sink_id=trait_id,
                label=OntologyRelationshipLabel.HAS_TRAIT
            )
        return trait_id

    def get_trait_subjects(self, trait_id) -> Tuple[List[int], List[Subject]]:
        subject_indices = []
        for u, v, d in self.graph.in_edges(trait_id, data=True):
            if d['label'] == OntologyRelationshipLabel.HAS_TRAIT:
                subject_indices.append(u)
        indices = subject_indices
        subjects: List[Subject] = [self.get_entry(u)[1] for u in subject_indices]
        return indices, subjects

    def get_subject_traits(self, subject_id) -> Tuple[List[int], List[Trait]]:
        trait_indices = []
        for u, v, d in self.graph.out_edges(subject_id, data=True):
            if d['label'] == OntologyRelationshipLabel.HAS_TRAIT:
                trait_indices.append(v)
        indices = trait_indices
        traits: List[Trait] = [self.get_entry(v)[1] for v in trait_indices]
        return indices, traits

    def _link_method_and_scale(self, source_id, method_id, scale_id):
        if not isinstance(self.get_entry(method_id)[1], ObservationMethod):
            raise ValueError("The provided entry ID does not correspond to a Method")
        self._add_edge(
            source_id=source_id,
            sink_id=method_id,
            label=OntologyRelationshipLabel.USES_METHOD
        )
        if not isinstance(self.get_entry(scale_id)[1], Scale):
            raise ValueError("The provided entry ID does not correspond to a Scale")
        self._add_edge(
            source_id=source_id,
            sink_id=scale_id,
            label=OntologyRelationshipLabel.USES_SCALE
        )

    def add_variable(
            self,
            variable: Variable,
            trait: int,
            method: int,
            scale: int,
            parents: List[int] = None,
            children: List[int] = None
    ) -> int:
        if not self.get_entry(trait, label=Trait.label):
            raise ValueError("The provided trait ID does not correspond to a Trait")
        if not self.get_entry(method, label=ObservationMethod.label):
            raise ValueError("The provided method ID does not correspond to an ObservationMethod")
        if not self.get_entry(scale, label=Scale.label):
            raise ValueError("The provided scale ID does not correspond to an Scale")

        variable_id = self._add_entry(variable, parents, children)
        self._add_edge(source_id=variable_id, sink_id=trait, label=OntologyRelationshipLabel.DESCRIBES_TRAIT)
        self._link_method_and_scale(variable_id, method, scale)
        return variable_id

    def add_condition(self, condition: Condition, parents: List[int] = None, children: List[int] = None) -> int:
        return self._add_entry(condition, parents, children)

    def add_parameter(
            self,
            parameter: Parameter,
            condition: int,
            method: int,
            scale: int,
            parents: List[int] = None,
            children: List[int] = None
    ) -> int:
        parameter_id = self._add_entry(parameter, parents, children)
        if not isinstance(self.get_entry(condition)[1], Condition):
            raise ValueError("The provided entry ID does not correspond to a Condition")
        self._add_edge(source_id=parameter_id, sink_id=condition, label=OntologyRelationshipLabel.DESCRIBES_CONDITION)
        self._link_method_and_scale(parameter_id, method, scale)
        return parameter_id

    def add_exposure(self, exposure: Exposure, parents: List[int] = None, children: List[int] = None) -> int:
        return self._add_entry(exposure, parents, children)

    def add_event(
            self,
            event: EventType,
            exposure: int,
            method: int,
            scale: int,
            parents: List[int] = None,
            children: List[int] = None
    ) -> int:
        event_id = self._add_entry(event, parents, children)
        if not isinstance(self.get_entry(exposure)[1], Exposure):
            raise ValueError("The provided entry ID does not correspond to an Exposure")
        self._add_edge(source_id=event_id, sink_id=exposure, label=OntologyRelationshipLabel.DESCRIBES_EXPOSURE)
        self._link_method_and_scale(event_id, method, scale)
        return event_id

    def add_location(self, location: LocationType, parents: List[int] = None, children: List[int] = None) -> int:
        return self._add_entry(location, parents, children)

    def add_layout(self, layout: LayoutType, parents: List[int] = None, children: List[int] = None) -> int:
        return self._add_entry(layout, parents, children)

    def add_design(self, design: Design, parents: List[int] = None, children: List[int] = None) -> int:
        return self._add_entry(design, parents, children)

    def add_role(self, role: Role, parents: List[int] = None, children: List[int] = None) -> int:
        return self._add_entry(role, parents, children)

    def add_title(self, title: Title, parents: List[int] = None, children: List[int] = None) -> int:
        return self._add_entry(title, parents, children)

    def add_germplasm_method(self, method: GermplasmMethod, parents: List[int] = None, children: List[int] = None) -> int:
        return self._add_entry(method , parents, children)

    @computed_field
    def entries(self) -> List[OntologyEntry]:
        return nx.get_node_attributes(self.graph, 'model')

