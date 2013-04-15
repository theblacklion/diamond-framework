import pygame.mixer as mixer

from diamond import event
from diamond.helper.weak_ref import Wrapper


class Channel(object):

    __channels = []

    def __init__(self, id):
        super(Channel, self).__init__()
        self.reserved = False
        self.id = id
        self.channel = mixer.Channel(id)
        self.is_paused = False

    @classmethod
    def add_channel(cls):
        num_channels = mixer.get_num_channels()
        # print self, 'add_channel', repr(num_channels)
        mixer.set_num_channels(num_channels + 1)
        channel = Channel(num_channels)
        cls.__channels.append(channel)
        return channel

    @classmethod
    def get_free(cls):
        channel = None
        for channel_ in cls.__channels:
            if not channel_.reserved:
                # print cls, 'found free one', channel_
                channel = channel_
                break
        if not channel:
            channel = cls.add_channel()
            # print cls, 'created new one', channel
        channel.reserve()
        # print cls, 'get_free', len(cls.__channels), mixer.get_num_channels()
        return channel

    def is_reserved(self):
        return self.reserved

    def reserve(self):
        self.reserved = True

    def free(self):
        self.reserved = False

    def play(self, sound, volume=None):
        if not self.is_paused:
            self.channel.stop()
            sound, org_volume = sound
            if volume is None:
                volume = org_volume
            sound.set_volume(volume / 255.0)
            self.channel.play(sound)

    def pause(self):
        self.channel.stop()
        self.is_paused = True

    def stop(self):
        self.channel.stop()

    def unpause(self):
        self.is_paused = False


class ChannelArray(object):

    def __init__(self, amount=2):
        channels = []
        for count in range(0, amount):
            channels.append(Channel.get_free())
        self.channels = channels
        self.cur_channel = len(self.channels)  # Next play will start at first.

    def play(self, sound, volume=None):
        self.cur_channel += 1
        if self.cur_channel >= len(self.channels):
            self.cur_channel = 0
        self.channels[self.cur_channel].play(sound, volume=volume)


class Sound(object):

    __instance = None

    def __init__(self):
        # print 'Sound.__init__(%s)' % self
        super(Sound, self).__init__()
        self.sounds = dict()
        self.listeners = [
            event.add_listener(self.pause, 'sound.pause'),
            event.add_listener(self.unpause, 'sound.unpause'),
            event.add_listener(self.toggle, 'sound.toggle'),
        ]
        self.is_paused = False

    def __del__(self):
        # print 'Sound.__del__(%s)' % self
        event.remove_listeners(self.listeners)

    @classmethod
    def get_instance(cls):
        instance = cls.__instance
        if instance is not None:
            instance = instance.resolve()
        if instance:
            return instance
        else:
            instance = cls()
            cls.__instance = Wrapper(instance)
            return instance

    def load(self, filename, volume=255):
        # print 'Sound.load(%s, %s, %d)' % (self, filename, volume)
        id = (filename, volume)
        if id not in self.sounds:
            sound = mixer.Sound(filename)
            self.sounds[id] = (sound, volume)
        return self.sounds[id]

    def stop(self):
        [channel.stop() for channel in Sound.__channels]

    def pause(self):
        [channel.pause() for channel in Sound.__channels]
        self.is_paused = True

    def unpause(self):
        [channel.unpause() for channel in Sound.__channels]
        self.is_paused = False

    def toggle(self):
        if self.is_paused is True:
            self.unpause()
        else:
            self.pause()
