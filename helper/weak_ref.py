import weakref
import new


class Wrapper(object):

    def __init__(self, obj):
        self.is_method = False
        self.has_instance = False
        if hasattr(obj, '__call__') and hasattr(obj, 'im_self'):
            inst = obj.im_self
            if inst is not None:
                try:
                    obj = obj.im_func, weakref.ref(inst), obj.im_class
                except AttributeError:
                    obj = weakref.ref(obj)
                else:
                    self.is_method = True
                    self.has_instance = True
            else:
                obj = obj.im_func, inst, obj.im_class
                self.is_method = True
        else:
            obj = weakref.ref(obj)
        self.obj = obj

    def __repr__(self):
        res = self.resolve(raise_error=False)
        return '%s containing %s>' % (super(Wrapper, self).__repr__()[:-1], res)

    def resolve(self, raise_error=True):
        if self.is_method:
            inst = self.obj[1]
            if self.has_instance:
                inst = inst()
                if inst is None and raise_error:
                    raise ReferenceError
            return new.instancemethod(self.obj[0], inst, self.obj[2])
        else:
            return self.obj()

    # TODO implement __eq__ and __ne__ methods
