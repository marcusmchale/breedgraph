"""
I considered the adapter and descriptor patterns during design of these wrappers.
see https://docs.python.org/3/howto/descriptor.html#descriptorhowto
"""

from pydantic import BaseModel

from typing import List, Set, Callable, Hashable, Any
from wrapt import ObjectProxy

from collections.abc import MutableSequence, MutableSet, MutableMapping


class Tracked(ObjectProxy):
    """
    Tracks add, remove and changes to a Pydantic BaseModel
    Including sets/lists/dicts of tracked items
    """

    def __init__(self, wrapped: BaseModel, on_changed: Callable  = lambda: None):
        super().__init__(wrapped)
        self._self_changed: Set[str] = set()  # record the name of any changed attribute
        self._self_on_changed = on_changed

        for attr, field in wrapped.model_fields.items():
            if field.frozen:
                continue  # no tracking changes to frozen fields,
                # note that frozen fields can still be mutated, e.g. list can be appended to
            elif attr == 'events':
                continue  # also don't want to track collected events, they are just to be consumed
            self.__wrapped__.__setattr__(attr, self._get_tracked(attr))

    def __setattr__(self, key, value):
        if all([
            key != '_self_changed',
            hasattr(self, key) and getattr(self, key) != value
        ]):
            self._self_changed.add(key)
            if self._self_on_changed:
                self._self_on_changed()

        self.__wrapped__.__setattr__(key, value)

    def _get_tracked(self, attr):
        value = getattr(self.__wrapped__, attr)
        on_changed = lambda: self.on_changed_attr(attr)
        if isinstance(value, BaseModel):
            value = Tracked(value, on_changed=on_changed)
        elif isinstance(value, list):
            value = TrackedList(value, on_changed=on_changed)
        elif isinstance(value, set):
            value = TrackedSet(value, on_changed=on_changed)
        elif isinstance(value, dict):
            value = TrackedDict(value, on_changed=on_changed)
        return value

    @property
    def changed(self) -> Set[str]:
        return self._self_changed

    @property
    def on_changed(self) -> Callable:
        return self._self_on_changed

    def on_changed_attr(self, attr: str):
        self.changed.add(attr)
        self.on_changed()

    def reset_tracking(self):
        self.changed.clear()
        for attr in self.__wrapped__.model_fields.keys():
            value = getattr(self.__wrapped__, attr)
            if isinstance(value, (Tracked, TrackedList, TrackedSet, TrackedDict)):
                value.reset_tracking()


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

        self._self_on_changed = on_changed

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
        return self._self_on_changed

    def reset_tracking(self):
        self.changed.clear()
        self.added.clear()
        self.removed.clear()
        for item in self:
            if isinstance(item, (Tracked, TrackedList, TrackedSet, TrackedDict)):
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
        if isinstance(value, BaseModel):
            value = Tracked(value, on_changed=lambda: self.on_changed_item(i))
        elif isinstance(value, list):
            value = TrackedList(value, on_changed=lambda: self.on_changed_item(i))
        elif isinstance(value, set):
            value = TrackedSet(value, on_changed=lambda: self.on_changed_item(i))
        elif isinstance(value, dict):
            value = TrackedDict(value, on_changed=lambda: self.on_changed_item(i))
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

        self._self_on_changed = on_changed

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
        return self._self_on_changed

    def reset_tracking(self):
        self.changed.clear()
        self.added.clear()
        self.removed.clear()
        for item in self:
            if isinstance(item, (Tracked, TrackedList, TrackedSet, TrackedDict)):
                item.reset_tracking()

    def on_changed_item(self, i: int):
        self.changed.add(i)
        self.on_changed()

    def _get_tracked(self, value: Any):
        if isinstance(value, BaseModel):
            value = Tracked(value, on_changed=lambda: self.on_changed_item(hash(value)))
        elif isinstance(value, list):
            value = TrackedList(value, on_changed=lambda: self.on_changed_item(hash(value)))
        elif isinstance(value, set):
            value = TrackedSet(value, on_changed=lambda: self.on_changed_item(hash(value)))
        elif isinstance(value, dict):
            value = TrackedDict(value, on_changed=lambda: self.on_changed_item(hash(value)))
        return value

    def add(self, value):
        self.added.add(hash(value))

        self.__wrapped__.add(self._get_tracked(value))
        self.on_changed()

    def discard(self, value):
        self.removed.add(hash(value))

        self.__wrapped__.discard(value)
        self.on_changed()


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

        self._self_on_changed = on_changed
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
        return self._self_on_changed

    def reset_tracking(self):
        self.changed.clear()
        self.added.clear()
        self.removed.clear()
        for value in self.values():
            if isinstance(value, (Tracked, TrackedList, TrackedSet, TrackedDict)):
                value.reset_tracking()

    def on_changed_value(self, key: Hashable):
        self.changed.add(key)
        self.on_changed()

    def _get_tracked(self, key: Hashable, value: Any):
        if isinstance(value, BaseModel):
            value = Tracked(value, on_changed=lambda: self.on_changed_value(key))
        elif isinstance(value, list):
            value = TrackedList(value, on_changed=lambda: self.on_changed_value(key))
        elif isinstance(value, set):
            value = TrackedSet(value, on_changed=lambda: self.on_changed_value(key))
        elif isinstance(value, dict):
            value = TrackedDict(value, on_changed=lambda: self.on_changed_value(key))
        return value

    def __setitem__(self, key, value) -> None:
        if key not in self.__wrapped__:
            self.added.add(key)
        else:
            self.changed.add(key)

        self.__wrapped__.__setitem__(key, self._get_tracked(key, value))
        self.on_changed()

    def __delitem__(self, key) -> None:
        if key in self.added or key in self.changed:
            raise ValueError("Key can't be removed until changes have been committed")

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
