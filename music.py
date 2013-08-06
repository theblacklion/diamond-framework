# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

# TODO music.load can also load file-like-objects. we should 

# import pygame.mixer

from diamond import event
from diamond.transition import TransitionManager


class Music(object):

    def __init__(self):
        self.tracklist = []
        self.cur_track = None
        self.ticker = TransitionManager()
        self.ticker.start()
        self.is_paused = False
        self.listeners = [
            event.add_listener(self.pause, 'music.pause'),
            event.add_listener(self.unpause, 'music.unpause'),
            event.add_listener(self.toggle, 'music.toggle'),
        ]

    def __del__(self):
        self.ticker.join()
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
        event.remove_listeners(self.listeners)

    def clear(self):
        self.stop()

    def add(self, vault):
        filename = vault.filename
        self.tracklist.append(filename)

    def load_next(self):
        if self.cur_track is None:
            if len(self.tracklist):
                self.cur_track = 0
        else:
            if len(self.tracklist) > 1:
                self.cur_track += 1
            if self.cur_track >= len(self.tracklist):
                self.cur_track = 0
        if self.cur_track is not None:
            pygame.mixer.music.load(self.tracklist[self.cur_track])
            event.emit('music.loaded', self)

    def play(self):
        if self.cur_track is None:
            self.load_next()
        if self.cur_track is not None:
            pygame.mixer.music.play()
            self.is_paused = False
            event.emit('music.started', self)

    def pause(self):
        pygame.mixer.music.pause()
        self.ticker.pause()
        self.is_paused = True
        event.emit('music.paused', self)

    def unpause(self):
        pygame.mixer.music.unpause()
        self.ticker.unpause()
        self.is_paused = False
        event.emit('music.unpaused', self)

    def toggle(self):
        if self.is_paused is True:
            self.unpause()
        else:
            self.pause()

    def set_volume(self, volume):
        # print 'set_volume(%s, %s)' % (self, volume)
        pygame.mixer.music.set_volume(volume / 100.0)

    def get_volume(self):
        return int(pygame.mixer.music.get_volume() * 100)

    def is_playing(self):
        return pygame.mixer.music.get_busy()

    def is_fading(self):
        return bool(self.ticker.tickers)

    def fade_to(self, dest_volume, msecs=2000):
        volume = self.get_volume()
        self.ticker.add_range(self.set_volume, args=lambda volume: volume, range=(volume, dest_volume), msecs=msecs)

    def fade_in(self, msecs=2000):
        self.fade_to(dest_volume=100, msecs=msecs)

    def fade_out(self, msecs=2000):
        self.fade_to(dest_volume=0, msecs=msecs)
        def func(self):
            self.cur_track = None
        self.ticker.add_change(func, args=[self])

    def stop_fading(self):
        self.ticker.clear()

    def stop(self):
        pygame.mixer.music.stop()
        self.cur_track = None
        self.set_volume(0)
        self.is_paused = False
        event.emit('music.stopped', self)

    def tick(self):
        if not self.is_playing():
            # self.load_next()
            self.play()
        if self.is_playing():
            if self.get_volume() == 0 and self.cur_track is None:
                self.stop()
