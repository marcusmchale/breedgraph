from typing import Union, List, MutableSequence
from wrapt import ObjectProxy


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
		# "dirty" means inconsistent with database, i.e. changes are yet to be saved
		super(TrackableObject, self).__init__(wrapped)
		self._self_dirty = False

	def __setattr__(self, key, value):
		if all([
			key != '_self_dirty',
			hasattr(self, key) and getattr(self, key) != value
		]):
			self._self_dirty = True
		super(TrackableObject, self).__setattr__(key, value)

	@property
	def dirty(self):
		return self._self_dirty

	def reset_tracking(self):
		self._self_dirty = False


class TrackableSequence(ObjectProxy):
	def __copy__(self):
		return self.__wrapped__.__copy__()

	def __deepcopy__(self, memo):
		return self.__wrapped__.__deepcopy__()

	def __reduce__(self):
		return self.__wrapped__.__reduce__()

	def __reduce_ex__(self, protocol):
		return self.__wrapped__.__reduce_ex__()

	def __init__(self, sequence: Union[List, MutableSequence]):
		super(TrackableSequence, self).__init__(sequence)
		self._self_dirty = False
		self._self_source_len = len(sequence)

	def __setitem__(self, i: int, o) -> None:
		self.__wrapped__.__setitem__(i, o)
		self._self_dirty = True

	def __delitem__(self, i: int) -> None:
		self.__wrapped__.__delitem__(i)
		self._self_dirty = True

	def __add__(self, value):
		self.__wrapped__.__add__(value)
		self._self_dirty = True

	def __iadd__(self, value):
		self.__wrapped__.__iadd__(value)
		self._self_dirty = True

	def insert(self, index: int, o) -> None:
		self.__wrapped__.insert(index, o)
		self._self_dirty = True

	def append(self, o) -> None:
		self.__wrapped__.append(o)

	def remove(self, value):
		self.__wrapped__.remove(value)
		self._self_dirty = True

	@property
	def dirty(self) -> bool:
		return self._self_dirty

	@property
	def source_len(self) -> int:
		return self._self_source_len

	def reset_tracking(self):
		self._self_dirty = False
		self._self_source_len = len(self.__wrapped__)
