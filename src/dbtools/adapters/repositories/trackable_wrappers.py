from typing import Union, Dict, Set, MutableMapping, MutableSet
from wrapt import ObjectProxy


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
        self.dirty = False

    def reset_tracking(self):
        self.dirty = False


# "dirty" means inconsistent with database, i.e. changes are yet to be saved
class TrackableObject(Trackable):

    def __setattr__(self, key, value):
        if all([
            key != 'dirty',
            hasattr(self, key) and getattr(self, key) != value
        ]):
            self.dirty = True
        super(TrackableObject, self).__setattr__(key, value)


# dirty is a dict of changed key/value for selective update
# value of None means key was deleted
class TrackableMapping(TrackableObject):

    def __init__(self, d: Union[Dict, MutableMapping]):
        super(TrackableMapping, self).__init__(d)
        self.dirty = dict()

    def __setitem__(self, key, value) -> None:
        self.dirty[key] = value
        self.__wrapped__.__setitem__(key, value)

    def __delitem__(self, key) -> None:
        self.__wrapped__.__delitem__(key)
        self.dirty[key] = None

    def reset_tracking(self):
        self.dirty = dict()
