import sys
import cStringIO
from functools import wraps

from pygame.time import get_ticks


def _get_func_and_arglist(fname, argnames, args_, kwargs_):
    for pos, arg in enumerate(args_):
        if type(arg) in (dict, set, list):
            args_[pos] = '%s(%d items)' % (type(arg).__name__, len(arg))
    for key, val in kwargs_.iteritems():
        if type(val) in (dict, set, list):
            kwargs_[key] = '%s(%d items)' % (type(val).__name__, len(val))
    items = ['%s=%r' % entry for entry in zip(argnames, args_) + kwargs_.items()]
    kwitems = dict([entry for entry in zip(argnames, args_) + kwargs_.items()])
    if 'self' in kwitems:
        func_name = '%s.%s' % (kwitems['self'].__class__.__name__, fname)
    else:
        func_name = fname
    return func_name, items


def dump_args(func):
    '''
    This decorator dumps out the arguments passed to a function before calling it.
    @link http://wiki.python.org/moin/PythonDecoratorLibrary
    '''
    @wraps(func)
    def wrapper(*args,**kwargs):
        argnames = func.func_code.co_varnames[:func.func_code.co_argcount]
        fname = func.func_name
        args_ = list(args)
        kwargs_ = kwargs.copy()
        func_name, items = _get_func_and_arglist(fname, argnames, args_, kwargs_)
        print '%s(%s)' % (func_name, ', '.join(items))
        return func(*args, **kwargs)
    wrapper.__wrapped__ = func
    return wrapper


def time(func):
    '''
    This decorator dumps out the arguments passed to a function before calling it
    and measures it's execution time in msecs.
    @link http://wiki.python.org/moin/PythonDecoratorLibrary
    '''
    @wraps(func)
    def wrapper(*args,**kwargs):
        argnames = func.func_code.co_varnames[:func.func_code.co_argcount]
        fname = func.func_name
        args_ = list(args)
        kwargs_ = kwargs.copy()
        func_name, items = _get_func_and_arglist(fname, argnames, args_, kwargs_)
        print '%s(%s)' % (func_name, ', '.join(items)),

        stdout = sys.stdout
        output = cStringIO.StringIO()
        sys.stdout = output

        start = get_ticks()
        result = func(*args, **kwargs)
        stop = get_ticks()

        contents = output.getvalue()
        sys.stdout = stdout

        print '->', stop - start, 'msecs'

        for line in contents.rstrip().split('\n'):
            print '  %s' % line

        return result
    wrapper.__wrapped__ = func
    return wrapper
