# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

from inspect import getargspec
from itertools import takewhile
from types import FunctionType

from diamond import event
from diamond.helper.weak_ref import Wrapper
from diamond.helper.ordered_set import OrderedSet
from diamond.thread import AbstractThread
from diamond.clock import get_ticks, wait
# from diamond.decorators import dump_args


class OnetimeTick(list):

    def __init__(self, *args, **kwargs):
        super(OnetimeTick, self).__init__(*args, **kwargs)
        self.user_data = dict()

    def __hash__(self):
        return id(self)

    # def __del__(self):
    #     print 'OnetimeTick.__del(%s)' % self


class ReoccuringTick(list):

    def __init__(self, *args, **kwargs):
        super(ReoccuringTick, self).__init__(*args, **kwargs)
        self.user_data = dict()

    def __hash__(self):
        return id(self)

    # def __del__(self):
    #     print 'ReoccuringTick.__del(%s)' % self


class BreakTickerLoop(Exception):
    pass


class Ticker(AbstractThread):
    # TODO try make use of http://docs.python.org/tutorial/datastructures.html#using-lists-as-queues

    def __init__(self, limit=25, timeout=20):
        super(Ticker, self).__init__()
        self.tickers = OrderedSet()  # Use OrderedSet. Removing is much faster here.
        self.is_dirty = False
        self.handle_limit_per_iteration = limit
        self.drop_outdated_msecs = timeout
        self.__is_paused = False
        self.listeners = [
            event.add_listener(self._on_dump_event, 'ticker.dump'),
            event.add_listener(self.pause, 'ticker.pause'),
            event.add_listener(self.unpause, 'ticker.unpause'),
        ]
        self.is_threaded = True
        # print 'Init ticker:', self
        # import traceback
        # traceback.print_stack()
        self.is_idle = True

    def teardown(self):
        self.clear()

    def __del__(self):
        # print 'Ticker.__del__(%s)' % self
        event.remove_listeners(self.listeners)

    def get_ticks(self):
        # print get_ticks()
        return get_ticks()

    def _on_dump_event(self, context):
        return self.tickers

    def pause(self):
        if not self.__is_paused:
            # print 'Ticker.pause(%s)' % self
            self.__is_paused = get_ticks()
        # Wait until our tick() is done. Usefull if tick is being called in a thread or via versa.
        while not self.is_idle:
            wait(5)

    def unpause(self):
        if self.__is_paused:
            # print 'Ticker.unpause(%s)' % self
            diff = get_ticks() - self.__is_paused
            for ticker in self.tickers:
                ticker[2] += diff
            self.__is_paused = False

    def add(self, func, msecs, delay=0, onetime=False, args=[], kwargs={}, dropable=False):
        # print 'Ticker.add(%s, %s, %s, %s, %s)' % (func, msecs, delay, args, kwargs)

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

        timestamp = self.get_ticks() + msecs + delay
        # timestamp = round(timestamp, -1)  # TODO does this improve performance or sync sprites?

        if onetime:
            tick = OnetimeTick((func, msecs, timestamp, args, kwargs, dropable))
        else:
            tick = ReoccuringTick((func, msecs, timestamp, args, kwargs, dropable))
        if len(self.tickers):
            # print len(self.tickers)
            # print tick
            # print self.tickers[-1]
            # print tick[2], self.tickers[-1][2], tick[2] < self.tickers[-1][2]
            if tick[2] < self.tickers[-1][2]:
                self.is_dirty = True
        self.tickers.add(tick)
        return tick

    # @dump_args
    def remove(self, func):
        remove = self.tickers.remove
        to_be_removed = []
        to_be_removed_append = to_be_removed.append
        result = False
        for ticker in self.tickers:
            try:
                func_ = ticker[0]
                if type(func_) is Wrapper:
                    func_ = func_.resolve()
            except ReferenceError:
                to_be_removed_append(ticker)
            else:
                # TODO perhaps only compare func and inst?
                if func_ == func:
                    remove(ticker)
                    result = True
                    break
        remove = self.tickers.remove
        [remove(ticker) for ticker in to_be_removed]
        return result

    # @dump_args
    def remove_many(self, tickers):
        remove = self.tickers.discard
        [remove(ticker) for ticker in tickers]

    # @dump_args
    def clear(self):
        is_paused = self.__is_paused
        self.__is_paused = True
        self.tickers.clear()
        # Wait until our tick() is done. Usefull if tick is being called in a thread or via versa.
        # We use a limit here to avoid dead-locks.
        cur_round, max_rounds = 0, 12
        while not self.is_idle and cur_round < max_rounds:
            wait(5)
            cur_round += 1
        self.__is_paused = is_paused

    def tick(self):
        # print 'Ticker.tick(%s) got %d tickers' % (self, len(self.tickers))
        if self.__is_paused or not self.is_idle:
            return
        self.is_idle = False
        if self.is_dirty:
            # tickers = self.tickers.copy()
            # self.tickers.clear()
            # self.tickers |= sorted(tickers, key=lambda item: item[2])
            self.tickers = type(self.tickers)(sorted(self.tickers, key=lambda item: item[2]))
            self.is_dirty = False
            # print 'Ticker.tick(%s) reordered timeline.' % self
        handle_limit_per_iteration = self.handle_limit_per_iteration
        drop_outdated_msecs = self.drop_outdated_msecs
        time = self.get_ticks()
        to_be_removed = []
        mark_outdated = to_be_removed.append
        condition = lambda item: item[2] <= time
        count = 0
        break_out = False
        for ticker in takewhile(condition, self.tickers):
            func, msecs, dest_time, args, kwargs, dropable = ticker

            # Resolve weak ref.
            if type(func) is Wrapper:
                func = func.resolve()

                if func is None:
                    mark_outdated(ticker)
                    continue

            # TODO Resolve weak args and kwargs.
            # args = [item.resolve() if type(item) is Wrapper else item for item in args]

            late = time - dest_time
            # print late, ticker
            if dropable and late > drop_outdated_msecs:
                if late > msecs:
                    dest_time = time
                # print late, ticker
                if type(ticker) is OnetimeTick:
                    mark_outdated(ticker)
                else:
                    ticker[2] = dest_time + msecs
                continue

            count += 1
            if count > handle_limit_per_iteration:
                print('max tickers handle limit per iteration reached (%d/%d).' % (count, handle_limit_per_iteration))
                break

            # print 'Ticker.tick after %d (%d / %d) msecs: %s(*%s, **%s)' % (msecs, dest_time, dest_time - time, func, args, kwargs)
            # print 'dest_time =', dest_time, '; time =', time
            spec = getargspec(func)
            spec_args = spec.args
            # print '*****'
            # print spec
            # print spec_args
            # print kwargs
            if 'current_ticker' in spec_args:
                # print 'found param!'
                kwargs = kwargs.copy()
                kwargs['current_ticker'] = ticker
            # print kwargs
            # print '*****'
            try:
                func(*args, **kwargs)
            except BreakTickerLoop:
                break_out = True
            except Exception:
                self.is_idle = True  # Release lock (wait(), join() etc.).
                raise
            if type(ticker) is OnetimeTick:
                mark_outdated(ticker)
            else:
                ticker[2] = dest_time + msecs
            if break_out:
                break
        if to_be_removed:
            self.remove_many(to_be_removed)
        # if count or len(to_be_removed):
        #     print 'executed %d tickers ; removed %d tickers' % (count, len(to_be_removed))

        self.is_idle = True
        return self.tickers[0][2] if self.tickers else None

    def join(self):
        event.remove_listeners(self.listeners)
        self.clear()
        super(Ticker, self).join()
