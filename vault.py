# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

import os
from collections import OrderedDict
from weakref import WeakValueDictionary, proxy, ProxyTypes
import json

import pygame.image
import pygame.surface

from diamond.helper.image import change_gamma

# TODO rework with WeakValueDictionary as already done in display. And test if we
#      don't get too much rebuilds and loads.
# TODO Should be somewhere else..
image_cache = {}


def load_image(filename, gamma=1.0):
    # print 'load_image(%s, %s)' % (filename, gamma)
    cache_id = '%s::%s' % (filename, gamma)
    if cache_id not in image_cache:
        base_cache_id = '%s::%s' % (filename, 1.0)
        if base_cache_id not in image_cache:
            image_cache[base_cache_id] = pygame.image.load(filename)
            # print 'loaded base image'
        if cache_id != base_cache_id:
            image_cache[cache_id] = change_gamma(image_cache[base_cache_id], gamma)
            # print 'generated specific image'
    return image_cache[cache_id]


def get_subsurface(filename, rect, gamma):
    # print 'get_subsurface(%s, %s, %s)' % (filename, rect, gamma)
    cache_id = '%s::%s::%s' % (filename, rect, gamma)
    if cache_id not in image_cache:
        surface = load_image(filename, gamma)
        subsurface = surface.subsurface(rect)
        image_cache[cache_id] = subsurface
        # print 'generated subsurface'
    return image_cache[cache_id]


class VaultSpriteActionFrame(object):

    def __init__(self, vault_sprite_action, rect, hotspot, delta, duration, events=None):
        super(VaultSpriteActionFrame, self).__init__()

        # A piggyback image is nothing more than a base image carrying
        # other images on top. For better performance we merge them.
        #
        # Got piggyback image?
        if type(rect[0]) is list:
            # Calculate global rect.
            self.rects = rect
            rects = []
            for pos, rect_ in enumerate(rect):
                hotspot_ = hotspot[pos]
                delta_ = delta[pos]
                x = hotspot_[0] - rect_[0] + delta_[0]
                y = hotspot_[1] - rect_[1] + delta_[1]
                rects.append(pygame.Rect(x, y, rect_[2], rect_[3]))
            rects = rects[0].unionall(rects)
            rect = (rect[0][0], rect[0][1], rects.x + rects.w, rects.y + rects.h)
            self.hotspots = hotspot
            hotspot = rect[0], rect[1]
            self.deltas = delta
            delta = rects.topleft
            self.is_piggyback = True
        else:
            self.is_piggyback = False

        self.rect = rect
        self.hotspot = hotspot
        self.delta = delta
        self.duration = duration
        self.vault_sprite_action = proxy(vault_sprite_action) if type(vault_sprite_action) not in ProxyTypes else vault_sprite_action
        self.surfaces = {}
        self.masks = {}
        self.pos_modifier = None
        self.__recalc_pos_modifier()
        if events is None:
            self.events = []
        elif isinstance(events, basestring):
            self.events = [events]
        else:
            self.events = events

    # def __del__(self):
    #     print 'VaultSpriteActionFrame.__del__(%s)' % self

    def __repr__(self):
        return '<VaultSpriteActionFrame(' \
            'rect = %s, hotspot = %s, delta = %s, duration = %s, events = %s)>' % (
            self.rect, self.hotspot, self.delta, self.duration, self.events)

    def copy(self):
        if not self.is_piggyback:
            frame = VaultSpriteActionFrame(self.vault_sprite_action, self.rect, self.hotspot, self.delta, self.duration, self.events)
        else:
            frame = VaultSpriteActionFrame(self.vault_sprite_action, self.rects, self.hotspots, self.deltas, self.duration, self.events)
        return frame

    def get_rect(self):
        return self.rect

    def get_hotspot(self):
        return self.hotspot

    def get_delta(self):
        return self.delta

    def get_pos_modifier(self):
        return self.pos_modifier

    def get_duration(self):
        return self.duration

    def get_surface(self, gamma=1.0):
        gamma_s = str(gamma)
        if gamma_s not in self.surfaces:
            if not self.is_piggyback:
                self.surfaces[gamma_s] = self.vault_sprite_action.vault_sprite.vault.get_subsurface(self.rect, gamma)
            else:
                # Build surface based on items supplied.
                surface = pygame.surface.Surface((self.rect[2], self.rect[3]), pygame.locals.SRCALPHA, 32)
                for pos, rect in enumerate(self.rects):
                    part = self.vault_sprite_action.vault_sprite.vault.get_subsurface(rect, gamma)
                    hotspot = self.hotspots[pos]
                    delta = self.deltas[pos]
                    x = hotspot[0] - rect[0] + delta[0]
                    y = hotspot[1] - rect[1] + delta[1]
                    surface.blit(part, (x, y))
                self.surfaces[gamma_s] = surface
        return self.surfaces[gamma_s]

    def get_mask(self, gamma=1.0):
        gamma_s = str(gamma)
        if gamma_s not in self.masks:
            surface = self.get_surface(gamma)
            mask = pygame.mask.from_surface(surface)
            self.masks[gamma_s] = mask
        return self.masks[gamma_s]

    def get_action(self):
        return self.vault_sprite_action

    def __recalc_pos_modifier(self):
        rect = self.rect
        hotspot = self.hotspot
        delta = self.delta
        x = hotspot[0] - rect[0] + delta[0]
        y = hotspot[1] - rect[1] + delta[1]
        self.pos_modifier = (x, y)


class VaultSpriteAction(object):

    def __init__(self, name, frames, vault_sprite):
        super(VaultSpriteAction, self).__init__()
        self.name = name
        if frames and frames[-1] == -1:  # Should we add a reverse loop?
            frames = frames[:-1]
            frames.extend(reversed(frames[1:-1]))
        self.frames = [VaultSpriteActionFrame(*([self] + frame)) for frame in frames]
        self.vault_sprite = proxy(vault_sprite)

    # def __del__(self):
    #     print 'VaultSpriteAction.__del__(%s)' % self

    def __repr__(self):
        return '<VaultSpriteAction(' \
            'name = %s, frames = %s)>' % (
            self.name, len(self.frames))

    def get_name(self):
        return self.name

    def get_frames(self):
        return self.frames

    def get_frame(self, pos):
        return self.frames[pos]

    def get_sprite(self, pos):
        return self.vault_sprite

    def add_frame(self, rect_or_frame, hotspot=None, delta=None, msecs=60, events=None):
        if type(rect_or_frame) is VaultSpriteActionFrame:
            frame = rect_or_frame
            self.frames.append(frame)
        else:
            rect = rect_or_frame
            if hotspot is None:
                hotspot = rect[0], rect[1]
            if delta is None:
                delta = rect[0], rect[1]
            self.frames.append(VaultSpriteActionFrame(self, rect, hotspot, delta, msecs, events))
        return self.frames[-1]

    def clear_frames(self):
        self.frames = []


class VaultSprite(object):

    def __init__(self, name, actions, vault):
        super(VaultSprite, self).__init__()
        self.name = name
        self.actions = OrderedDict()
        # TODO find out how we can unlock the vault itself.
        self.vault = vault
        for action, frames in actions.iteritems():
            self.actions[action] = VaultSpriteAction(action, frames, self)

    # def __del__(self):
    #     print 'VaultSprite.__del__(%s)' % self

    def __repr__(self):
        try:
            vault_name = str(self.vault)
        except ReferenceError:
            vault_name = '<already gone>'
        return '<VaultSprite(' \
            'name = %s, actions = %s, vault = %s)>' % (
            self.name, len(self.actions), vault_name)

    def get_name(self):
        return self.name

    def get_actions(self):
        return self.actions

    def get_action_names(self):
        return self.actions.keys()

    def get_action(self, name):
        return self.actions[name]

    def get_vault(self):
        return self.vault

    def add_action(self, name):
        self.actions[name] = VaultSpriteAction(name, [], self)
        return self.actions[name]

    def clear_actions(self):
        self.actions = OrderedDict()


class Vault(object):

    __instances = WeakValueDictionary()

    def __init__(self, vault):
        super(Vault, self).__init__()
        self.texture_module = vault
        self.texture_filename = vault.filename
        self.sprites = OrderedDict()
        for name, actions in vault.sprites.iteritems():
            self.sprites[name] = VaultSprite(name, actions, self)
        if self.texture_filename is not None:
            self.surface = load_image(self.texture_filename)
        else:
            self.surface = None

    # def __del__(self):
    #     print 'Vault.__del__(%s)' % self

    def __repr__(self):
        return '<Vault(' \
            'texture_filename = %s, sprites = %s)>' % (
            self.texture_filename, len(self.sprites))

    @classmethod
    def get_instance(cls, vault):
        cache_id = id(vault)
        try:
            cls.__instances[cache_id]
            # print 'return cached vault instance for', vault
            return cls.__instances[cache_id]
        except KeyError:
            pass
        instance = cls(vault)
        cls.__instances[cache_id] = instance
        # print 'generate new vault instance for', vault
        return instance

    @classmethod
    def clear_instance_cache(cls):
        # print 'Vault.clear_instance_cache()'
        del cls.__instances[:]

    def get_sprites(self):
        return self.sprites

    def get_sprite_names(self):
        return self.sprites.keys()

    def get_sprite(self, name=None):
        if name is None:
            name = self.sprites.keys()[0]
        return self.sprites[name]

    def get_subsurface(self, rect, gamma=1.0):
        return get_subsurface(self.texture_filename, rect, gamma)

    def add_sprite(self, name, actions={}):
        self.sprites[name] = VaultSprite(name, actions, self)
        return self.sprites[name]

    def save(self):
        module = self.texture_module
        module_filename = module.__file__
        py_filename = '%s.py' % os.path.splitext(module_filename)[0]
        json_filename = '%s.json' % os.path.splitext(module_filename)[0]
        # print module
        # print module_filename
        # print json_filename
        if not os.path.exists(json_filename):
            if not os.path.exists(py_filename):
                raise Exception('Cannot add missing code to load JSON data into vault without a .py file.')
            # TODO write code into python file.
        # TODO check if code is in python file. add it if necessary.
        # TODO write json file
        # JSON_SPRITE_TEMPLATE = '''
        #         "%(id)d": {
        #             %(actions)s
        #         },
        # '''.rstrip()
        # JSON_ACTION_TEMPLATE = '''
        #             "%(action)s": [
        #                 %(frames)s
        #             ]
        # '''.lstrip()
        # JSON_FRAME_TEMPLATE = '''
        #                 [[%d, %d, %d, %d], [%d, %d], [%d, %d], %d, %s]
        # '''.lstrip()
        # JSON_TEMPLATE = '''
        # {
        #     "filename": "%(filename)s",
        #     "sprites": {%(sprites)s
        #     },
        #     "tile_size": [%(tile_w)d, %(tile_h)d]
        # }
        # '''.lstrip()
        # sprites = []
        # for key, actions in self.sprites.iteritems():
        #     frame = actions['none'][0]
        #     sprites.append(JSON_SPRITE_TEMPLATE % dict(
        #         id=int(key),
        #         x=frame[0][0],
        #         y=frame[0][1],
        #         w=frame[0][2],
        #         h=frame[0][3],
        #     ))
        # json = JSON_TEMPLATE % dict(
        #     filename=data['filename'],
        #     sprites=''.join(sprites).rstrip(','),
        #     tile_w=tile_width,
        #     tile_h=tile_height,
        # )
        # TODO should use the template above to produce pretty print!
        json_data = json.load(open(json_filename, 'rb'), object_pairs_hook=OrderedDict)
        sprites = json_data['sprites'] = OrderedDict()
        for s_name, sprite in self.sprites.iteritems():
            actions = OrderedDict()
            for a_name, action in sprite.actions.iteritems():
                frames = []
                for frame in action.frames:
                    if frame.is_piggyback:
                        frame = frame.rects, frame.hotspots, frame.deltas, frame.duration, frame.events
                    else:
                        frame = frame.rect, frame.hotspot, frame.delta, frame.duration, frame.events
                    # TODO catch reversed animations. perhaps place special event when loading frames.
                    #      if using an event the Sprite._load_frames() should handle the direction.
                    frames.append(frame)
                actions[a_name] = frames
            sprites[s_name] = actions
        json.dump(json_data, open(json_filename, 'wb'))


class GeneratedVault(Vault):

    def __init__(self):
        class EmptyVault():
            filename = None
            sprites = OrderedDict()
        super(GeneratedVault, self).__init__(EmptyVault)
        self.surface_cache = {}

    # def __del__(self):
    #     print 'GeneratedVault.__del__(%s)' % self

    def __repr__(self):
        return '<Vault(' \
            'generated, sprites = %s)>' % len(self.sprites)

    def set_surface(self, surface):
        self.surface = surface
        self.surface_cache.clear()

    def generate_surface(self, width, height):
        self.surface = pygame.Surface((width, height)).convert_alpha()
        self.surface_cache.clear()
        return self.surface

    def get_subsurface(self, rect, gamma=1.0):
        cache_id = '%s::%s' % (rect, gamma)
        base_cache_id = '%s::%s' % (rect, 1.0)
        if base_cache_id not in self.surface_cache:
            self.surface_cache[base_cache_id] = self.surface.subsurface(rect)
        if cache_id not in self.surface_cache:
            self.surface_cache[cache_id] = change_gamma(self.surface_cache[base_cache_id], gamma)
        return self.surface_cache[cache_id]
