import bisect
import threading
from xmlrpc.client import Marshaller


class OrderedUniqueList(list):
    def __init__(self, iterable=None):
        super().__init__()
        self.lock = threading.Lock()
        if iterable is not None:
            super().extend(sorted(iterable))

    def append(self, __object) -> None:
        # lock here to prevent concurrent access
        with self.lock:
            index = bisect.bisect_left(self, __object)
            if index == len(self) or self[index] != __object:
                self.insert(index, __object)

    def remove(self, __value) -> None:
        with self.lock:
            index = bisect.bisect_left(self, __value)
            if index < len(self) and self[index] == __value:
                del self[index]

    def extend(self, __iterable) -> None:
        with self.lock:
            for __object in __iterable:
                index = bisect.bisect_left(self, __object)
                if index == len(self) or self[index] != __object:
                    self.insert(index, __object)

    def __contains__(self, item):
        res = self.find_like(item)
        return res is not None

    def find_like(self, object):
        index = bisect.bisect_left(self, object)
        if -1 < index < len(self) and self[index] == object:
            return self[index]
        return None

    def get_bigger(self, __object) -> "OrderedUniqueList":
        with self.lock:
            index = bisect.bisect_right(self, __object)
            return OrderedUniqueList(self[index:]) if  index < len(self) else OrderedUniqueList([])

    def get_smaller(self, __object) -> "OrderedUniqueList":
        with self.lock:
            index = bisect.bisect_left(self, __object)
            return OrderedUniqueList(self[:index]) if index <= len(self) else OrderedUniqueList([])

    def get_bigger_or_equal(self, __object) -> "OrderedUniqueList":
        with self.lock:
            index = bisect.bisect_left(self, __object)
            return OrderedUniqueList(self[index:]) if index < len(self) else OrderedUniqueList([])

    def get_smaller_or_equal(self, __object) -> "OrderedUniqueList":
        with self.lock:
            index = bisect.bisect_right(self, __object)
            return OrderedUniqueList(self[:index]) if index <= len(self) else OrderedUniqueList([])


    def encode(self, marshaller_w:Marshaller):
         marshaller_w.dump_array(self, marshaller_w.write)

# ----------------------------------------------------------------------------------------------------------------------

if __name__ == '__main__':
    a = OrderedUniqueList([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    print(a)