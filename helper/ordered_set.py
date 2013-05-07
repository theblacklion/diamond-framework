# Ordered Set.
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com> (partly)

## {{{ http://code.activestate.com/recipes/577624/ (r2)
import collections
from itertools import chain

# from diamond.decorators import time


class OrderedSet(collections.MutableSet):

    KEY, PREV, NEXT = range(3)

    def __init__(self, iterable=None):
        self.end = end = []
        end += [None, end, end]  # sentinel node for doubly linked list
        self.map = {}            # key --> [key, prev, next]
        if iterable is not None:
            self |= iterable

    def __len__(self):
        return len(self.map)

    def __contains__(self, key):
        return key in self.map

    def add(self, key):
        if key not in self.map:
            end = self.end
            curr = end[OrderedSet.PREV]
            curr[OrderedSet.NEXT] = end[OrderedSet.PREV] = self.map[key] = [key, curr, end]

    def copy(self):
        return OrderedSet(self)

    def discard(self, key):
        if key in self.map:
            key, prev, next = self.map.pop(key)
            prev[OrderedSet.NEXT] = next
            next[OrderedSet.PREV] = prev

    def __iter__(self):
        KEY = OrderedSet.KEY
        NEXT = OrderedSet.NEXT
        end = self.end
        curr = end[NEXT]
        while curr is not end:
            yield curr[KEY]
            curr = curr[NEXT]

    def __reversed__(self):
        KEY = OrderedSet.KEY
        PREV = OrderedSet.PREV
        end = self.end
        curr = end[PREV]
        while curr is not end:
            yield curr[KEY]
            curr = curr[PREV]

    def pop(self, last=True):
        if not self:
            raise KeyError('set is empty')
        # key = next(reversed(self)) if last else next(iter(self))
        if last:
            key = next(reversed(self))
        else:
            key = next(iter(self))
        self.discard(key)
        return key

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, list(self))

    def __eq__(self, other):
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return set(self) == set(other)

    def __del__(self):
        self.clear()  # remove circular references

    # @time
    def union(self, *iterables):
        oset = OrderedSet(self)
        # for iterable in iterables:
        #     oset |= iterable
        # [oset.__or__(iterable) for iterable in iterables]
        oset = oset | chain(*iterables)
        return oset

    def update(self, iterable):
        self |= iterable

    def index(self, value):
        index = 0
        for item in self:
            if item is value:
                return index
            index += 1

    # @time
    def __getitem__(self, index):
        '''
        Returns an item of the ordered set.
        Please keep in mind that this can be slow due to the fact that we have
        no index and have to skim thru all items of the doubly linked list.
        If you do this multiple times in a row you might want to create a list
        from this and continue to work with it instead.
        '''
        if abs(index) >= len(self.map):
            raise IndexError('set index out of range')
        if index < 0:
            index = len(self.map) + index
        iterable = iter(self)
        curr = next(iterable)
        for count in xrange(0, index):
            curr = next(iterable)
        return curr

    # @time
    def __getslice__(self, start, stop):
        '''
        Returns an iterable slice of the ordered set.
        Please keep in mind that this can be slow due to the fact that we have
        no index and have to skim thru all items of the doubly linked list.
        If you do this multiple times in a row you might want to create a list
        from this and continue to work with it instead.
        '''
        results = []
        iterable = iter(self)
        try:
            for count in xrange(0, stop):
                curr = next(iterable)
                if count < start:
                    continue
                results.append(curr)
        except StopIteration:
            pass
        return results

    def __delitem__(self, index):
        item = self[index]
        self.remove(item)

    def __delslice__(self, start, stop):
        remove = self.remove
        [remove(item) for item in self.__getslice__(start, stop)]


if __name__ == '__main__':
    print '1', OrderedSet('abracadaba')
    print '2', OrderedSet('simsalabim')
    x = OrderedSet('abracadaba')
    # doesn't raise "Exception TypeError: TypeError('list indices must be integers, not NoneType',) in ignored"
    print '3', OrderedSet('abracadaba').union(OrderedSet('simsalabim'))
    print '4', OrderedSet('abracadaba') | OrderedSet('simsalabim')
    print '5', OrderedSet('abracadaba'), list(OrderedSet('abracadaba')[2:]), list('abrcd'[2:])
    print '6', OrderedSet('abracadaba'), list(OrderedSet('abracadaba')[:2]), list('abrcd'[:2])
    print '7', OrderedSet('abracadaba'), list(OrderedSet('abracadaba')[2:2]), list('abrcd'[2:2])
    print '8', OrderedSet('abracadaba'), list(OrderedSet('abracadaba')[0:0]), list('abrcd'[0:0])
    print '9', OrderedSet('abracadaba'), list(OrderedSet('abracadaba')[0:1]), list('abrcd'[0:1])
    print '10', OrderedSet('abracadaba'), list(OrderedSet('abracadaba')[-2:]), list('abrcd'[-2:])
    print '11', OrderedSet('abracadaba'), list(OrderedSet('abracadaba')[-1]), list('abrcd'[-1])
    print '12', OrderedSet('abracadaba'), list(OrderedSet('abracadaba')[-4]), list('abrcd'[-4])
    o = OrderedSet('abracadaba')
    del o[3]
    print '13', o
    o = OrderedSet('abracadaba')
    del o[1:3]
    print '14', o
## end of http://code.activestate.com/recipes/577624/ }}}
