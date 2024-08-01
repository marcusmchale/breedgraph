"""
I considered the adapter and descriptor patterns during design of these wrappers.
see https://docs.python.org/3/howto/descriptor.html#descriptorhowto
"""
import logging
import networkx as nx

from functools import wraps
from pydantic import BaseModel, TypeAdapter
from pydantic_core import core_schema, SchemaSerializer

from typing import List, Set, Callable, Hashable, Any

from wrapt import ObjectProxy

from collections.abc import MutableSequence, MutableSet, MutableMapping

logger = logging.getLogger(__name__)

class Tracked(ObjectProxy):
    """
    Tracks add, remove and changes to a Pydantic BaseModel
    Including sets/lists/dicts of tracked items
    """

    def __init__(self, wrapped: BaseModel, on_changed: Callable  = lambda: None):
        super().__init__(wrapped)
        self._self_changed: Set[str] = set()  # record the name of any changed attribute
        self._self_on_changed = [on_changed]

        # need to disable validate assignment to prevent coercion of tracked types back to their base type:
        validate_assignment = wrapped.model_config.get('validate_assignment', None)
        if validate_assignment:
            wrapped.model_config['validate_assignment'] = False

        for attr, field in wrapped.model_fields.items():
            if field.frozen:
                continue  # no tracking changes to frozen fields,
                # note that frozen fields can still be mutated, e.g. list can be appended to
            elif attr == 'events':
                continue  # also don't want to track collected events, they are just to be consumed
            self.__wrapped__.__setattr__(attr, self._get_tracked(attr))

        #set it back to the stored value
        if validate_assignment is False:
            wrapped.model_config['validate_assignment'] = validate_assignment

    def __setattr__(self, key, value):
        if all([
            key != '_self_changed',
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

        if isinstance(value, (Tracked,TrackedList,TrackedSet,TrackedDict,TrackedGraph)):
            logger.debug("Value already tracked, appending on_changed callback")
            value._self_on_changed.append(on_changed)
            return value

        if isinstance(value, BaseModel):
            value = Tracked(value, on_changed=on_changed)
        elif isinstance(value, list):
            value = TrackedList(value, on_changed=on_changed)
        elif isinstance(value, set):
            value = TrackedSet(value, on_changed=on_changed)
        elif isinstance(value, dict):
            value = TrackedDict(value, on_changed=on_changed)
        elif isinstance(value, nx.DiGraph):
            value = TrackedGraph(value, on_changed=on_changed)
        return value

    @property
    def changed(self) -> Set[str]:
        return self._self_changed

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
        for attr in self.__wrapped__.model_fields.keys():
            value = getattr(self.__wrapped__, attr)
            if isinstance(value, (Tracked, TrackedList, TrackedSet, TrackedDict, TrackedGraph)):
                value.reset_tracking()

    def model_dump(self):
        return self.__wrapped__.model_dump()


class TrackedList(ObjectProxy, MutableSequence):
    """
    Tracks add, remove and changes to a list
    """

    def __init__(self, d: List = None, on_changed: Callable = lambda: None):
        if d is None:
            d = list()
        elif not isinstance(d, list):
            d = [d]
        super().__init__(d)

        self._self_changed: Set[int] = set()  # record the index of any changed element
        self._self_added: Set[int] = set()
        self._self_removed = list()

        self._self_on_changed = [on_changed]

        for i, value in enumerate(self):
            self.__wrapped__.__setitem__(i, self._get_tracked(i, value))


    @property
    def changed(self) -> Set[int]:
        return self._self_changed

    @property
    def added(self):
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
            if isinstance(item, (Tracked, TrackedList, TrackedSet, TrackedDict, TrackedGraph)):
                item.reset_tracking()

    def on_changed_item(self, i: int):
        self.changed.add(i)
        self.on_changed()

    def _shift_indices(self, indices: set, threshold_index: int, increment: True):
        for j in indices.copy():
            if j >= threshold_index:
                indices.remove(j)
                if increment:
                    indices.add(j + 1)
                else:
                    indices.add(j - 1)

    def _get_tracked(self, i:int, value: Any):
        if isinstance(value, (Tracked,TrackedList,TrackedSet,TrackedDict,TrackedGraph)):
            logger.debug("Value already tracked, adding to its callback")
            def on_changed():
                self.on_changed_item(i)

            value._self_on_changed.append(on_changed)
            return value

        if isinstance(value, BaseModel):
            value = Tracked(value, on_changed=lambda: self.on_changed_item(i))
        elif isinstance(value, list):
            value = TrackedList(value, on_changed=lambda: self.on_changed_item(i))
        elif isinstance(value, set):
            value = TrackedSet(value, on_changed=lambda: self.on_changed_item(i))
        elif isinstance(value, dict):
            value = TrackedDict(value, on_changed=lambda: self.on_changed_item(i))
        elif isinstance(value, nx.DiGraph):
            value = TrackedGraph(value, on_changed=lambda: self._on_changed_item(i))
        return value

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
        if i in self.added or self.changed:
            raise ValueError("This item can't be removed until changes have been committed")

        self._shift_indices(self.added, i + 1, False)
        self._shift_indices(self.changed, i + 1, False)

        value = self.__wrapped__.__getitem__(i)
        self.removed.append(value)

        self.__wrapped__.__delitem__(i)
        self.on_changed()

    def silent_remove(self, value):
        i = self.__wrapped__.index(value)
        self.__wrapped__.delitem(i)

    def silent_append(self, value):
        i = self.__wrapped__.index(value)
        self.__wrapped__.append(i)

    #def __len__(self):
    #    return self.__wrapped__.__len__()
    #
    #def __getitem__(self, i: int):
    #    return self.__wrapped__.__getitem__(i)
    #
    #def __iter__(self):
    #    return self.__wrapped__.__iter__()

    # the below are to support model dump, see patch at bottom of this file and described here:
    # https://github.com/pydantic/pydantic/issues/7779
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        _ = source_type
        schema = core_schema.no_info_after_validator_function(
            cls._validate,
            handler(list),
            serialization=core_schema.plain_serializer_function_ser_schema(
                list,
                info_arg=False,
                return_schema=core_schema.list_schema(),
            ),
        )
        cls.__pydantic_serializer__ = SchemaSerializer(schema)  # <-- this is necessary for pydantic-core to serialize
        return schema

    @classmethod
    def _validate(cls, value: "TrackedList"):
        return cls(value)


class TrackedSet(ObjectProxy, MutableSet):
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
            if isinstance(item, (Tracked, TrackedList, TrackedSet, TrackedDict, TrackedGraph)):
                item.reset_tracking()

    def on_changed_item(self, i: int):
        self.changed.add(i)
        self.on_changed()

    def _get_tracked(self, value: Any):
        if isinstance(value, (Tracked, TrackedList, TrackedSet, TrackedDict, TrackedGraph)):
            logger.debug("Value already tracked, adding to its callback")

            def on_changed():
                self.on_changed_item(hash(value))

            value._self_on_changed.append(on_changed)
            return value


        if isinstance(value, BaseModel):
            value = Tracked(value, on_changed=lambda: self.on_changed_item(hash(value)))
        elif isinstance(value, list):
            value = TrackedList(value, on_changed=lambda: self.on_changed_item(hash(value)))
        elif isinstance(value, set):
            value = TrackedSet(value, on_changed=lambda: self.on_changed_item(hash(value)))
        elif isinstance(value, dict):
            value = TrackedDict(value, on_changed=lambda: self.on_changed_item(hash(value)))
        elif isinstance(value, nx.DiGraph):
            value = TrackedGraph(value, on_changed=lambda: self._on_changed_item(hash(value)))
        return value

    def add(self, value):
        self.added.add(hash(value))
        self.__wrapped__.add(self._get_tracked(value))
        self.on_changed()

    def discard(self, value):
        self.removed.add(hash(value))
        self.__wrapped__.discard(value)
        self.on_changed()

    def silent_add(self, value):
        self.__wrapped__.add(self._get_tracked(value))

    def silent_discard(self, value):
        self.__wrapped__.discard(value)

    def silent_remove(self, value):
        self.__wrapped__.remove(value)

    # the below are to support model dump, see patch at bottom of this file and described here:
    # https://github.com/pydantic/pydantic/issues/7779
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        _ = source_type
        schema = core_schema.no_info_after_validator_function(
            cls._validate,
            handler(set),
            serialization=core_schema.plain_serializer_function_ser_schema(
                set,
                info_arg=False,
                return_schema=core_schema.set_schema(),
            ),
        )
        cls.__pydantic_serializer__ = SchemaSerializer(schema)  # <-- this is necessary for pydantic-core to serialize
        return schema

    @classmethod
    def _validate(cls, value: "TrackedSet"):
        return cls(value)


class TrackedDict(ObjectProxy, MutableMapping):
    """
    Tracks add, remove and changes to values in a dictionary
    Including dictionaries of tracked items, tracked lists or nested tracked dicts
    """
    def __init__(self, d: dict = None, on_changed: Callable = lambda: None):
        if d is None:
            d = dict()
        super().__init__(d)

        self._self_changed: Set[Hashable] = set()  # record the key of any changed value
        self._self_added: Set[Hashable] = set()
        self._self_removed = dict()

        self._self_on_changed = [on_changed]
        for key, value in self.items():
            self.__wrapped__.__setitem__(key, self._get_tracked(key, value))

    @property
    def changed(self) -> Set[Hashable]:
        return self._self_changed

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
            if isinstance(value, (Tracked, TrackedList, TrackedSet, TrackedDict, TrackedGraph)):
                value.reset_tracking()

    def on_changed_value(self, key: Hashable):
        self.changed.add(key)
        self.on_changed()

    def _get_tracked(self, key: Hashable, value: Any):
        if isinstance(value, (Tracked, TrackedList, TrackedSet, TrackedDict, TrackedGraph)):
            logger.debug("Value already tracked, adding to its callback")

            def on_changed():
                self.on_changed_value(key)

            value._self_on_changed.append(on_changed)
            return value

        if isinstance(value, BaseModel):
            value = Tracked(value, on_changed=lambda: self.on_changed_value(key))
        elif isinstance(value, list):
            value = TrackedList(value, on_changed=lambda: self.on_changed_value(key))
        elif isinstance(value, set):
            value = TrackedSet(value, on_changed=lambda: self.on_changed_value(key))
        elif isinstance(value, dict):
            value = TrackedDict(value, on_changed=lambda: self.on_changed_value(key))
        elif isinstance(value, nx.DiGraph):
            value = TrackedGraph(value, on_changed=lambda: self._on_changed_value(key))
        return value

    def __setitem__(self, key, value) -> None:
        if key not in self.__wrapped__:
            self.added.add(key)
        else:
            self.changed.add(key)

        self.__wrapped__.__setitem__(key, self._get_tracked(key, value))
        self.on_changed()

    def __delitem__(self, key) -> None:
        #if key in self.added or key in self.changed:
        #    raise ValueError("Key can't be removed until changes have been committed")
        self.removed[key] = self[key]
        self.__wrapped__.__delitem__(key)
        self.on_changed()

    def silent_set(self, key, value) -> None: # set an item without recording the change
        self.__wrapped__.__setitem__(key, self._get_tracked(key, value))

    def silent_remove(self, key) -> None: # remove an item without recording the change
        self.__wrapped__.__delitem__(key)

    #def __len__(self):
    #    return self.__wrapped__.__len__()
    #
    #def __getitem__(self, __key):
    #    return self.__wrapped__.__getitem__(__key)
    #
    #def __iter__(self):
    #    return self.__wrapped__.__iter__()

    # the below are to support model dump, see patch at bottom of this file and described here:
    # https://github.com/pydantic/pydantic/issues/7779
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        _ = source_type
        schema = core_schema.no_info_after_validator_function(
            cls._validate,
            handler(dict),
            serialization=core_schema.plain_serializer_function_ser_schema(
                dict,
                info_arg=False,
                return_schema=core_schema.dict_schema(),
            ),
        )
        cls.__pydantic_serializer__ = SchemaSerializer(schema)  # <-- this is necessary for pydantic-core to serialize
        return schema

    @classmethod
    def _validate(cls, value: "TrackedDict"):
        return cls(value)


class TrackedGraph(ObjectProxy, nx.DiGraph):
    """
    Tracks changes to a nx.DiGraph
    """

    def __init__(self, g: nx.DiGraph, on_changed: Callable  = lambda: None):
        if g is None:
            g = nx.DiGraph()
        super().__init__(g)

        #for n in g.nodes:
        #    g.nodes[n]['model'] = Tracked(g.nodes[n]['model'], on_changed=lambda: self.on_changed_model(n))

        self._self_on_changed = [on_changed]
        self._self_changed: Set[str] = set()  # node or adj, case depending

        # https://networkx.org/documentation/stable/reference/classes/digraph.html
        # we want to wrap after init and provide a callback so we can't rely on overriding the default factories
        # so far the below works though
        #self.__wrapped__.graph = TrackedDict(g.graph, on_changed=lambda: self.on_changed_attr('graph'))
        self.__wrapped__._node = TrackedDict(g._node, on_changed=lambda: self.on_changed_attr('_node'))
        self.__wrapped__._adj = TrackedDict(g._adj, on_changed=lambda: self.on_changed_attr('_adj'))
        #self.__wrapped__._pred = TrackedDict(g._pred, on_changed=lambda: self.on_changed_attr('pred'))

    @property
    def added_nodes(self) -> Set[int]:
        return self.__wrapped__._node.added.copy()

    @property
    def removed_nodes(self) -> Set[int]:
        return self.__wrapped__._node.removed.copy()

    @property
    def changed_nodes(self) -> Set[int]:
        return self.__wrapped__._node.changed.copy()

    def replace_with_stored(self, old_id, new_model: BaseModel):
        self.__wrapped__.nodes[old_id]['model'] = new_model
        # remove references to old node in tracking
        pred = list(self.__wrapped__.predecessors(old_id))
        nx.relabel_nodes(self.__wrapped__, {old_id: new_model.id}, copy=False)
        for p in pred:
            self.__wrapped__._adj[p].added.remove(old_id)
            del self.__wrapped__._adj[p].removed[old_id]
        self.__wrapped__._node.added.discard(old_id)
        self.__wrapped__._node.changed.discard(old_id)
        del self.__wrapped__._node.removed[old_id]


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
        #for attr in self.__wrapped__.model_fields.keys():
        #    value = getattr(self.__wrapped__, attr)
        #    if isinstance(value, (Tracked, TrackedList, TrackedSet, TrackedDict, TrackedGraph)):
        #        value.reset_tracking()

# https://github.com/pydantic/pydantic/issues/7779
TypeAdapter(TrackedList)
TypeAdapter(TrackedSet)
TypeAdapter(TrackedDict)
