import networkx as nx

from pydantic import BaseModel, computed_field
from src.breedgraph.domain.model.base import StoredModel, DiGraphAggregate

from .subjects import Subject
from .entries import OntologyEntry
from .variables import Scale, ScaleCategory, ObservationMethod, Trait, Variable
from .enums import ObservationMethodType, ScaleType, OntologyRelationshipLabel, VersionChange, AxisType

from .parameters import Condition, Parameter, ControlMethod
from .event_type import Exposure, EventType

from functools import total_ordering
from typing import List, Tuple, ClassVar, Generator


@total_ordering
class Version(BaseModel):
    major: int = 0
    minor: int = 0
    patch: int = 0
    comment: str = 'default'

    @property
    def name(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}-{self.comment}"

    def as_tuple(self):
        return tuple([self.major, self.minor, self.patch])

    def __gt__(self, other):
        return self.as_tuple() > other.as_tuple()

    def __eq__(self, other):
        return self.as_tuple() == other.as_tuple()

    def increment(self, version_change: VersionChange = VersionChange.PATCH):
        if version_change is VersionChange.PATCH:
            self.patch += 1
        elif version_change is VersionChange.MINOR:
            self.minor += 1
            self.patch = 0
        else:
            self.major += 1
            self.minor = 0
            self.patch = 0

class VersionStored(Version, StoredModel):
    label: ClassVar[str] = 'OntologyVersion'
    plural: ClassVar[str] = 'OntologyVersions'
    """
        Ontology version is associated with it's respective entries.
        When a new term is added, this means a new version, but may be a minor/patch version
        Major version changes should reflect a curated commit.
    """

class OntologyOutput(OntologyEntry):
    version: VersionStored

    label: str  # https://github.com/pydantic/pydantic/issues/7009
    # waiting for the above issue to be resolved, currently raises UserWarning
    parents: list[int] = list()
    children: list[int] = list()
    """ObservationMethodType for ObservationMethod"""
    observation_type: ObservationMethodType|None = None
    """ScaleType for Scale"""
    scale_type: ScaleType|None = None
    """Subjects for trait"""
    subjects: List[int] = list()
    """Categories for scale"""
    categories: List[int] = list()
    """Trait for variable"""
    trait: int|None = None
    """Condition for parameter"""
    condition: int|None = None
    """Exposure for event"""
    exposure: int|None = None
    """ControlMethod or ObservationMethod for variable/parameter/event"""
    method: int|None = None
    """Scale for variable/parameter/event"""
    scale: int|None = None
    """Rank for ordinal scale categories"""
    rank: int|None = None
    """Axes for LayoutType entries"""
    axes: List[AxisType] = list()

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
        if isinstance(entry, int):
            if entry in self._graph:
                model = self._graph.nodes[entry].get('model')
                if label is None or model.label == label:
                    yield entry, model
            yield None
        else:
            for i, d in self._graph.nodes(data=True):
                if all([
                    label is None or d['label'] == label,
                    entry is None or entry.casefold() in [n.casefold() for n in d['model'].names]
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

    def get_entry_model(self, entry: int|str|None = None, label:str = None) -> OntologyEntry|None:
        """
        :param entry: Integer ID or str for name or synonym lookup
        :param label: Label for label lookup
        :return: Returns the matching entry or None
        """
        try:
            entry_model = next(self.get_entries(entry=entry, label=label))
            if entry_model is None:
                return None
            else:
                return entry_model[1]
        except StopIteration:
            return None

    def _add_entry(
            self,
            entry: OntologyEntry,
            parents: List[int] = None,
            children: List[int] = None
    ) -> int:
        # ensure same class doesn't exist with the given name/synonym, unless it is a category
        if isinstance(entry, ScaleCategory):
            # allow duplicate names for categories,
            # just prevent name collisions when linking to scale
            pass
        else:
            for n in entry.names:
                if match := self.get_entry_model(n, label=entry.label):
                    raise ValueError(f"Name {n} is already used in this ontology for {entry.label}: {match.names}")

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

    def add_entry(
            self,
            entry: OntologyEntry,
            parents: List[int] = None,
            children: List[int] = None,
            **kwargs
    ):
        temp_id = self._add_entry(entry, parents, children)
        if isinstance(entry, ScaleCategory):
            if 'scale' in kwargs:
                self.link_category(temp_id, scale=kwargs.get('scale'), rank=kwargs.get('rank'))
        elif isinstance(entry, Scale) and 'categories' in kwargs:
            self.link_scale(temp_id, categories=kwargs.get('categories'))
        elif isinstance(entry, Trait):
            if not 'subjects' in kwargs:
                raise ValueError("Trait entries require subjects")
            self.link_trait(temp_id, subjects=kwargs.get('subjects'))
        elif isinstance(entry, Variable):
            if not all([s in kwargs for s in ['trait','method','scale']]):
                raise ValueError("Variable entries require trait, method and scale")
            self.link_variable(
                temp_id,
                trait=kwargs.get('trait'),
                method=kwargs.get('method'),
                scale=kwargs.get('scale')
            )
        elif isinstance(entry, Parameter):
            if not all([s in kwargs for s in ['condition','method','scale']]):
                raise ValueError("Parameter entries require condition, method and scale")
            self.link_parameter(
                temp_id,
                condition=kwargs.get('condition'),
                method=kwargs.get('method'),
                scale=kwargs.get('scale')
            )
        elif isinstance(entry, EventType):
            if not all([s in kwargs for s in ['exposure','method','scale']]):
                raise ValueError("EventType entries require exposure, method and scale")
            self.link_event(
                temp_id,
                exposure=kwargs.get('exposure'),
                method=kwargs.get('method'),
                scale=kwargs.get('scale')
            )
        return temp_id

    def increment_edge_rank(self, source_id, sink_id):
        self._graph.edges[source_id, sink_id]['rank'] += 1

    def link_category(
            self,
            category_id: int,
            scale: int,
            rank: int|None = None
    ):
        if self.get_entry(category_id, label=ScaleCategory.label) is None:
            raise ValueError("Category does not exist")

        scale_model = self.get_entry_model(scale)
        if not isinstance(scale_model, Scale):
            raise TypeError("Scale ID must be an instance of Scale")
        elif not scale_model.scale_type in [ScaleType.NOMINAL, ScaleType.ORDINAL]:
            raise TypeError("Only Nominal and Ordinal Scales may have ontology ScaleCategories linked")

        new_category = self.get_entry_model(category_id)
        existing_category_ids = self.get_category_ids(scale)
        for e in existing_category_ids:
            existing_category = self.get_entry_model(e)
            if match := set(new_category.names).intersection(existing_category.names):
                raise ValueError(f"Existing category {e} for this scale uses a common name: {match}")

            if rank is not None:
                existing_category_rank = self.get_rank(e)
                if rank <= existing_category_rank:
                    self.increment_edge_rank(scale, e)

        self.add_relationship(
            source_id=scale,
            sink_id=category_id,
            label=OntologyRelationshipLabel.HAS_CATEGORY,
            rank=len(existing_category_ids) if rank is None else rank
        )

    def link_scale(
            self,
            scale_id: int,
            categories: List[int] = None
    ):
        scale_model = self.get_entry_model(scale_id)
        if not isinstance(scale_model, Scale):
            raise TypeError("Scale ID is not a Scale")

        if categories is not None:
            if scale_model.scale_type in [ScaleType.NOMINAL, ScaleType.ORDINAL]:
                for rank, category in enumerate(categories):
                    self._add_edge(
                        source_id=scale_id,
                        sink_id=category,
                        label=OntologyRelationshipLabel.HAS_CATEGORY,
                        rank=rank
                    )

    def link_trait(
            self,
            trait_id: int,
            subjects: List[int] = None
    ):
        if not subjects:
            raise ValueError("No subjects specified")
        for subject_id in subjects:
            _, subject = self.get_entry(subject_id)
            if not isinstance(subject, Subject):
                raise TypeError("Subject reference is not a subject")
            self._add_edge(
                source_id=subject_id,
                sink_id=trait_id,
                label=OntologyRelationshipLabel.HAS_TRAIT
            )


    def get_subjects(self, trait_id) -> Tuple[List[int], List[Subject]]:
        subject_ids = self.get_subject_ids(trait_id)
        subjects: List[Subject] = [self.get_entry(u)[1] for u in subject_ids]
        return subject_ids, subjects


    def get_traits(self, subject_id) -> Tuple[List[int], List[Trait]]:
        trait_ids = self.get_trait_ids(subject_id)
        traits: List[Trait] = [self.get_entry(v)[1] for v in trait_ids]
        return trait_ids, traits

    def _link_method_and_scale(self, source_id, method_id, scale_id):
        _, method_entry = self.get_entry(method_id)
        _, source_entry = self.get_entry(source_id)
        _, scale = self.get_entry(scale_id)

        if isinstance(source_entry, Variable) and not isinstance(method_entry, ObservationMethod):
            raise ValueError("Variable entries require ObservationMethod")
        elif isinstance(source_entry, Parameter) and not isinstance(method_entry, ControlMethod):
            raise ValueError("Parameter entries require ControlMethod")
        elif isinstance(source_entry, EventType) and not isinstance(method_entry, (ObservationMethod, ControlMethod)):
            raise ValueError("EventType entries require ObservationMethod or ControlMethod")
        elif not isinstance(source_entry, (Variable|Parameter|EventType)):
            raise ValueError("Unsupported source type")
        self._add_edge(
            source_id=source_id,
            sink_id=method_id,
            label=OntologyRelationshipLabel.USES_METHOD
        )

        if not isinstance(scale, Scale):
            raise ValueError("The provided source id does not correspond to a scale")
        self._add_edge(
            source_id=source_id,
            sink_id=scale_id,
            label=OntologyRelationshipLabel.USES_SCALE
        )

    def link_variable(
            self,
            variable_id: int,
            trait: int = None,
            method: int = None,
            scale: int = None
    ) -> int:
        if not (trait and method and scale):
            raise TypeError("Variable requires trait method and scale")

        if not self.get_entry(trait, label=Trait.label):
            raise ValueError("The provided trait ID does not correspond to a Trait")
        self._add_edge(source_id=variable_id, sink_id=trait, label=OntologyRelationshipLabel.DESCRIBES_TRAIT)
        self._link_method_and_scale(variable_id, method, scale)
        return variable_id

    def link_parameter(
            self,
            parameter_id: int,
            condition: int,
            method: int,
            scale: int,
    ) -> int:
        if not self.get_entry(condition, label=Condition.label):
            raise ValueError("The provided entry ID does not correspond to a Condition")

        self._add_edge(source_id=parameter_id, sink_id=condition, label=OntologyRelationshipLabel.DESCRIBES_CONDITION)
        self._link_method_and_scale(parameter_id, method, scale)
        return parameter_id

    def link_event(
            self,
            event_id: int,
            exposure: int,
            method: int,
            scale: int
    ) -> int:
        if not self.get_entry(exposure, Exposure.label):
            raise ValueError("The provided entry ID does not correspond to an Exposure")
        self._add_edge(source_id=event_id, sink_id=exposure, label=OntologyRelationshipLabel.DESCRIBES_EXPOSURE)
        self._link_method_and_scale(event_id, method, scale)
        return event_id

    @computed_field
    def entries(self) -> List[OntologyEntry]:
        return nx.get_node_attributes(self._graph, 'model')

    def get_parent_ids(self, node_id) -> List[int]:
        parent_ids = []
        for u, v, d in self._graph.in_edges(node_id, data=True):
            if d['label'] == OntologyRelationshipLabel.RELATES_TO:
                parent_ids.append(u)
        return parent_ids

    def get_children_ids(self, node_id) -> List[int]:
        children_ids = []
        for u, v, d in self._graph.out_edges(node_id, data=True):
            if d['label'] == OntologyRelationshipLabel.RELATES_TO:
                children_ids.append(u)
        return children_ids

    def get_trait_id(self, variable_id) -> int:
        for u, v, d in self._graph.out_edges(variable_id, data=True):
            if d['label'] == OntologyRelationshipLabel.DESCRIBES_TRAIT:
                return v

    def get_subject_ids(self, trait_id: int) -> List[int]:
        subject_ids = []
        for u, v, d in self._graph.in_edges(trait_id, data=True):
            if d['label'] == OntologyRelationshipLabel.HAS_TRAIT:
                subject_ids.append(u)
        return subject_ids

    def get_trait_ids(self, subject_id) -> List[int]:
        trait_ids = []
        for u, v, d in self._graph.out_edges(subject_id, data=True):
            if d['label'] == OntologyRelationshipLabel.HAS_TRAIT:
                trait_ids.append(v)
        return trait_ids

    def get_category_ids(self, scale_id: int):
        scale = self.get_entry_model(scale_id)

        if not isinstance(scale, Scale):
            return []

        if scale.scale_type == ScaleType.NOMINAL:
            category_indices = []
            for u, v, d in self._graph.out_edges(scale_id, data=True):
                if d['label'] == OntologyRelationshipLabel.HAS_CATEGORY:
                    category_indices.append(v)
            return category_indices

        elif scale.scale_type == ScaleType.ORDINAL:
            index_rank = []
            for u, v, d in self._graph.out_edges(scale_id, data=True):
                if d['label'] == OntologyRelationshipLabel.HAS_CATEGORY:
                    index_rank.append((v, d['rank']))
            index_rank.sort(key=lambda x: x[1])
            indices: List[int] = [i[0] for i in index_rank]
            return indices
        else:
            return []

    def get_condition_id(self, parameter_id) -> int:
        for u, v, d in self._graph.out_edges(parameter_id, data=True):
            if d['label'] == OntologyRelationshipLabel.DESCRIBES_CONDITION:
                return v

    def get_exposure_id(self, event_id) -> int:
        for u, v, d in self._graph.out_edges(event_id, data=True):
            if d['label'] == OntologyRelationshipLabel.DESCRIBES_EXPOSURE:
                return v

    def get_method_id(self, entry_id) -> int:
        for u, v, d in self._graph.out_edges(entry_id, data=True):
            if d['label'] == OntologyRelationshipLabel.USES_METHOD:
                return v

    def get_scale_id(self, entry_id) -> int:
        for u, v, d in self._graph.out_edges(entry_id, data=True):
            if d['label'] == OntologyRelationshipLabel.USES_SCALE:
                return v

    def get_rank(self, category_id) -> int:
        for u, v, d in self._graph.in_edges(category_id, data=True):
            if d['label'] == OntologyRelationshipLabel.HAS_CATEGORY:
                return d.get('rank')

    def to_output(self, node_id) -> OntologyOutput:
        model = self.get_entry_model(node_id)
        model_dict = model.model_dump()
        return OntologyOutput(
            **model_dict,
            version=self.version,
            label=model.label,
            parents=self.get_parent_ids(node_id),
            children=self.get_children_ids(node_id),
            subjects=self.get_subject_ids(node_id),
            categories=self.get_category_ids(node_id),
            trait=self.get_trait_id(node_id),
            condition=self.get_condition_id(node_id),
            exposure=self.get_exposure_id(node_id),
            method=self.get_method_id(node_id),
            scale=self.get_scale_id(node_id),
            rank=self.get_rank(node_id),
        )

    def to_output_map(self) -> dict[int, OntologyOutput]:
        return {node: self.to_output(node) for node in self._graph}
