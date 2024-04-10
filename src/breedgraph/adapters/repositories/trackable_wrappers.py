from abc import ABC, abstractmethod
from typing import Union, Dict, Set, MutableMapping, overload, Iterable, Callable
from wrapt import ObjectProxy

from collections.abc import MutableSequence

# considered the adapter pattern and descriptor pattern during design of these wrappers
#   - https://docs.python.org/3/howto/descriptor.html#descriptorhowto


class Tracked(ObjectProxy):

    def __init__(self, wrapped, on_changed: Callable  = None):
        super(Tracked, self).__init__(wrapped)
        self._self_changed = False
        self._self_on_changed = on_changed

    def __setattr__(self, key, value):
        if all([
            key != '_self_changed',
            hasattr(self, key) and getattr(self, key) != value
        ]):
            self._self_changed = True
            if self._self_on_changed:
                self._self_on_changed()

        super(Tracked, self).__setattr__(key, value)

    @property
    def changed(self) -> bool:
        return self._self_changed

    @changed.setter
    def changed(self, value: bool):
        self._self_changed = value

    @property
    def on_changed(self) -> Callable:
        return self._self_on_changed

    @on_changed.setter
    def on_changed(self, callback: Callable):
        self._self_on_changed = callback

    def reset_tracking(self):
        self.changed = False

class TrackedList(MutableSequence, Tracked):

    def __init__(self, d: list = None, on_changed = None):
        if d is None:
            d = list()

        super(TrackedList, self).__init__(d, on_changed)

        for i, item in enumerate(d):
            d[i] = Tracked(item, self.on_changed_item)

        self._self_added = list()
        self._self_removed = list()

    def on_changed_item(self):
        self.changed = True

    @property
    def added(self):
        return self._self_added

    @property
    def removed(self):
        return self._self_removed

    def insert(self, index: int, value):
        tracked_item = Tracked(value)
        self.added.append(tracked_item)
        self.__wrapped__.insert(index, tracked_item)
        self.changed = True

    def remove(self, value):
        self.__wrapped__.remove(value)
        self.removed.append(value)
        self.changed = True

    def __setitem__(self, index: int, value):
        existing_value = self.__wrapped__.__getitem__(index)
        new_value = Tracked(value)
        if existing_value in self._self_added:
            self.added.remove(existing_value)
            self.added.append(new_value)
        if existing_value in self._self_removed:
            self.removed.remove(existing_value)
            self.removed.append(new_value)
        self.__wrapped__.__setitem__(index, new_value)
        self.changed = True

    def __delitem__(self, index: int):
        item = self.__wrapped__.__getitem__[index]
        if item in self.added:
            raise ValueError("This item was just added so it can't be removed")

        self.removed.append(item)
        self.__wrapped__.__delitem__(index)
        self.changed = True

    def __len__(self):
        return self.__wrapped__.__len__()

    def __getitem__(self, index: int):
        return self.__wrapped__.__getitem__(index)

    def __iter__(self):
        return self.__wrapped__.__iter__()

    def reset_tracking(self):
        for item in self.__wrapped__:
            item.changed = False
        self.added.clear()
        self.removed.clear()
        self.changed = False

from pydantic import BaseModel

class Test(BaseModel):
    name: str


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