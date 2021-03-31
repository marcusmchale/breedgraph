from typing import Union, Dict, MutableMapping
from wrapt import ObjectProxy


# "dirty" means inconsistent with database, i.e. changes are yet to be saved
class TrackableObject(ObjectProxy):
    def __copy__(self):
        return self.__wrapped__.__copy__()

    def __deepcopy__(self, memo):
        return self.__wrapped__.__deepcopy__()

    def __reduce__(self):
        return self.__wrapped__.__reduce__()

    def __reduce_ex__(self, protocol):
        return self.__wrapped__.__reduce_ex__()

    def __init__(self, wrapped):
        super(TrackableObject, self).__init__(wrapped)
        self.dirty = False

    def __setattr__(self, key, value):
        if all([
            key != 'dirty',
            hasattr(self, key) and getattr(self, key) != value
        ]):
            self.dirty = True
        super(TrackableObject, self).__setattr__(key, value)

    def reset_tracking(self):
        self.dirty = False


# stores additional dicts:
#  - changed for selective update
#  - new for additions
# value of None means key was deleted
class TrackableDict(ObjectProxy):

    def __copy__(self):
        return self.__wrapped__.__copy__()

    def __deepcopy__(self, memo):
        return self.__wrapped__.__deepcopy__()

    def __reduce__(self):
        return self.__wrapped__.__reduce__()

    def __reduce_ex__(self, protocol):
        return self.__wrapped__.__reduce_ex__()

    def __init__(self, d: Union[Dict, MutableMapping]):
        super(TrackableDict, self).__init__(d)
        self.dirty = False
        self.changed = dict()
        self.new = dict()

    def __setitem__(self, key, value) -> None:
        self.dirty = True
        if key in self.__wrapped__ and key not in self.new:
            self.changed[key] = value
        else:
            self.new[key] = value
        self.__wrapped__.__setitem__(key, value)

    def __delitem__(self, key) -> None:
        self.__wrapped__.__delitem__(key)
        self.dirty = True
        if key in self.new:
            del self.new[key]
        else:
            self.changed[key] = None

    def reset_tracking(self):
        self.dirty = False
        self.changed = dict()
        self.new = dict()


#  class TrackableSequence(ObjectProxy):
#      def __copy__(self):
#          return self.__wrapped__.__copy__()
#
#      def __deepcopy__(self, memo):
#          return self.__wrapped__.__deepcopy__()
#
#      def __reduce__(self):
#          return self.__wrapped__.__reduce__()
#
#      def __reduce_ex__(self, protocol):
#          return self.__wrapped__.__reduce_ex__()
#
#      def __init__(self, sequence: Union[List, MutableSequence]):
#          super(TrackableSequence, self).__init__(sequence)
#          self._self_dirty = False
#          self._self_source_len = len(sequence)
#
#      def __setitem__(self, i: int, o) -> None:
#          self.__wrapped__.__setitem__(i, o)
#          self._self_dirty = True
#
#      def __delitem__(self, i: int) -> None:
#          self.__wrapped__.__delitem__(i)
#          self._self_dirty = True
#
#      def __add__(self, value):
#          self.__wrapped__.__add__(value)
#          self._self_dirty = True
#
#      def __iadd__(self, value):
#          self.__wrapped__.__iadd__(value)
#          self._self_dirty = True
#
#      def insert(self, index: int, o) -> None:
#          self.__wrapped__.insert(index, o)
#          self._self_dirty = True
#
#      def append(self, o) -> None:
#          self.__wrapped__.append(o)
#
#      def remove(self, value):
#          self.__wrapped__.remove(value)
#          self._self_dirty = True
#
#      @property
#      def dirty(self) -> bool:
#          return self._self_dirty
#
#      @property
#      def source_len(self) -> int:
#          return self._self_source_len
#
#      def reset_tracking(self):
#          self._self_dirty = False
#          self._self_source_len = len(self.__wrapped__)
