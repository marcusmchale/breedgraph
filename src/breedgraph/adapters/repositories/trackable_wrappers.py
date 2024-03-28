from abc import ABC, abstractmethod
from typing import Union, Dict, Set, MutableMapping, overload, Iterable
from wrapt import ObjectProxy

from collections.abc import MutableSequence

class Trackable(ObjectProxy):
    def __copy__(self):
        return self.__wrapped__.__copy__()
    def __deepcopy__(self, memo):
        return self.__wrapped__.__deepcopy__()
    def __reduce__(self):
        return self.__wrapped__.__reduce__()
    def __reduce_ex__(self, protocol):
        return self.__wrapped__.__reduce_ex__()
    def __init__(self, wrapped):
        super(Trackable, self).__init__(wrapped)
        self._self_changed = False

    def reset_tracking(self):
        self._self_changed = False

    @property
    def changed(self):
        return self._self_changed


# "changed" means inconsistent with database, i.e. changes are yet to be saved
class TrackedObject(Trackable):
    def __setattr__(self, key, value):
        if all([
            key != '_self_changed',
            hasattr(self, key) and getattr(self, key) != value
        ]):
            self._self_changed = True
        super(TrackedObject, self).__setattr__(key, value)


class TrackedList(MutableSequence, Trackable):

    def __init__(self, d: list = None):
        if d is None:
            d = list()

        super(TrackedList, self).__init__(d)

        for i, item in enumerate(d):
            d[i] = TrackedObject(item)

        self._self_added = set()
        self._self_removed = set()

    @property
    def added(self):
        return self._self_added

    @property
    def removed(self):
        return self._self_removed

    def insert(self, index: int, value):
        tracked_item = TrackedObject(value)
        self._self_added.add(tracked_item)
        self.__wrapped__.insert(index, tracked_item)
        self._self_changed = True

    def remove(self, value):
        self.__wrapped__.remove(value)
        self._self_removed.add(value)
        self._self_changed = True

    def __getitem__(self, index: int):
        return self.__wrapped__.__getitem__(index)

    def __setitem__(self, index: int, value):
        existing_value = self.__wrapped__.__getitem__(index)
        new_value = TrackedObject(value)
        if existing_value in self._self_added:
            self._self_added.remove(existing_value)
            self._self_added.add(new_value)
        if existing_value in self._self_removed:
            self._self_removed.remove(existing_value)
            self._self_removed.add(new_value)
        self.__wrapped__.__setitem__(index, new_value)
        self._self_changed = True

    def __delitem__(self, index: int):
        item = self.__wrapped__.__getitem__[index]
        if item in self.added:
            raise ValueError("This item was just added, why try to remove it?")

        self._self_removed.add(item)
        self.__wrapped__.__delitem__(index)
        self._self_changed = True

    def __len__(self):
        return self.__wrapped__.__len__()


## dirty is a dict of changed key/value for selective update
## value of None means key was deleted
## todo if this is used consider refactoring to keep the dirty flag and add a new dict to track changes
#class TrackedMapping(TrackedObject):
#
#    def __init__(self, d: Union[Dict, MutableMapping]):
#        super(TrackedMapping, self).__init__(d)
#        self._self_dirty = dict()
#
#    def __setitem__(self, key, value) -> None:
#        self._self_dirty[key] = value
#        self.__wrapped__.__setitem__(key, value)
#
#    def __delitem__(self, key) -> None:
#        self.__wrapped__.__delitem__(key)
#        self._self_dirty[key] = None
#
#    def reset_tracking(self):
#        self._self_dirty = dict()
#
#
#class TrackedSet(TrackedObject, MutableSet):
#
#    def add(self, value):
#        self._self_added.add(value)
#        self.__wrapped__.add(TrackedObject(value))
#        self._self_dirty = True
#
#    def discard(self, value):
#        self._self_discarded.add(value)
#        self.__wrapped__.discard(value)
#        self._self_dirty = True
#
#    def remove(self, value):
#        self._self_discarded.add(value)
#        self.__wrapped__.remove(value)
#        self._self_dirty = True
#
#    @property
#    def added(self):
#        return self._self_added
#
#    @property
#    def discarded(self):
#        return self._self_discarded
#
#    @discarded.setter
#    def discarded(self, value: "TrackedSet"):
#        self._self_discarded = value
#
#    @added.setter
#    def added(self, value: "TrackedSet"):
#        self._self_added = value
#
#    def __init__(self, d: Union[Set, MutableSet] = None):
#        if d is None:
#            d = set()
#        super(TrackedSet, self).__init__(d)
#        for item in d:
#            d.remove(item)
#            d.add(TrackedObject(item))
#        self._self_added = set()
#        self._self_discarded = set()
#
#    def reset_tracking(self):
#        self._self_added.clear()
#        self._self_discarded.clear()
#        self._self_dirty = False
#        for item in self.__wrapped__:
#            item.reset_tracking()