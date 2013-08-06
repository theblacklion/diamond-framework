# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

# TODO make use of http://docs.python.org/library/itertools.html
from inspect import getargspec
from diamond.helper.weak_ref import Wrapper

# from diamond.decorators import time, dump_args


listeners = {}

basic_rules = dict(
    instance__is=lambda context, value: context is not value,
    instance__is_not=lambda context, value: context is value,
    class__is=lambda context, value: not isinstance(context, value),
)

context_rules = {
    'eq': lambda context_value, value: context_value != value,
    'neq': lambda context_value, value: context_value == value,
    'contains': lambda context_value, value: value not in context_value,
    'gt': lambda context_value, value: context_value <= value,
    'gte': lambda context_value, value: context_value < value,
    'lt': lambda context_value, value: context_value >= value,
    'lte': lambda context_value, value: context_value > value,
    'is': lambda context_value, value: context_value is not value,
    'is_not': lambda context_value, value: context_value is value,
    'in': lambda context_value, value: context_value not in value,
    'returns': lambda context_value, value: context_value() != value,
    'amp': lambda context_value, value: not (context_value & value),
}

proxy_rules = set([
    'instance__is',
    'instance__is_not',
    'class__is',
    'is',
    'is_not',
])

proxy_context_rules = set([
    '__contains',
    '__is',
    '__is_not',
])


class Listener(object):

    def __init__(self, func, event_name, filters):
        self.func = func
        self.event_name = event_name
        self.filters = filters

    def __repr__(self):
        return 'Listener(%s, %s, %s)' % (self.func, self.event_name, self.filters)


# @time
def clear_listeners():
    # print 'event.clear_listeners()'
    listeners.clear()


def get_listeners(hide_empty_lists=True):
    if hide_empty_lists:
        results = {}
        for key, val in listeners.iteritems():
            if val:
                results[key] = val
        return results
    else:
        return listeners.copy()


# @time
def add_listener(func, event_name, **filters):
    # print 'event.add_listener(func=%s, event_name=%s, filters=%s)' % (func, event_name, filters)
    func = Wrapper(func)
    if filters:
        # print 'event.add_listener(func=%s, event_name=%s, filters=%s)' % (func, event_name, filters)
        for key, val in filters.iteritems():
            if key in proxy_rules:
                try:
                    filters[key] = Wrapper(val)
                except TypeError:
                    pass
                continue
            for rule in proxy_context_rules:
                if key.endswith(rule):
                    try:
                        filters[key] = Wrapper(val)
                    except TypeError:
                        pass
                    break
    handler = Listener(func, event_name, filters)
    try:
        listeners[event_name] |= set([handler])
    except KeyError:
        listeners[event_name] = set([handler])
    return Wrapper(handler)


# @dump_args
def remove_listener(candidate):
    # print 'Remove listener:', candidate
    try:
        listener = candidate.resolve()
    except ReferenceError:
        # Try to find dead candidate and remove it.
        for key in listeners:
            try:
                listeners[key].remove(candidate)
                break
            except ValueError:
                pass
    else:
        if listener is not None:
            listeners[listener.event_name].remove(listener)


# @dump_args
def remove_listeners(candidates):
    [remove_listener(listener) for listener in candidates]


def _parse(context, operator):
    try:
        var, operator = operator.rsplit('__', 1)
    except ValueError:
        var, operator = '', operator
    # print 'context parts =', var, operator, context
    # The following loop supports deep paths into context.
    if '__' in var:
        while 1:
            try:
                var, next = var.split('__', 1)
            except ValueError:
                next = None
            if isinstance(context, dict):
                context = context.get(var)
            elif isinstance(context, list):
                context = context[int(var)]
            else:
                context = getattr(context, var)
            if next is not None:
                var = next
            else:
                break
    elif len(var):
        if isinstance(context, dict):
            context = context.get(var)
        else:
            context = getattr(context, var)
    # else:
    #     print 'context parts =', key, var, operator, context
    return operator, context


# @time
def emit(event_name, context=None):
    # print 'event.emit(event_name=%s, context=%s)' % (event_name, context)
    parse = _parse
    results = []
    for listener in listeners.get(event_name, set()).copy():
        func = listener.func
        event_name = listener.event_name
        filters = listener.filters

        # Resolve weak ref.
        try:
            func = func.resolve()
        except ReferenceError:
            # It might happen that a race conditions brings us here.
            try:
                listeners[event_name].remove(listener)
                # print 'removed stale listener: %s' % listener
            except KeyError:
                pass
            continue

        matching_failed = False
        # print 'event iteration =', func, filters
        for key, value in filters.iteritems():
            # print 'key =', key, ';', 'value =', value
            # Resolve weak ref.
            if type(value) is Wrapper:
                value = value.resolve()
            if key in basic_rules:
                matching_failed = basic_rules[key](context, value)
            elif key.startswith('context'):
                key, operator = key.split('__', 1)
                # print 'filter =', key, operator, value
                try:
                    operator, context_value = parse(context, operator)
                except AttributeError:
                    matching_failed = True
                    break
                # print 'context_value =', context_value
                try:
                    rule = context_rules[operator]
                except KeyError:
                    raise Exception('Unknown operator "%s" in filter for func "%s". Possible operators are: %s' % (operator, func, ', '.join(context_rules.keys())))
                # print 'operator parts =', context_value, operator, value
                matching_failed = rule(context_value, value)
            else:
                raise Exception('Unknown key "%s" in filter for func "%s". Possible keys are: %s' % (operator, func, ', '.join(basic_rules.keys())))
            if matching_failed:
                break
        if not matching_failed:
            if hasattr(func, '__wrapped__'):
                spec = getargspec(func.__wrapped__)
            else:
                spec = getargspec(func)
            args = spec.args
            if 'context' in args:
                # print 'executing %s with context: %s' % (func, context)
                results.append((func, func(context=context)))
            elif 'event' in args:
                # print 'executing %s with event: %s' % (func, context)
                results.append((func, func(event=context)))
            else:
                # print 'DEBUG: event.emit() got function without proper event interface:', func
                # print 'executing %s without context.' % func
                results.append((func, func()))
    return results
