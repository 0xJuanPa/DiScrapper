import functools
from hashlib import sha1
from typing import Callable


@functools.total_ordering
class IdComparable:
    @staticmethod
    def hasher_fun(st):
        return sha1(st.encode("utf8")).digest()

    @staticmethod  # to export
    def set_hasher_fun(hasher_fun: Callable[[str], bytes]):
        pass

    @staticmethod
    def hasher(st):
        return int.from_bytes(IdComparable.hasher_fun(st), byteorder="big")

    def __hash__(self):
        return hash(self.id)

    def __init__(self, ):
        self.id: int | None = None

    def __gen_cmp(self, other, func):
        if other is None:
            return False
        if isinstance(other, int):
            return func(self.id, other)
        if isinstance(other, str):
            return func(self.id, int(other))
        if hasattr(other, "id") and isinstance(other.id, int):
            return func(self.id, other.id)
        raise "Incompatible Comparison"

    def __gt__(self, other):
        return self.__gen_cmp(other, self.id.__class__.__gt__)

    def __eq__(self, other):
        return self.__gen_cmp(other, self.id.__class__.__eq__)
