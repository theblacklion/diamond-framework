# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

from threading import Thread

from diamond.clock import get_ticks, wait


class AbstractThread(Thread):

    STATE_RUNNING = 3
    STATE_STOP = 8
    STATE_STOPPED = 9

    def __init__(self):
        super(AbstractThread, self).__init__()
        self.state = AbstractThread.STATE_STOPPED
        self.sleep_timeout = 1.0 / 60 * 1000.0  # TODO should we base this on our framerate or vsync?

    def tick(self):
        '''Overwrite this method for doing your stuff.'''
        raise NotImplemented()

    def run(self):
        self.state = AbstractThread.STATE_RUNNING
        while self.state == AbstractThread.STATE_RUNNING:
            start = get_ticks()
            next_tick = self.tick()
            duration = get_ticks() - start
            # print duration, self.sleep_timeout
            if next_tick is not None:
                # print start, next_tick, next_tick - start
                sleep = max(start, next_tick) - start
            else:
                # print None
                sleep = 0
            timeout = self.sleep_timeout - duration
            # print 1, timeout, sleep
            timeout += sleep
            # print 2, timeout
            timeout = max(self.sleep_timeout, timeout)
            # print 3, timeout
            wait(timeout)

    def join(self):
        if self.state == AbstractThread.STATE_RUNNING:
            self.state = AbstractThread.STATE_STOP
            super(AbstractThread, self).join()
            self.state = self.STATE_STOPPED
        #     print 'Thread joined:', self
        # else:
        #     print 'Thread not started, yet.'

    def __del__(self):
        # print 'Thread.__del__(%s)' % self
        super(Thread, self).__del__()
