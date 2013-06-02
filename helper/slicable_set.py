# Slicable Set.
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

# from diamond.decorators import time


class SlicableSet(set):

    # @time
    def __getitem__(self, index):
        '''
        Returns an item of the ordered set.
        Please keep in mind that this can be slow due to the fact that we have
        no index and have to skim thru all items of the doubly linked list.
        If you do this multiple times in a row you might want to create a list
        from this and continue to work with it instead.
        '''
        if abs(index) >= len(self):
            raise IndexError('set index out of range')
        if index < 0:
            index = len(self) + index
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
