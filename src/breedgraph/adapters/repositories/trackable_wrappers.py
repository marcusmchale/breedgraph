"""
I considered the adapter and descriptor patterns during design of these wrappers.
see https://docs.python.org/3/howto/descriptor.html#descriptorhowto
"""

from pydantic import BaseModel

from typing import List, Set, Callable
from wrapt import ObjectProxy

from collections.abc import MutableSequence

class Tracked(ObjectProxy):

    def __init__(self, wrapped: BaseModel, on_changed: Callable  = None):
        super().__init__(wrapped)
        self._self_changed: Set[str] = set()  # record the name of any changed attribute
        self._self_on_changed = on_changed

        for attr, field in wrapped.model_fields.items():
            if field.frozen:
                continue  # no need to track changes to frozen fields

            value = getattr(wrapped, attr)
            if isinstance(value, BaseModel):
                setattr(self, attr, Tracked(value))
            elif isinstance(value, List):
                list_changed = lambda: self._self_changed.add(attr)
                setattr(self, attr, TrackedList(value, list_changed))

    def __setattr__(self, key, value):
        if all([
            key != '_self_changed',
            hasattr(self, key) and getattr(self, key) != value
        ]):
            self._self_changed.add(key)
            if self._self_on_changed:
                self._self_on_changed()

        super(Tracked, self).__setattr__(key, value)

    @property
    def changed(self) -> Set[str]:
        return self._self_changed

    @property
    def on_changed(self) -> Callable:
        return self._self_on_changed

    def reset_tracking(self):
        self.changed.clear()
        for attr in self.__wrapped__.model_fields.keys():
            value = getattr(self.__wrapped__, attr)
            if isinstance(value, TrackedList):
                value.reset_tracking()


class TrackedList(ObjectProxy, MutableSequence):

    def __init__(self, d: List = None, on_changed: Callable = None):
        if d is None:
            d = list()
        elif not isinstance(d, list):
            d = [d]

        super().__init__(d)
        self._self_changed: Set[int] = set()  # record the name of any changed attribute
        self._self_added: Set[int] = set()

        self._self_removed = list()

        self._self_on_changed = on_changed

        for i, item in enumerate(d):
            if isinstance(item, BaseModel):
                d[i] = Tracked(item, on_changed = lambda: self.on_changed_item(i))

    @property
    def name(self) -> str|None:
        return self._self_name

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
        if self._self_on_changed:
            return self._self_on_changed
        else:
            return lambda: None

    def reset_tracking(self):
        self.added.clear()
        self.removed.clear()
        self.changed.clear()
        for item in self.__wrapped__:
            if isinstance(item, Tracked):
                item.reset_tracking()

    def on_changed_item(self, i: int):
        self.changed.add(i)
        self.on_changed()

    def _shift_indices(self, indices: set, threshold_index: int, increment: True):
        for j in indices:
            if j >= threshold_index:
                self.added.remove(j)
                if increment:
                    self.added.add(j + 1)
                else:
                    self.added.add(j - 1)

    def insert(self, i: int, value):  # insert is also called by append
        self._shift_indices(self.added, i, True)
        self._shift_indices(self.changed, i, True)

        self.added.add(i)
        self.__wrapped__.insert(i, Tracked(value))
        self.on_changed()

    def remove(self, value):
        i = self.__wrapped__.index(value)
        self._shift_indices(self.added, i + 1, False)
        self._shift_indices(self.changed, i + 1, False)

        self.__wrapped__.__delitem__(i)
        self.removed.append(value)
        self.on_changed()

    def __setitem__(self, i: int, value):
        self.__wrapped__.__setitem__(i, Tracked(value))
        self.changed.add(i)
        self.on_changed()

    def __delitem__(self, i: int):
        item = self.__wrapped__.__getitem__[i]
        if item in self.added or self.changed:
            raise ValueError("This item can't be removed until changes have been committed")

        self.removed.append(item)
        self.__wrapped__.__delitem__(i)
        self.on_changed()

    def __len__(self):
        return self.__wrapped__.__len__()

    def __getitem__(self, i: int):
        return self.__wrapped__.__getitem__(i)

    def __iter__(self):
        return self.__wrapped__.__iter__()

## value of None means key was deleted
#class TrackedMapping(MutableMapping, Tracked):
#
#    def __init__(self, d: dict = None):
#        if d is None:
#            d = dict()
#
#        super(TrackedMapping, self).__init__(d)
#
#        for key, value in d.items():
#            d[key] = Tracked(value)
#
#        # record any keys added/removed
#        self._self_added = set()
#        self._self_removed = set()
#
#    @property
#    def added(self):
#        return self._self_added
#
#    @property
#    def removed(self):
#        return self._self_removed
#
#    def __setitem__(self, key, value) -> None:
#        if key not in self.__wrapped__:
#            self.added.add(key)
#        tracked = Tracked(value)
#        tracked.changed = True
#        self.__wrapped__.__setitem__(key, tracked)
#        self.changed = False
#
#    def __delitem__(self, key) -> None:
#        if key in self.added:
#            raise ValueError("This key was just added so it can't be removed")
#
#        self.removed.add(key)
#        self.__wrapped__.__delitem__(key)
#        self.changed = True
#
#    def __len__(self):
#        return self.__wrapped__.__len__()
#
#    def __getitem__(self, __key):
#        return self.__wrapped__.__getitem__(__key)
#
#    def __iter__(self):
#        return self.__wrapped__.__iter__()
#
#    def reset_tracking(self):
#        for item in self.__wrapped__.values():
#            item.changed = False
#        self._self_added.clear()
#        self._self_removed.clear()
#        self._self_changed = False
#