# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)


class Array(dict):

    def merge(self, *item_lists):
        copy = self.copy()
        for items in item_lists:
            copy.update(items)
        return copy

    def copy(self):
        dict = Array(self)
        return dict

    def __getstate__(self):
        return self.__dict__.items()

    def __setstate__(self, items):
        for key, val in items:
            self.__dict__[key] = val

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, dict.__repr__(self))

    def __setitem__(self, key, value):
        return super(Array, self).__setitem__(key, value)

    def __getitem__(self, name):
        item = super(Array, self).__getitem__(name)
        return Array(item) if type(item) == dict else item

    def __delitem__(self, name):
        return super(Array, self).__delitem__(name)

    __getattr__ = __getitem__
    __setattr__ = __setitem__
