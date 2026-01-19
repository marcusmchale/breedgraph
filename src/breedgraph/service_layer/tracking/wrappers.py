"""
I considered the adapter and descriptor patterns during design of these wrappers.
see https://docs.python.org/3/howto/descriptor.html#descriptorhowto

Changes to primitive types are recorded in their parent objects Tracking wrapper (list/set/dict/graph/other)
Changes to list/set/dict/graph are recorded in the respective Tracking wrapper, i.e. added/removed/changed items.
Changes to attributes of an object are also recorded in the wrapper, however new attributes/removed attributes are not.

"""
import networkx as nx
from numpy import datetime64
from wrapt import ObjectProxy
from enum import Enum
from collections import defaultdict
from collections.abc import MutableSequence, MutableSet, MutableMapping
from dataclasses import is_dataclass, fields
from typing import (
    List, Set, Dict, Hashable, Any,
    Union, TypeVar, Self, ClassVar,
    overload, Callable, Protocol, runtime_checkable,
    Generator
)
import copy


import logging

logger = logging.getLogger(__name__)

# Primitive type changes that don't require nested tracking
primitives = (int, float, str, bool, bytes, Enum, datetime64)

@runtime_checkable
class TrackableProtocol(Protocol):
    """Protocol defining the common interface for all trackable objects"""
    _self_on_changed: list[Callable]

    @property
    def changed(self) -> Set[Union[str, int, Hashable]]:
        """Return set of changed attributes/indices/keys"""
        ...

    @property
    def on_changed(self) -> Callable:
        """Return callback function for change events"""
        ...

    def on_changed_attr(self, attr: Union[str, int, Hashable]) -> None:
        """Handle change to a specific attribute/index/key"""
        ...

    def reset_tracking(self) -> None:
        """Reset all tracking information"""
        ...


def _create_tracked_class_for_dataclass(wrapped_class):
    """Create a TrackedObject subclass that mimics the dataclass for _is_dataclass_instance checks"""
    class_name = f"Tracked{wrapped_class.__name__}"

    # Create a new class that inherits from TrackedObject but has the dataclass attributes
    tracked_class = type(class_name, (TrackedObject,), {
        '__dataclass_fields__': wrapped_class.__dataclass_fields__,
        '__dataclass_params__': getattr(wrapped_class, '__dataclass_params__', None),
    })

    return tracked_class

# custom asdict to use instead of dataclasses asdict and _asdict_inner functions
# ensuring the objects are recursively unwrapped
def asdict(obj, *, dict_factory=dict):
    """Custom asdict implementation that handles tracked objects"""
    if is_dataclass(obj):
        # Handle dataclass objects
        result = {}
        for field in fields(obj):
            value = getattr(obj, field.name)
            result[field.name] = _asdict_inner(value, dict_factory)
        return dict_factory(result.items())
    else:
        # Handle non-dataclass objects
        return _asdict_inner(obj, dict_factory)


def _asdict_inner(obj, dict_factory):
    """Internal function that handles the recursive conversion"""
    # Handle tracked objects first
    if isinstance(obj, TrackableProtocol):
        # Unwrap and process the wrapped object
        obj = obj.__wrapped__

    # Handle different types
    if is_dataclass(obj):
        # Recursively process dataclass fields
        result = {}
        for field in fields(obj):
            value = getattr(obj, field.name)
            result[field.name] = _asdict_inner(value, dict_factory)
        return dict_factory(result.items())
    elif isinstance(obj, dict):
        return type(obj)((_asdict_inner(k, dict_factory), _asdict_inner(v, dict_factory))
                         for k, v in obj.items())
    elif isinstance(obj, (list, tuple)):
        return type(obj)(_asdict_inner(v, dict_factory) for v in obj)
    elif isinstance(obj, set):
        return set(_asdict_inner(v, dict_factory) for v in obj)
    else:
        # For primitives and other objects, return as-is
        return obj


class TrackedFactory:
    """Factory class for creating appropriate tracking wrappers"""

    @staticmethod
    def create(obj, on_changed: Callable = lambda: None) -> TrackableProtocol:
        if isinstance(obj, list):
            return TrackedList(obj, on_changed)
        elif isinstance(obj, set):
            return TrackedSet(obj, on_changed)
        elif isinstance(obj, dict):
            return TrackedDict(obj, on_changed)
        elif isinstance(obj, nx.DiGraph):
            return TrackedGraph(obj, on_changed)
        else:
            # Check if it's a dataclass and create appropriate tracked class
            if hasattr(obj, '__dataclass_fields__'):
                tracked_class = _create_tracked_class_for_dataclass(obj.__class__)
                return tracked_class(obj, on_changed)
            else:
                # Assume it's an Aggregate or similar non-dataclass object
                return TrackedObject(obj, on_changed)


TTracked = TypeVar('TTracked')

@overload
def tracked(obj: List[TTracked], on_changed: Callable = lambda: None) -> Union['TrackedList', List[TTracked]]: ...

@overload
def tracked(obj: Set[TTracked], on_changed: Callable = lambda: None) -> Union['TrackedSet', Set[TTracked]]: ...

@overload
def tracked(obj: Dict[str, TTracked], on_changed: Callable = lambda: None) -> Union['TrackedDict', Dict[str, TTracked]]: ...

@overload
def tracked(obj: nx.DiGraph, on_changed: Callable = lambda: None) -> Union['TrackedGraph', nx.DiGraph]: ...

@overload
def tracked(obj: Any, on_changed: Callable = lambda: None) -> Union['TrackedObject', TTracked]: ...

def tracked(obj: Any, on_changed: Callable = lambda: None) -> Union[TrackableProtocol, TTracked]:
    """
    Create a tracked version of an object that maintains the original type for type checking.
    This function acts as a type-preserving wrapper around TrackedFactory.create().
    """
    tracked_obj = TrackedFactory.create(obj, on_changed)
    return tracked_obj


class TrackedObject(ObjectProxy, TrackableProtocol):
    """
    Tracks add, remove and changes to a dataclass object
    """
    _private_tracked_attrs: ClassVar[List[str]] = ['_graph']
    _skip_tracking_attrs: ClassVar[List[str]] = ['id', 'events']

    def __init__(self, wrapped, on_changed: Callable = lambda: None):
        super().__init__(wrapped)
        self._self_changed: Set[str] = set()
        self._self_on_changed = [on_changed]

        # Track attributes
        for attr_name in dir(wrapped):
            # Skip dunder attributes
            if attr_name.startswith('__'):
                continue

            # Track private attributes if they're in the allowed list
            if attr_name.startswith('_'):
                if attr_name not in self._private_tracked_attrs:
                    continue
            # Track public attributes (excluding methods, properties, and skip list)
            else:
                attr_value = getattr(wrapped, attr_name)
                class_attr = getattr(type(wrapped), attr_name, None)
                if (callable(attr_value) or
                        isinstance(class_attr, property) or
                        attr_name in self._skip_tracking_attrs):
                    continue

            try:
                value = getattr(wrapped, attr_name)
                if value is not None:
                    self.__wrapped__.__setattr__(attr_name, self._get_tracked(attr_name))
            except (AttributeError, TypeError):
                # Skip attributes that can't be set
                continue

    def __setattr__(self, key, value):
        if all([
            key not in ('_self_changed', '_self_on_changed'),
            hasattr(self, key) and getattr(self, key) != value
        ]):
            self._self_changed.add(key)
            for callback in self._self_on_changed:
                callback()

        self.__wrapped__.__setattr__(key, value)

    def silent_setattr(self, key, value):
        self.__wrapped__.__setattr__(key, value)

    def _get_tracked(self, attr):
        value = getattr(self.__wrapped__, attr)
        on_changed = lambda: self.on_changed_attr(attr)

        # Return primitive types unchanged - they don't require nested tracking
        if value is None or isinstance(value, primitives):
            return value
        if isinstance(value, TrackableProtocol):
            logger.debug("Value already tracked, appending on_changed callback")
            value._self_on_changed.append(on_changed)
            return value
        return tracked(value, on_changed)

    @property
    def changed(self) -> Set[str]:
        return self._self_changed

    @property
    def added_models(self) -> List[Self]:
        """
        :return: Returns a list of added models from an aggregate
        """
        added_models: List[Self] = list()
        for attr in self.changed:
            value = getattr(self.__wrapped__, attr)
            if hasattr(value, 'collect_added_models'):
                value.collect_added_models(added_models)

        return added_models

    @property
    def removed_models(self) -> List[Self]:
        """
        :return: Returns a list of removed models from an aggregate
        """
        removed_models: List[Self] = list()
        for attr in self.changed:
            value = getattr(self.__wrapped__, attr)
            if hasattr(value, 'collect_removed_models'):
                value.collect_removed_models(removed_models)
        return removed_models

    @property
    def changed_models(self) -> List[Self]:
        """
        :return: Returns a list of changed models from an aggregate
        """
        changed_models: List[Self] = list()
        if self.changed and hasattr(self, 'id'):
            changed_models.append(self)

        for attr in self.changed:
            value = getattr(self.__wrapped__, attr)
            if not isinstance(value, (TrackedList, TrackedSet, TrackedDict, TrackedGraph)) and hasattr(value, 'id'):
                changed_models.append(value)
            elif hasattr(value, 'collect_changed_models'):
                value.collect_changed_models(changed_models)

        return changed_models

    @property
    def on_changed(self) -> Callable:
        def call_all():
            for callback in self._self_on_changed:
                callback()
        return call_all

    def on_changed_attr(self, attr: str):
        self.changed.add(attr)
        self.on_changed()

    def reset_tracking(self):
        self.changed.clear()
        # Reset tracking for all attributes (including private ones like _graph)
        for attr_name in dir(self.__wrapped__):
            if not callable(getattr(self.__wrapped__, attr_name, None)):
                value = getattr(self.__wrapped__, attr_name)
                if hasattr(value, 'reset_tracking'):
                    try:
                        value.reset_tracking()
                    except TypeError:
                        logger.debug("expected reset_tracking to be callable")

    def model_dump(self):
        return self.__wrapped__.model_dump()

    @property
    def controlled_models(self):
        """
        Override controlled_models to include removed models for access control.
        """
        base_controlled_models = []
        if hasattr(self.__wrapped__, 'controlled_models'):
            base_controlled_models = self.__wrapped__.controlled_models

        removed_controlled_models = []
        for removed_model in self.removed_models:
            if hasattr(removed_model, 'label') and hasattr(removed_model, 'id'):
                removed_controlled_models.append(removed_model)

        return base_controlled_models + removed_controlled_models

    def __deepcopy__(self, *args, **kwargs):
        self.__wrapped__ = copy.deepcopy(self.__wrapped__, *args, **kwargs)


class TrackedList(ObjectProxy, MutableSequence, TrackableProtocol):
    """
    Tracks add, remove and changes to a list
    """

    def __init__(self, d: List = None, on_changed: Callable = lambda: None):
        if d is None:
            d = list()
        elif hasattr(d, '__iter__') and not isinstance(d, (str, bytes)):
            d = list(d)
        elif not isinstance(d, list):
            d = [d]
        super().__init__(d)

        self._self_changed: Set[int] = set()  # record the index of any changed element
        self._self_added: Set[int] = set() # record the index of any added element
        self._self_removed = list()

        self._self_on_changed = [on_changed]

        for i, value in enumerate(self):
            self.__wrapped__.__setitem__(i, self._get_tracked(i, value))

    @property
    def changed(self) -> Set[int]:
        return self._self_changed

    def collect_added_models(self, added_models: List):
        for i in self.added:
            value = self.__wrapped__.__getitem__(i)
            if isinstance(value, TrackedObject):
                added_models.append(value)
            elif hasattr(value, 'collect_added_models'):
                value.collect_added_models(added_models)

    def collect_removed_models(self, removed_models: List):
        for value in self.removed:
            if isinstance(value, TrackedObject):
                removed_models.append(value)
            elif hasattr(value, 'collect_removed_models'):
                value.collect_removed_models(removed_models)

    def collect_changed_models(self, changed_models: List):
        for i in self.changed:
            value = self.__wrapped__.__getitem__(i)
            if isinstance(value, TrackedObject):
                changed_models.append(value)
            elif hasattr(value, 'collect_changed_models'):
                value.collect_changed_models(changed_models)

    @property
    def added(self) -> Set[int]:
        return self._self_added

    @property
    def removed(self):
        return self._self_removed

    @property
    def on_changed(self) -> Callable:
        def call_all():
            for callback in self._self_on_changed:
                callback()
        return call_all

    def reset_tracking(self):
        self.changed.clear()
        self.added.clear()
        self.removed.clear()
        for item in self:
            if isinstance(item, TrackableProtocol):
                item.reset_tracking()

    def on_changed_item(self, i: int):
        self.changed.add(i)
        self.on_changed()

    @staticmethod
    def _shift_indices(indices: set, threshold_index: int, increment: bool = True):
        for j in indices.copy():
            if j >= threshold_index:
                indices.remove(j)
                if increment:
                    indices.add(j + 1)
                else:
                    indices.add(j - 1)

    def _get_tracked(self, i: int, value: Any):
        # Return primitive types unchanged - they don't require nested tracking
        if value is None or isinstance(value, primitives):
            return value

        if isinstance(value, TrackableProtocol):
            logger.debug("Value already tracked, adding to its callback")
            def on_changed():
                self.on_changed_item(i)
            value._self_on_changed.append(on_changed)
            return value

        on_changed = lambda: self.on_changed_item(i)
        return tracked(value, on_changed)

    def insert(self, i: int, value):  # insert is also called by append
        self._shift_indices(self.added, i, True)
        self._shift_indices(self.changed, i, True)

        self.added.add(i)

        self.__wrapped__.insert(i, self._get_tracked(i, value))
        self.on_changed()

    def remove(self, value):
        i = self.__wrapped__.index(value)
        self.__delitem__(i)

    def __setitem__(self, i: int, value):
        self.__wrapped__.__setitem__(i, self._get_tracked(i, value))
        if i>= len(self):
            self.added.add(i)
        else:
            self.changed.add(i)
        self.on_changed()

    def __delitem__(self, i: int):
        self._shift_indices(self.added, i + 1, False)
        self._shift_indices(self.changed, i + 1, False)

        value = self.__wrapped__.__getitem__(i)
        self.removed.append(value)

        self.__wrapped__.__delitem__(i)
        self.on_changed()

    def silent_remove(self, value):
        i = self.__wrapped__.index(value)
        self.__wrapped__.__delitem__(i)

    def silent_append(self, value):
        self.__wrapped__.append(self._get_tracked(len(self), value))

    def __deepcopy__(self, *args, **kwargs):
        self.__wrapped__ = copy.deepcopy(self.__wrapped__, *args, **kwargs)


class TrackedSet(ObjectProxy, MutableSet, TrackableProtocol):
    """
    Tracks add, remove and changes to a set

    Caution: Due to add/change set elements being recorded by their hash only,
     tracked sets are only safe to use where the hash is guaranteed unique

    e.g. they are not suited to collections of strings
    """

    def __init__(self, s: Set = None, on_changed: Callable = lambda: None):
        if s is None:
            s = set()
        elif not isinstance(s, set):
            s = {s}

        self._self_changed: Set[int] = set()  # record the hash of any changed element
        self._self_added: Set[int] = set() # record the hash of any added element
        self._self_removed: Set[Hashable] = set() # keep a copy of removed element

        self._self_on_changed = [on_changed]

        tracked_set = set()
        for i in s:
            tracked_set.add(self._get_tracked(i))

        super().__init__(tracked_set)

    @property
    def changed(self) -> Set[int]:
        return self._self_changed

    def collect_added_models(self, added_models: List):
        for value in self:
            if hash(value) in self.added:
                if isinstance(value, TrackedObject):
                    added_models.append(value)
                elif hasattr(value, 'collect_added_models'):
                    value.collect_added_models(added_models)


    def collect_removed_models(self, removed_models: List):
        for value in self.removed:
            if isinstance(value, TrackedObject):
                removed_models.append(value)
            elif hasattr(value, 'collect_removed_models'):
                value.collect_removed_models(removed_models)

    def collect_changed_models(self, changed_models: List):
        for value in self:
            if hash(value) in self.changed:
                if isinstance(value, TrackedObject):
                    changed_models.append(value)
                elif hasattr(value, 'collect_changed_models'):
                    value.collect_changed_models(changed_models)

    @property
    def added(self) -> Set[int]:
        return self._self_added

    @property
    def removed(self) -> Set[Hashable]:
        return self._self_removed

    @property
    def on_changed(self) -> Callable:
        def call_all():
            for callback in self._self_on_changed:
                callback()
        return call_all

    def reset_tracking(self):
        self.changed.clear()
        self.added.clear()
        self.removed.clear()
        for item in self:
            if isinstance(item, TrackableProtocol):
                item.reset_tracking()

    def on_changed_item(self, i: int):
        self.changed.add(i)
        self.on_changed()

    def _get_tracked(self, value: Any):
        # Return primitive types unchanged - they don't require nested tracking
        if value is None or isinstance(value, primitives):
            return value

        if isinstance(value, TrackableProtocol):
            logger.debug("Value already tracked, adding to its callback")
            def on_changed():
                self.on_changed_item(hash(value))
            value._self_on_changed.append(on_changed)
            return value

        on_changed = lambda: self.on_changed_item(hash(value))
        return tracked(value, on_changed)

    def add(self, value):
        self.added.add(hash(value))
        self.__wrapped__.add(self._get_tracked(value))
        self.on_changed()

    def discard(self, value):
        self.removed.add(value)
        self.__wrapped__.discard(value)
        self.on_changed()

    def silent_add(self, value):
        self.__wrapped__.add(self._get_tracked(value))

    def silent_discard(self, value):
        self.__wrapped__.discard(value)

    def silent_remove(self, value):
        self.__wrapped__.remove(value)

    def __deepcopy__(self, *args, **kwargs):
        self.__wrapped__ = copy.deepcopy(self.__wrapped__, *args, **kwargs)


class TrackableDefaultDict(defaultdict):
    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)
        self[key] = self.default_factory(key)
        return self[key]


class TrackedDict(ObjectProxy, MutableMapping, TrackableProtocol):
    """
    Tracks add, remove and changes to values in a dictionary
    Including dictionaries of tracked items, tracked lists or nested tracked dicts
    """
    def __init__(self, d: dict|defaultdict|Generator = None, on_changed: Callable = lambda: None):
        if d is None:
            d = dict()
        elif hasattr(d, '__iter__') and not isinstance(d, (dict, defaultdict, str, bytes)):
            # Handle generators and other iterables from asdict()
            try:
                # Convert generator of (key, value) pairs to dict
                d = dict(d)
            except (ValueError, TypeError) as e:
                print(f"Failed to convert {type(d)} to dict: {e}")
                # If conversion fails, create empty dict
                d = dict()

        if isinstance(d, defaultdict):
            df = d.default_factory
            def tracked_factory(k):
                return self._get_tracked(k, df())
            d = TrackableDefaultDict(tracked_factory, d)

        super().__init__(d)

        self._self_changed: Set[Hashable] = set()  # record the key of any changed value
        self._self_added: Set[Hashable] = set()
        self._self_removed = dict()

        self._self_on_changed = [on_changed]
        for key, value in d.items():
            self.__wrapped__.__setitem__(key, self._get_tracked(key, value))

    @property
    def changed(self) -> Set[Hashable]:
        return self._self_changed

    def collect_added_models(self, added_models: List):
        for key in self.added | self.changed:
            value = self[key]
            if isinstance(value, TrackedObject):
                if key in self.added:
                    added_models.append(value)
                if hasattr(value, 'added_models'):
                    added_models.extend(value.added_models)
            elif hasattr(value, 'collect_added_models'):
                value.collect_added_models(added_models)

    def collect_removed_models(self, removed_models: List):
        for key in self.removed.keys() | self.changed:
            value = self[key]
            if isinstance(value, TrackedObject):
                if key in self.removed:
                    removed_models.append(value)
            elif hasattr(value, 'collect_removed_models'):
                value.collect_removed_models(removed_models)

    def collect_changed_models(self, changed_models: List):
        for key in self.changed:
            value = self[key]
            if isinstance(value, TrackedObject):
                changed_models.append(value)
            elif hasattr(value, 'collect_changed_models'):
                value.collect_changed_models(changed_models)

    @property
    def added(self) -> Set[Hashable]:
        return self._self_added

    @property
    def removed(self) -> dict:
        return self._self_removed

    @property
    def on_changed(self) -> Callable:
        def call_all():
            for callback in self._self_on_changed:
                callback()
        return call_all

    def reset_tracking(self):
        self.changed.clear()
        self.added.clear()
        self.removed.clear()
        for value in self.values():
            if isinstance(value, TrackableProtocol):
                value.reset_tracking()

    def on_changed_value(self, key: Hashable):
        self.changed.add(key)
        self.on_changed()

    def _get_tracked(self, key: Hashable, value: Any):
        # Return primitive types unchanged - they don't require nested tracking
        if value is None or isinstance(value, primitives):
            return value

        if isinstance(value, TrackableProtocol):
            logger.debug("Value already tracked, adding to its callback")
            def on_changed():
                self.on_changed_value(key)
            value._self_on_changed.append(on_changed)
            return value

        on_changed = lambda: self.on_changed_value(key)
        return tracked(value, on_changed)

    def __setitem__(self, key, value) -> None:
        if key not in self.__wrapped__:
            self.added.add(key)
        else:
            self.changed.add(key)

        self.__wrapped__.__setitem__(key, self._get_tracked(key, value))
        self.on_changed()

    def __delitem__(self, key) -> None:
        self.removed[key] = self[key]
        self.__wrapped__.__delitem__(key)
        self.on_changed()

    def silent_set(self, key, value) -> None: # set an item without recording the change
        self.__wrapped__.__setitem__(key, self._get_tracked(key, value))

    def silent_remove(self, key) -> None: # remove an item without recording the change
        self.__wrapped__.__delitem__(key)

    def replace_with_stored(self, old_id, new_model):
        if old_id in self._self_changed:
            self._self_changed.remove(old_id)
            self._self_changed.add(new_model.id)
        if old_id in self._self_added:
            self._self_added.remove(old_id)
            self._self_added.add(new_model.id)
        if old_id in self._self_removed:
            self._self_removed.pop(old_id)
            self._self_removed[new_model.id] = new_model

        self.silent_remove(old_id)
        self.silent_set(new_model.id, new_model)

    def __deepcopy__(self, *args, **kwargs):
        self.__wrapped__ = copy.deepcopy(self.__wrapped__, *args, **kwargs)


class TrackedGraph(ObjectProxy, nx.DiGraph, TrackableProtocol):
    """
    Tracks changes to a nx.DiGraph
    """

    def __init__(self, g: nx.DiGraph, on_changed: Callable  = lambda: None):
        if g is None:
            g = nx.DiGraph()
        super().__init__(g)

        self._self_on_changed = [on_changed]
        self._self_changed: Set[str] = set()  # node or adj, case depending

        # https://networkx.org/documentation/stable/reference/classes/digraph.html
        # we want to wrap after init and provide a callback so we can't rely on overriding the default factories
        # so far the below works though
        self.__wrapped__._node = TrackedDict(g._node, on_changed=lambda: self.on_changed_attr('_node'))
        self.__wrapped__._adj = TrackedDict(g._adj, on_changed=lambda: self.on_changed_attr('_adj'))

    @property
    def added_nodes(self) -> Set[int]:
        return self.__wrapped__._node.added.copy()

    @property
    def removed_nodes(self) -> dict[int, Any]:
        return self.__wrapped__._node.removed.copy()

    @property
    def changed_nodes(self) -> Set[int]:
        return self.__wrapped__._node.changed.copy()

    def collect_added_models(self, added_models: List):
        for i in self.added_nodes:
            model = self.nodes[i]['model']
            added_models.append(model)

    def collect_removed_models(self, removed_models: List):
        for value in self.removed_nodes.values():
            model = value['model']
            removed_models.append(model)

    def collect_changed_models(self, changed_models: List):
        for i in self.changed_nodes:
            model = self.nodes[i]['model']
            changed_models.append(model)
        # For write tracking purposes, changes include added/removed incoming edges.
        for source, sink in self.added_edges|self.removed_edges:
            if sink in self.added_nodes|self.removed_nodes.keys():
                continue
            sink_model = self.nodes[sink]['model']
            if sink_model in changed_models:
                continue
            changed_models.append(sink_model)

    def replace_with_stored(self, old_id, new_model):
        # get list of references to old node so can later remove them from tracking
        pred = list(self.__wrapped__.predecessors(old_id))
        nx.relabel_nodes(self.__wrapped__, {old_id: new_model.id}, copy=False)

        self.__wrapped__._adj.changed.discard(old_id)
        for p in pred:
            if old_id in self.__wrapped__._adj[p].added:
                self.__wrapped__._adj[p].added.remove(old_id)
            if old_id in self.__wrapped__._adj[p].removed:
                del self.__wrapped__._adj[p].removed[old_id]

        self.__wrapped__._node.added.discard(old_id)
        self.__wrapped__._node.changed.discard(old_id)
        if old_id in self.__wrapped__._node.removed:
            del self.__wrapped__._node.removed[old_id]

        self.__wrapped__.nodes[new_model.id].silent_set('model', new_model)

    @property
    def added_edges(self) -> Set[tuple[int, int]]:
        added = set()
        for node_id in self.__wrapped__._adj.changed:
            added.update({(node_id, child_id) for child_id in self.__wrapped__._adj[node_id].added})
        return added

    @property
    def removed_edges(self) -> Set[tuple[int, int]]:
        removed = set()
        for node_id in self.__wrapped__._adj.changed:
            removed.update({(node_id, child_id) for child_id in self.__wrapped__._adj[node_id].removed})
        return removed

    @property
    def _succ(self):
        return self.__wrapped__._succ

    @property
    def _pred(self):
        return self.__wrapped__._pred

    @property
    def _adj(self):
        return self.__wrapped__._adj

    @property
    def _node(self):
        return self.__wrapped__._node

    def __dict__(self):
        return self.__wrapped__.__dict__

    def neighbors(self, n):
        return self.__wrapped__.neighbors(n)

    def successors(self, n):
        return self.__wrapped__.successors(n)

    def number_of_nodes(self):
        return self.__wrapped__.number_of_nodes()

    def add_node(self, node_for_adding, **attr):
        self.__wrapped__.add_node(node_for_adding, **attr)

    def remove_node(self, n):
        self.__wrapped__.remove_node(n)

    def add_edge(self, node_for_adding, edge, **attr):
        self.__wrapped__.add_edge(node_for_adding, edge, **attr)

    def remove_edge(self, u, v):
        self.__wrapped__.remove_edge(u, v)

    @property
    def changed(self) -> Set[str]:
        return self._self_changed

    @property
    def on_changed(self) -> Callable:
        def call_all():
            for callback in self._self_on_changed:
                callback()
        return call_all

    def on_changed_attr(self, s: str):
        self.changed.add(s)
        self.on_changed()

    def reset_tracking(self):
        self.changed.clear()
        self._node.reset_tracking()
        self._adj.reset_tracking()

    def __deepcopy__(self, *args, **kwargs):
        self.__wrapped__ = copy.deepcopy(self.__wrapped__, *args, **kwargs)
