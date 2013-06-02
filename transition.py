# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

# TODO make use of http://docs.python.org/library/itertools.html
from types import FunctionType

from diamond.ticker import Ticker, OnetimeTick, BreakTickerLoop
from diamond.helper.weak_ref import Wrapper
# from diamond.decorators import dump_args


class Stack(object):

    def __init__(self, name, transition_manager):
        super(Stack, self).__init__()
        self.name = name
        self.transition_manager = Wrapper(transition_manager)
        self.tick = None
        if name not in transition_manager.stacks:
            transition_manager.stacks[name] = self

    def __repr__(self):
        return '<Stack(name="%s", TransitionManager=%s)>' % (self.name, self.transition_manager)

    # def __del__(self):
    #     print 'Stack.__del__(%s)' % self

    def has_items(self):
        return self.tick is not None

    def __iter__(self):
        name = self.name
        for ticker in self.transition_manager.resolve().tickers:
            if ticker.user_data['stack'].name == name:
                yield ticker

    def get_items(self):
        return list(iter(self))

    def get_last(self):
        name = self.name
        for ticker in reversed(self.transition_manager.resolve().tickers):
            if ticker.user_data['stack'].name == name:
                return ticker
        return None

    def clear(self):
        self.tick = None
        self.transition_manager.resolve().remove_many(self.get_items())

    # @dump_args
    def remove(self):
        self.clear()
        transition_manager = self.transition_manager.resolve()
        if self.name in transition_manager.stacks:
            del transition_manager.stacks[self.name]

    def __getattr__(self, name):
        attr = getattr(self.transition_manager.resolve(), name)
        def wrapper(*args, **kwargs):
            # print 'args =', args
            # print 'kwargs =', kwargs
            kwargs['stack'] = self.name
            return attr(*args, **kwargs)
        return wrapper


class Transition(object):

    @classmethod
    def wait(cls, msecs, dropable=False):
        return [(lambda: None, [], {}, 0, msecs, dropable)]

    @classmethod
    def change(cls, callback, args=[], kwargs={}, delay=0, dropable=False):
        if hasattr(args, '__call__'):
            args = args()
        if hasattr(kwargs, '__call__'):
            kwargs = kwargs()
        return [(callback, args, kwargs, 0, 0 + delay, dropable)]

    @classmethod
    def range(cls, callback, args=[], kwargs={}, range=(0, 1), msecs=100, delay=0, min_step_msecs=10):
        length = max(range) - min(range)
        if length == 0:
            return []
        msecs_part = msecs / float(length)
        step = 1 if range[1] >= range[0] else -1
        # print 'range =', range, 'msecs =', msecs, 'length =', length
        # print 'part =', msecs_part
        results = []
        args_ = args
        kwargs_ = kwargs
        delay = delay
        delay_flush_limit = min(min_step_msecs, msecs)
        is_first = True

        # TODO which variant is faster?
        for count in xrange(range[0], range[1] + step, step):
            delay += msecs_part
            if delay < delay_flush_limit:
                continue
            if hasattr(args, '__call__'):
                args_ = args(count)
            if hasattr(kwargs, '__call__'):
                kwargs_ = kwargs(count)
            result = (callback, args_, kwargs_, count, delay, not is_first)
            results.append(result)
            delay = 0
            # print count
            is_first = False

        # TODO which variant is faster? is this buggy?
        # if hasattr(args, '__call__'):
        #     args_ = lambda count: args(count)
        # else:
        #     args_ = lambda count: args
        # if hasattr(kwargs, '__call__'):
        #     kwargs_ = lambda count: kwargs(count)
        # else:
        #     kwargs_ = lambda count: kwargs
        # for count in xrange(range[0], range[1] + step, step):
        #     delay += msecs_part
        #     if delay < delay_flush_limit:
        #         continue
        #     result = (callback, args_, kwargs_, count, delay, not is_first)
        #     # result = (callback, args_(count), kwargs_(count), count, delay, not is_first)
        #     results.append(result)
        #     delay = 0
        #     # print count
        #     is_first = False

        # TODO Can we fix this missing-last-value-issue someway else?
        delay += msecs_part
        if hasattr(args, '__call__'):
            args_ = args(count)
        if hasattr(kwargs, '__call__'):
            kwargs_ = kwargs(count)
        result = (callback, args_, kwargs_, range[1], delay, False)
        results.append(result)

        # print 'results generated =', len(results)
        return results


class TransitionManager(Ticker):

    def __init__(self, *args, **kwargs):
        super(TransitionManager, self).__init__(*args, **kwargs)
        self.stacks = {}
        self.last_stack_id = -1

    def _get_func(self, callback):
        if type(callback) is tuple:
            func, path = callback
            path = path.split('.')
            while path:
                part = path.pop(0)
                func = getattr(func, part)
        else:
            func = callback
        return func

    # @dump_args
    def add(self, transition, stack='global', append=True, manage_stack=True):
        '''
        Adds a transition to a stack.
        If append is True it will add it at the end of the stack.
        If append is False it will add it at the current timestamp.
        If append is a Stack object it will add it after the latest item in the
        given stack.
        If append is a OnetimeTick it will add it after the timestamp of the
        given item.
        '''
        if type(stack) is Stack:
            if stack.name not in self.stacks:
                self.stacks[stack.name] = stack
        else:
            if stack not in self.stacks:
                self.stacks[stack] = Stack(stack, self)
            stack = self.stacks[stack]
        get_func = self._get_func
        seen_funcs = {}
        timestamp = 0
        cur_tick = self.get_ticks()
        if type(append) is Stack and append.tick:
            # The max() clause ensures that no items get appended to the past.
            previous_timestamp = max(append.tick[2], cur_tick)
        elif type(append) is OnetimeTick:
            # The max() clause ensures that no items get appended to the past.
            previous_timestamp = max(append[2], cur_tick)
        elif append and stack.tick is not None:
            # The max() clause ensures that no items get appended to the past.
            previous_timestamp = max(int(stack.tick[2]), cur_tick)
        else:
            previous_timestamp = cur_tick
        try:
            is_append_to_end_of_tickers = self.tickers[-1][2] < previous_timestamp
            # print 'last ticker:', self.tickers[-1][2]
        except IndexError:
            is_append_to_end_of_tickers = True
        # print '4 vals =', stack.name, previous_timestamp, cur_tick, is_append_to_end_of_tickers
        if not is_append_to_end_of_tickers:
            self.is_dirty = True
            # print previous_timestamp, is_append_to_end_of_tickers
            # print 'stack =', stack
            # import traceback
            # traceback.print_stack()
            # condition = lambda item: item.user_data['stack'] == stack
            # tickers = filter(condition, self.tickers)
            # print tickers
            # print self.tickers[-1]
            # exit()
        timestamp = previous_timestamp
        tick = None
        tickers_append = self.tickers.add
        # print 'previous_timestamp =', previous_timestamp,
        # print 'tickers in queue =', self.stacks[stack]
        for step in transition:
            callback, args, kwargs, count, msecs, dropable = step
            try:
                func = seen_funcs[callback]
            except KeyError:
                func = get_func(callback)
                seen_funcs[callback] = func
            if args is None:
                args = []
            elif type(args) not in (list, tuple, set):
                args = [args]
            if kwargs is None:
                kwargs = {}
            elif type(kwargs) is not dict:
                kwargs = dict(data=kwargs)
            msecs = int(msecs)
            timestamp += msecs

            # What can we do with inline functions and lambdas?
            is_function = isinstance(func, FunctionType)
            has_closure = func.__closure__ is not None
            has_free_vars = func.__code__.co_freevars
            if is_function and has_closure and has_free_vars:
                msg = ('Never put simple functions/lambdas with vars referencing '
                       'the parent (e.g. class instance, nodes, sprites etc.) into '
                       'events or tickers! These can effectively block the garbage '
                       'collector and this will result in a huge memory leak. '
                       'If you need such inline functions please always pass all '
                       'necessary things as parameters to the function. Free vars '
                       'found in function %(name)s of file %(filename)s starting at'
                       ' line %(line)s: %(vars)s')
                raise Exception(msg % dict(
                    name=func.__code__.co_name,
                    filename=func.__code__.co_filename,
                    line=func.__code__.co_firstlineno,
                    vars=', '.join(func.__code__.co_freevars)
                ))
            # func = Wrapper(func)
            # TODO Make contents of args and kwargs weak.
            # for pos, item in enumerate(args):
            #     try:
            #         args[pos] = Wrapper(item)
            #     except TypeError:
            #         pass

            timestamp = round(timestamp, -1)  # TODO does this improve performance or sync sprites?
            tick = OnetimeTick((func, timestamp, timestamp, args, kwargs, dropable))
            tick.user_data['stack'] = stack
            tickers_append(tick)
        if tick is not None:
            latest_tick = self.stacks[stack.name]
            if not latest_tick.tick or latest_tick.tick[2] <= timestamp:
                stack.tick = tick
        # TODO remove this if clause if "last does not match!" does not occur anymore!
        if not append and manage_stack:
            items = stack.get_items()
            items = sorted(items, key=lambda item: item[2])
            last = items[-1] if items else None
            if stack.tick != last:
                print 'add last does not match'
                # for item in items:
                #     print item
                print 'last =', last
                print 'stack =', stack.tick
                stack.tick = last
        # Return start, top and length.
        return previous_timestamp, timestamp, timestamp - previous_timestamp, tick

    # @dump_args
    def remove_many(self, tickers):
        # First collect all stacks from tickers to be deleted.
        seen_stacks = set([ticker.user_data['stack'] for ticker in tickers])
        # Now delete the tickers.
        super(TransitionManager, self).remove_many(tickers)
        # And see if tickers for the stacks remain.
        for stack in seen_stacks:
            stack.tick = stack.get_last()

    # @dump_args
    def clear(self):
        super(TransitionManager, self).clear()
        for name, stack in self.stacks.iteritems():
            # print name, stack.tick
            stack.tick = None
        self.stacks.clear()

    def has_stack(self, name):
        return self.stacks[name].tick is not None

    # @dump_args
    def stack(self, name='_stack_%s'):
        try:
            return self.stacks[name]
        except KeyError:
            if '%s' in name:
                self.last_stack_id += 1
                name = name % self.last_stack_id
            self.stacks[name] = Stack(name, self)
            return self.stacks[name]

    def add_wait(self, msecs=1000, stack='global', append=True):
        self.add(
            Transition.wait(
                msecs=msecs,
            ),
            stack,
            append,
        )

    def add_change(self, callback, args=[], kwargs={}, delay=0, stack='global', append=True):
        return self.add(
            Transition.change(
                callback=callback,
                args=args,
                kwargs=kwargs,
                delay=delay,
            ),
            stack,
            append,
        )

    def add_range(self, callback, args=[], kwargs={}, range=(0, 1), msecs=1000, delay=0, min_step_msecs=10, stack='global', append=True):
        return self.add(
            Transition.range(
                callback=callback,
                args=args,
                kwargs=kwargs,
                range=range,
                msecs=msecs,
                delay=delay,
                min_step_msecs=min_step_msecs,
            ),
            stack,
            append,
        )

    def _injection(self, callback, args=[], kwargs={}, stack='global', current_ticker=None):
        # print '_injection', callback, args, kwargs, stack
        func = self._get_func(callback)
        transition = func(*args, **kwargs)
        tickers = self.tickers
        pos = tickers.index(current_ticker)
        # print 'pos =', pos
        rest = tickers[pos + 1:]
        del tickers[pos + 1:]
        start, stop, length, last_tick = self.add(transition, stack=stack, append=False, manage_stack=False)
        # print 'start =', start, '; stop =', stop, '; length =', length, '; last_tick =', last_tick
        # print 'stack =', stack
        # Calculate difference between requested start and real start.
        late = max(0, (start - current_ticker[2]))
        # print 'late =', late
        # print len(rest)

        # print
        # for ticker in rest:
        #     print ticker, ticker.user_data['stack'].name
        # print

        condition = lambda item: item.user_data['stack'].name == stack
        for ticker in filter(condition, rest):
            # print ticker[2], '->',
            ticker[2] += (length + late)
            # print ticker[2], ticker
        # print
        tickers |= rest

        if rest:
            stack = self.stacks[stack]
            items = sorted(iter(stack), key=lambda item: item[2])
            last = items[-1] if items else None
            if stack.tick != last:
                # print '_injection last does not match'
                # for item in items:
                #     print item
                # print 'last =', last
                # print 'stack =', stack.tick
                # print 'rest =', len(rest)
                stack.tick = last
            self.is_dirty = True
        raise BreakTickerLoop

    # @dump_args
    def add_injection(self, callback, args=[], kwargs={}, delay=0, stack='global', append=True):
        args = callback, args, kwargs, stack
        return self.add(
            Transition.change(
                callback=self._injection,
                args=args,
                delay=delay,
            ),
            stack,
            append,
        )
