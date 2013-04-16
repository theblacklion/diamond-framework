# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

import random

import pygame

from diamond.vault import Vault, VaultSprite, GeneratedVault
from diamond import event
from diamond.transition import Transition
from diamond.effects import TransitionEffects
from diamond.array import Array
from diamond.decorators import dump_args, time


class Sprite(object):

    def __init__(self, vault):
        super(Sprite, self).__init__()
        assert type(vault) is VaultSprite
        self.vault = vault
        self.parent_node = None
        self.ancestor_nodes = []
        self.display = None  # Is being set by on_node_added() and attach_to_display().
        self.pos = (0, 0)
        self.pos_real = None
        self.pos_real_in_tree = None  #(0, 0)
        self.size = (0, 0)
        self.order_pos = 0  # Influences ordering along children of parent node.
        self.hotspot = (0, 0)
        self.rotation = 0.0
        self.scaling = (0.0, 0.0)
        self.rgba = 1.0, 1.0, 1.0, 1.0  # Color and alpha value.
        self.rgba_inherited = 1.0, 1.0, 1.0, 1.0  # Color and alpha value.
        self.gamma = 1.0  # Gamma manipulation (0 = dark, 2 = bright)
        self.gamma_inherited = 1.0  # Gamma manipulation
        self.default_action = 'none'
        self.action = self.default_action
        self.action_queue = []
        self.frame = None
        self.frame_no = 0
        self.frames = {}  # Cache for our frames including textures.
        self.frame_action_length = 0
        self.frame_plan = None
        self.align_box = None
        self.pos_is_dirty = True
        self.is_dirty = True
        self.tex_dl = None
        self.frames_is_dirty = True
        self.texture_is_dirty = False
        self.is_hidden = False
        self.is_attached = False
        self.is_animation_paused = False
        self.listeners = [
            event.add_listener(self.display_screen_dropped_event, 'display.screen.dropped'),
            event.add_listener(self.display_screen_created_event, 'display.screen.created')
        ]
        self.track_movement = False
        self.track_animation_loop = False
        self.track_animation_events = False

    # @dump_args
    def __del__(self):
        # print 'Sprite.__del__(%s)' % self
        self.detach_from_display()
        event.remove_listeners(self.listeners)

    @classmethod
    def make(cls, vault_module, sprite_name=None):
        '''Factory which creates a vault and returns a proper Sprite object.'''
        if not isinstance(vault_module, Vault):
            vault = Vault.get_instance(vault_module)
        else:
            vault = vault_module
        if sprite_name is not None:
            vault = vault.get_sprite(str(sprite_name))
        else:
            vault = vault.get_sprites().values()[0]
        return cls(vault=vault)

    @classmethod
    def make_many(cls, vault_module, sprite_name=None, amount=1):
        '''Factory which creates a vault and returns x Sprite objects within a list.'''
        if not isinstance(vault_module, Vault):
            vault = Vault.get_instance(vault_module)
        else:
            vault = vault_module
        if sprite_name is not None:
            vault = vault.get_sprite(sprite_name)
        else:
            vault = vault.get_sprites().values()[0]
        return [cls(vault=vault) for count in xrange(0, amount)]

    # @time
    def on_node_added(self, display, node=None, hard=True):
        '''Event is being called when being added to Node object.'''
        if self.display and display != self.display:
            self.detach_from_display()
            self.display = display
            self.parent_node = node
            if display is not None:  # Add sprite to node without display?
                self.attach_to_display()
        elif not self.display:
            self.display = display
            self.parent_node = node
            if display is not None:  # Add sprite to node without display?
                self.attach_to_display()
        else:
            self.detach_from_display(unload=False)
            self.display = display
            if not self.parent_node:
                if hard:
                    self._update_frame_plan()
            self.parent_node = node
            self.attach_to_display(load=False)
        self.update_inherited_rgba(force=True)
        self.update_inherited_gamma(force=True)
        self.ancestor_nodes = node.get_ancestor_nodes()
        self._recalc_real_pos()
        # self._recalc_real_pos_in_tree()  # We probably don't need this anymore.
        self._add_to_update_list()

    # @time
    def on_node_removed(self, node=None, hard=True):
        if hard:
            if self.frames:
                self.set_action(self.default_action, hard=True)
        if self.display:
            self.detach_from_display(unload=False)
        self.parent_node = None
        self.pos_real = None
        del self.ancestor_nodes[:]
        self._remove_from_update_list()

    def add_to(self, parent, hard=True):
        '''Convenience function.'''
        parent.add(self, hard=hard)
        self.pos_is_dirty = True

    def remove_from_parent(self, hard=True):
        self.parent_node.remove(self, hard=hard)

    def switch_parent_node(self, new_node, translate_pos=True):
        # TODO perhaps move this somewhere else?
        # TODO implement gamma and rgba transition.
        x, y = self.parent_node.translate_pos(self.pos, new_node)
        self.remove_from_parent(hard=False)
        self.add_to(new_node, hard=False)
        # print x, y
        self.set_pos(x, y)

    def __repr__(self):
        pos = '%s,%s' % self.pos
        name = 'Sprite(%s.%s@%s)' % (self.vault.name, self.__hash__(), pos)
        # if self.parent_node:
        #     return '<%s -> %s>' % (self.parent_node, name)
        return '<%s>' % name

    def _get_delay_from_msecs_tuple(self, msecs):
        if type(msecs) in (tuple, list):
            min, max = msecs
            msecs = min + int((max - min) * random.random())
            # print (min, max), msecs
        return msecs

    # @dump_args
    def _rebuild_frame_plan(self):
        get_delay_from_msecs_tuple = self._get_delay_from_msecs_tuple
        plan = []
        # timestamp = pygame.time.get_ticks()
        timestamp = 0
        for frame_no, frame in enumerate(self.frames[self.action]):
            timestamp += get_delay_from_msecs_tuple(frame['frame_vault'].get_duration())
            plan.append([timestamp, frame, frame_no])
        self.frame_plan = plan
        # print 'timestamp =', timestamp  # FIXME
        cur = pygame.time.get_ticks()
        offset = (cur % timestamp) if timestamp else 0
        for frame in plan:
            frame[0] += cur - offset

    # @dump_args
    def _update_frame_plan(self, offset=0):
        if not self.frame_plan:
            if self.frames_is_dirty is not True:
                raise Exception('missing frame plan for update.')
                self._rebuild_frame_plan()
            return
        get_delay_from_msecs_tuple = self._get_delay_from_msecs_tuple
        timestamp = pygame.time.get_ticks()
        # If plan exists only walk into it and change the durations.
        for item in self.frame_plan:
            frame = item[1]
            timestamp += get_delay_from_msecs_tuple(frame['frame_vault'].get_duration()) + offset
            item[0] = timestamp

    # @dump_args
    def _load_frames(self):
        # print
        # import traceback
        # traceback.print_stack()
        # print
        frames = self.frames = {}
        get_texture_instance = self.display.get_texture_instance
        get_texture_dl_instance = self.display.get_texture_dl_instance
        rgba = self.rgba_inherited
        gamma = self.gamma_inherited
        gamma_s = str(gamma)
        rotation = self.rotation  # TODO should use rotation_inherited
        for action, obj in self.vault.get_actions().iteritems():
            frames_ = obj.get_frames()
            action_ = frames[action] = []
            for frame in frames_:
                surfaces = {}
                surfaces[gamma_s] = frame.get_surface(gamma)
                texture = get_texture_instance(surfaces[gamma_s])
                texture_dl = get_texture_dl_instance(texture, rgba, rotation)
                action_.append(dict(
                    texture=texture,
                    texture_dl=texture_dl,
                    frame_vault=frame,
                    surfaces=surfaces,
                    current_gamma=gamma,
                ))
        self.frame = self.frames[self.action][self.frame_no]
        self.frame_action_length = len(self.frames[self.action])
        self.size = self.frame['frame_vault'].rect[2:]
        self._rebuild_frame_plan()

    # @dump_args
    def __rebuild_frame_textures(self):
        # print
        # import traceback
        # traceback.print_stack()
        # print
        get_texture_instance = self.display.get_texture_instance
        get_texture_dl_instance = self.display.get_texture_dl_instance
        rgba = self.rgba_inherited
        rotation = self.rotation  # TODO should use rotation_inherited
        gamma = self.gamma_inherited
        gamma_s = str(gamma)
        for action, frames in self.frames.iteritems():
            for frame in frames:
                # TODO move all stuff here into display. It should track and
                #      cache the vaults and just return the DLs.
                last_gamma = frame['current_gamma']
                surfaces = frame['surfaces']
                if last_gamma != gamma:
                    # print 'last =', last_gamma, 'cur =', gamma
                    if gamma_s not in surfaces:
                        surfaces[gamma_s] = frame['frame_vault'].get_surface(gamma)
                        # print 'add surface', gamma_s, surfaces[gamma_s]
                    texture = get_texture_instance(surfaces[gamma_s])
                    frame.update(dict(
                        texture=texture,
                        current_gamma=gamma,
                    ))
                    # print 'get texture', texture
                texture_dl = get_texture_dl_instance(frame['texture'], rgba, rotation)
                if frame['texture_dl'] != texture_dl:
                    frame['texture_dl'] = texture_dl

    # @dump_args
    def _unload_frames(self):
        self.frame = None
        self.frame_no = 0
        self.frames = {}  # Cache for our frames including textures.
        self.frame_action_length = 0
        self.frame_plan = None
        self.size = (0, 0)
        # self.action = self.default_action  # Why do we need this?

    def has_action(self, name):
        return name in self.frames.keys()

    # @dump_args
    def set_action(self, name, hard=False):
        del self.action_queue[:]
        if not hard and self.action == name:
            return  # Don't reset to frame 0 - just keep going.
        self.action = name
        self.frame_no = 0
        self.frame = self.frames[name][0]
        self.frame_action_length = len(self.frames[name])
        self.size = self.frame['frame_vault'].rect[2:]
        self._rebuild_frame_plan()
        self.is_dirty = True
        self._recalc_real_pos()

    def add_action(self, name):
        self.action_queue.append(name)

    def clear_action_queue(self):
        del self.action_queue[:]

    # @dump_args
    def recalc_real_pos(self, recursive=False):
        self.pos_is_dirty = True if not recursive else 'recursive'
        self._add_to_update_list()

    def _get_align_box_offset(self, rect, boxrect, align):
        abx, aby = 0, 0
        selfrect = pygame.Rect(0, 0, rect[2], rect[3])
        finalrect = boxrect.clamp(selfrect.clamp(boxrect))
        if align == 'center':
            pass
        elif align == 'left':
            finalrect.x = 0
        elif align == 'right':
            finalrect.x = finalrect.w - selfrect.w
        elif align == 'top':
            finalrect.y = 0
        elif align == 'bottom':
            finalrect.y = finalrect.h - selfrect.h
        elif align == 'topleft':
            finalrect.x = 0
            finalrect.y = 0
        elif align == 'topright':
            finalrect.x = finalrect.w - selfrect.w
            finalrect.y = 0
        elif align == 'bottomleft':
            finalrect.x = 0
            finalrect.y = finalrect.h - selfrect.h
        elif align == 'bottomright':
            finalrect.x = finalrect.w - selfrect.w
            finalrect.y = finalrect.h - selfrect.h
        else:
            raise Exception('Unknown alignment: %s' % align)
        # print boxrect, selfrect, finalrect
        abx = abs(finalrect.x)
        aby = abs(finalrect.y)
        # print abx, aby
        return abx, aby

    # @dump_args
    def _recalc_real_pos_in_tree(self):
        # Keep in sync with Node.update_real_pos_in_tree !
        try:
            px, py = self.parent_node.pos_real_in_tree
            ix, iy = self.pos_real
            new_pos = (px + ix, py + iy)
            if new_pos != self.pos_real_in_tree:
                self.pos_real_in_tree = new_pos
                if self.parent_node.order_matters:
                    self.parent_node.child_sprites_need_reorder = True
        except AttributeError:
            pass

    # @dump_args
    def _recalc_real_pos(self, recursive=False):
        if self.frame is None:
            return False
        # Calculate initial position.
        frame_vault = self.frame['frame_vault']
        fv_x, fv_y = frame_vault.pos_modifier
        x = self.pos[0] - fv_x
        y = self.pos[1] - fv_y
        # Try to center within box if necessary.
        if self.align_box:
            abx, aby = self._get_align_box_offset(frame_vault.rect, *self.align_box)
            x += abx
            y += aby
        # Calculate reposition for rotation.

        # Calculate reposition for scaling.

        # Check if position has changed and we have to do something.
        if (x, y) != self.pos_real or recursive:
            # print self, (x, y), self.pos_real, (x, y) != self.pos_real, recursive
            self.pos_real = (x, y)
            self._recalc_real_pos_in_tree()
            return True
        return False

    # @dump_args
    def set_pos(self, x, y):
        self.pos = x, y
        self.pos_is_dirty = True
        self._add_to_update_list()

    # @dump_args
    def set_pos_rel(self, rx, ry):
        self.pos = self.pos[0] + rx, self.pos[1] + ry
        self.pos_is_dirty = True
        self._add_to_update_list()

    # @dump_args
    def set_order_pos(self, z):
        self.order_pos = z
        self.pos_is_dirty = True
        self._add_to_update_list()

    # @dump_args
    def set_rotation(self, angle):
        rest = 0
        if angle < 0:
            rest = angle - (360 * (angle / 360))
            angle = 360 - (360-rest)
        elif angle >= 360:
            angle = angle - (360 * (angle / 360))
        else:
            rest = angle
        # print rest
        angle = max(0.0, min(359.0, angle))
        if angle != self.rotation:
            self.rotation = angle
            self.texture_is_dirty = True
            # TODO gather inherited rotation
            self._add_to_update_list()

    def get_rotation(self):
        return self.rotation

    # @dump_args
    def get_inherited_rgba(self):
        # print 'get_inherited_rgba:', self, self.rgba, self.parent_node
        r1, g1, b1, a1 = self.rgba
        # print 'me', self, r1, g1, b1, a1
        r2, g2, b2, a2 = self.parent_node.rgba_inherited
        # print 'parent', self.parent_node, r2, g2, b2, a2
        return r1 * r2, g1 * g2, b1 * b2, a1 * a2

    def update_inherited_rgba(self, force=False):
        new_rgba = self.get_inherited_rgba()
        if new_rgba != self.rgba_inherited or force:
            self.rgba_inherited = new_rgba
            self.texture_is_dirty = True
            try:
                self.display.drawables_dirty = True
                self._add_to_update_list()
            except AttributeError:
                pass

    def set_alpha(self, alpha):
        r, g, b, a = self.rgba
        alpha = max(0.0, min(1.0, alpha / 100.0))
        if a != alpha:
            self.rgba = r, g, b, alpha
            self.texture_is_dirty = True
            self._add_to_update_list()
            if self.parent_node:
                self.update_inherited_rgba()

    def get_alpha(self):
        return self.rgba[3] * 100

    def set_tint(self, r=None, g=None, b=None):
        if r is None and g is None and b is None:
            raise Exception('set_tint() requires at least one of r, g or b.')
        func = lambda v: max(0.0, min(1.0, v / 100.0)) if v is not None else 0.0
        rgba = func(r), func(g), func(b), self.rgba[3]
        if rgba != self.rgba:
            self.rgba = rgba
            self.texture_is_dirty = True
            self._add_to_update_list()
            if self.parent_node:
                self.update_inherited_rgba()

    def get_tint(self):
        return self.rgba[:3]

    # @dump_args
    def get_inherited_gamma(self):
        # print 'get_inherited_gamma:', self, self.gamma
        g1 = self.gamma
        # print 'me', self, g1
        g2 = self.parent_node.gamma_inherited
        # print 'parent', self.parent_node, g2
        return g1 * g2

    def update_inherited_gamma(self, force=False):
        new_gamma = self.get_inherited_gamma()
        if new_gamma != self.gamma_inherited or force:
            self.gamma_inherited = new_gamma
            self.texture_is_dirty = True
            self._add_to_update_list()

    def set_gamma(self, value):
        value = max(0.0, min(2.0, value / 100.0))
        if self.gamma != value:
            self.gamma = value
            self.texture_is_dirty = True
            self._add_to_update_list()
            if self.parent_node:
                self.update_inherited_gamma()

    def get_gamma(self):
        return self.gamma * 100

    # @dump_args
    def hide(self):
        '''
        NOTE: If you change this also adapt Node.hide_children!
        '''
        self.is_hidden = True
        # try:
        #     self.display.display_list_dirty = True
        # except AttributeError:
        #     pass
        if self.parent_node:
            self.parent_node.on_child_hidden(self)

    # @dump_args
    def show(self):
        '''
        NOTE: If you change this also adapt Node.show_children!
        '''
        self.is_hidden = False
        self.pos_is_dirty = True
        self._add_to_update_list()
        # try:
        #     self.display.display_list_dirty = True
        # except AttributeError:
        #     pass
        self.is_dirty = True
        if self.parent_node:
            self.parent_node.on_child_shown(self)

    def set_align_box(self, width, height, align='center'):
        '''
        Sets up an align box. Choices are:
        center, left, right, top, bottom,
        topleft, topright, bottomleft, bottomright
        '''
        self.align_box = pygame.Rect(0, 0, width, height), align
        self.pos_is_dirty = True
        self._add_to_update_list()

    def get_align_box(self):
        return [self.align_box[0].w, self.align_box[0].h, self.align_box[1]]

    def unset_align_box(self):
        self.align_box = None

    def get_rect(self, exclude_hidden=True):
        '''
        Returns a pygame.Rect with the real pos and size.

        @param exclude_hidden: Unused. See Node.get_rect() why it is here.
        '''
        if self.pos_real_in_tree is None:
            self._recalc_real_pos()
        return pygame.Rect(self.pos_real_in_tree[0], self.pos_real_in_tree[1], self.size[0], self.size[1])

    # @time
    def attach_to_display(self, load=True, display=None):
        if display:
            self.display = display
        if load:
            self.frames_is_dirty = True
        self.is_dirty = True
        self.is_attached = True
        self.pos_is_dirty = True
        if self.display:
            self.display.display_list_dirty = True
            self._add_to_update_list()

    # @time
    def detach_from_display(self, unload=True):
        if unload:
            if self.display:
                self._unload_frames()
            self.frame_action_length = 0
        self.pos_is_dirty = False
        self.texture_is_dirty = False
        self.is_dirty = False
        self.is_attached = False
        self.pos_real = None
        if self.display:
            self.display.display_list_dirty = True
            self._remove_from_update_list()

    def replace_vault(self, vault):
        self.detach_from_display(unload=True)
        self.vault = vault
        self.attach_to_display()

    # @time
    def display_screen_dropped_event(self, context):
        if self.display:
            self.detach_from_display(unload=True)

    # @time
    def display_screen_created_event(self, context):
        if self.display:
            self.attach_to_display(load=True)

    def pause_animation(self):
        self.is_animation_paused = True

    def unpause_animation(self):
        self.is_animation_paused = False
        self._update_frame_plan()

    def _add_to_update_list(self, timestamp=0, rel_timestamp=None):
        try:
            self.display.add_to_update_list(self, timestamp, rel_timestamp)
        except AttributeError:
            pass

    def _remove_from_update_list(self):
        try:
            self.display.remove_from_update_list(self)
        except AttributeError:
            pass

    def _update_animation(self):
        cur_time = pygame.time.get_ticks()
        plan = self.frame_plan
        frame_no = self.frame_no
        frames = self.frames[self.action]
        pick_new = False
        for stamp, frame, frame_no_ in plan[frame_no:]:
            if stamp >= cur_time:
                pick_new = frame_no_
                break
        # print self, pick_new, frame_no, len(frames), plan[-1][0], cur_time, plan[-1][0] < cur_time
        if pick_new and pick_new != frame_no:
            # print pick_new, frame_no, len(frames)
            self.frame_no = pick_new
            self.frame = frames[pick_new]
            self.size = self.frame['frame_vault'].rect[2:]
            self.pos_is_dirty = True
            self.is_dirty = True
            if self.track_animation_events:
                for event_ in self.frame['frame_vault'].events:
                    event.emit('sprite.animation.event', Array(
                        event=event_,
                        sprite=self,
                    ))
        elif plan[-1][0] < cur_time:
            if not self.action_queue:
                # We make sure that our offset will never be bigger than a
                # complete animation loop.
                # duration = plan[-1][0] - plan[0][0]
                # offset = cur_time - plan[-1][0]
                # offset = offset % duration
                # self._update_frame_plan(offset=offset)
                # TODO Offset above seems to place animations out of sync.
                # TODO Maybe we can use optional shared frame plans via class vars??
                self._update_frame_plan()
                self.frame_no = 0
                self.frame = frames[0]
                self.size = self.frame['frame_vault'].rect[2:]
            else:
                action = self.action_queue.pop(0)
                self.set_action(action)
            self.pos_is_dirty = True
            self.is_dirty = True
            if self.track_animation_loop:
                event.emit('sprite.animation.looped', self)
        self._add_to_update_list(self.frame_plan[self.frame_no][0])

    # TODO Try to avoid the update call if not necessary by letting the display
    #      filter all dirty and outdated sprites for the update round.
    #      For the animation the sprite should save the next required update
    #      timestamp.
    #      Perhaps we can combine both functionalities by using a 0 for a ASAP
    #      update and a normal timestamp for a scheduled one.
    #      Either way filtering could also be done by the sprite placing itself
    #      into the display update list with a timestamp or 0 (for ASAP).
    #      Before and after this we should measure the cpu load and msecs of
    #      the display update method.
    # @dump_args
    def update(self):
        if self.frames_is_dirty:
            self._load_frames()
            self.frames_is_dirty = False
        if self.frame_action_length > 1 and not self.is_animation_paused:
            self._update_animation()
        if self.pos_is_dirty:
            # print self, self.pos_real
            # TODO testing on recursive lets gem animation stop before end. why?
            # TODO this also affects set_pos.
            if self._recalc_real_pos(recursive=self.pos_is_dirty == 'recursive'):
                try:
                    if self.parent_node.order_matters:
                        self.display.display_list_dirty = True
                    else:
                        self.display.drawables_dirty = True
                except AttributeError:
                    pass
                self.is_dirty = True
                if self.track_movement:
                    event.emit('sprite.moved', self)
            self.pos_is_dirty = False
        if self.texture_is_dirty:
            self.texture_is_dirty = False
            self.__rebuild_frame_textures()
            self.is_dirty = True
        if self.is_dirty:
            # print self, self.pos_real
            if not self.is_hidden:
                self.display.drawables_dl_dirty = True
            self.is_dirty = False


class SpriteEffects(TransitionEffects):

    def _move_by(self, sprite, pos, msecs, delay):
        # Calc distance from src to dst.
        x1, y1 = sprite.pos
        x2, y2 = x1 + pos[0], y1 + pos[1]
        action = 'move' if 'move' in sprite.frames.keys() else sprite.default_action
        transition = (
            Transition.change(callback=(sprite, 'set_action'), args=(action), delay=delay) +
            self._calc_movement(sprite, msecs, x1, y1, x2, y2) +
            Transition.change(callback=(sprite, 'add_action'), args=(sprite.default_action))
        )
        return transition

    def move_by(self, sprite, stack='global', pos=(0, 0), msecs=1000, delay=0, append=True):
        if sprite.pos_is_dirty:
            sprite._recalc_real_pos()
        if append:
            self.add_injection(callback=self._move_by, args=(sprite, pos, msecs, 0), delay=delay, stack=stack, append=append)
        else:
            transition = self._move_by(sprite, pos, msecs, delay)
            self.add(transition, stack=stack, append=append)

    @time
    def _move_to(self, sprite, pos, msecs, delay):
        # Calc distance from src to dst.
        x1, y1 = sprite.pos
        x2, y2 = pos
        action = 'move' if 'move' in sprite.frames.keys() else sprite.default_action
        transition = (
            Transition.change(callback=(sprite, 'set_action'), args=(action), delay=delay) +
            self._calc_movement(sprite, msecs, x1, y1, x2, y2) +
            Transition.change(callback=(sprite, 'add_action'), args=(sprite.default_action))
        )
        return transition

    @time
    def move_to(self, sprite, stack='global', pos=(0, 0), msecs=1000, delay=0, append=True):
        if sprite.pos_is_dirty:
            sprite._recalc_real_pos()
        if append:
            self.add_injection(callback=self._move_to, args=(sprite, pos, msecs, 0), delay=delay, stack=stack, append=append)
        else:
            transition = self._move_to(sprite, pos, msecs, delay)
            self.add(transition, stack=stack, append=append)
        # transition = self._move_to(sprite, pos, msecs, delay)
        # self.add(transition, stack=stack, append=append)
        # sprite.pos = pos

    # @dump_args
    def rotate_to(self, sprite, stack='global', angle=0.0, msecs=1000, delay=0, append=True):
        if sprite.pos_is_dirty:
            sprite._recalc_real_pos()
        if append:
            self.add_injection(callback=self._rotate_to, args=(sprite, angle, msecs), delay=delay, stack=stack, append=append)
        else:
            transition = self._rotate_to(sprite, angle, msecs)
            self.add(transition, stack=stack, append=append)


class SpritePrimitives(object):

    @classmethod
    def make_rectangle(cls, width, height,
            color=(255, 255, 255, 255), background=(0, 0, 0, 0), thickness=1,
            sprite_name='default', action_name='none',
            hotspot=None, delta=None):
        vault = GeneratedVault()
        surface = vault.generate_surface(width, height)
        surface.fill(color, rect=(0, 0, width, height))
        surface.fill(background, rect=(thickness, thickness, width - (thickness * 2), height - (thickness * 2)))
        sprite = vault.add_sprite(sprite_name)
        action = sprite.add_action(action_name)
        action.add_frame((0, 0, width, height), hotspot, delta)
        return Sprite.make(vault)
