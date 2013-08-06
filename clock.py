# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

from time import time, sleep

from diamond import _startup_time


def get_ticks():
    '''Returns the number of milliseconds since diamond was loaded.'''
    return (time() * 1000) -_startup_time


def wait(msecs):
    sleep(msecs / 1000.0)


def reset():
    '''Resets the statup time to now.'''
    global _startup_time
    _startup_time = time() * 1000


def shift(msecs):
    '''Use this to alter the time for e.g. compensating loading or creation time of scenes.'''
    global _startup_time
    _startup_time += msecs
    if _startup_time > time() * 1000:
        _startup_time = time() * 1000


class Timer(object):

    def __init__(self):
        super(Timer, self).__init__()
        self._start = 0
        self._stop = 0

    def start(self):
        self._start = time() * 1000

    def stop(self):
        self._stop = time() * 1000

    result = property(lambda self: self._stop - self._start)
