# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

from itertools import chain

import pygame

from diamond import event
from diamond.sprite import Sprite
from diamond.vault import GeneratedVault
from diamond.helper.slicable_set import SlicableSet
from diamond.helper.ordered_set import OrderedSet
from diamond.decorators import dump_args, time


class Node(object):

    def __init__(self, name=None):
        super(Node, self).__init__()
        self.name = name
        self.parent_node = None
        self.display = None
        self.child_nodes = OrderedSet()
        self.child_nodes_hidden = OrderedSet()
        self.child_sprites = OrderedSet()
        self.child_sprites_hidden = OrderedSet()
        self.child_nodes_need_reorder = False
        self.child_sprites_need_reorder = False
        self.pos = (0, 0)
        self.pos_real = (0, 0)
        self.pos_real_in_tree = None  # (0, 0)
        self.order_pos = 0  # Influences ordering along children of parent node.
        self.manage_order_pos = True  # Auto presets order_pos with len() + 1.
        self.hotspot = (0, 0)
        self.rgba = 1.0, 1.0, 1.0, 1.0  # Color and alpha value.
        self.rgba_inherited = 1.0, 1.0, 1.0, 1.0  # Color and alpha value.
        self.gamma = 1.0  # Gamma manipulation (0 = dark, 2 = bright)
        self.gamma_inherited = 1.0  # Gamma manipulation
        self.pos_is_dirty = True
        self.pos_real_is_dirty = True
        self.__order_matters = True
        self.is_hidden = False
        self.clipping_region = None
        self.clipping_region_inherited = self.clipping_region
        self.track_movement = False
        self.cached_tree = None
        self.cached_tree_dirty = True
        self.cached_representation = None
        self.cached_representation_dirty = True
        self.cached_representation_sprite_list = OrderedSet()

    def set_clipping_region(self, x, y, w, h):
        self.clipping_region = pygame.Rect(x, y, w, h)
        self.inherit_clipping_region()
        # TODO can we somehow move this into attach_to_display?
        self.display.enable_clipping()

    def inherit_clipping_region(self):
        rect = self.clipping_region
        # print self, rect, self.display
        if rect is None:
            if self.display is not None:
                # print 1
                rect = self.display.get_rect()
                self.clipping_region = rect
            else:
                # print 2
                return
        if self.parent_node and self.parent_node.clipping_region_inherited is not None:
            rect = rect.clip(self.parent_node.clipping_region_inherited)
        # print rect
        self.clipping_region_inherited = rect
        for child in self.child_nodes | self.child_nodes_hidden:
            child.inherit_clipping_region()

    def __get_order_matters(self):
        return self.__order_matters

    # @time
    def __set_order_matters(self, bool):
        if bool and type(self.child_nodes) is not OrderedSet:
            # print self, 'convert to OrderedSet'
            self.child_nodes = OrderedSet(self.child_nodes)
            self.child_nodes_hidden = OrderedSet(self.child_nodes_hidden)
            self.child_sprites = OrderedSet(self.child_sprites)
            self.child_sprites_hidden = OrderedSet(self.child_sprites_hidden)
            self.cached_representation_sprite_list = OrderedSet(self.cached_representation_sprite_list)
            self.child_nodes_need_reorder = True
            self.child_sprites_need_reorder = True
        elif not bool and type(self.child_nodes) is not SlicableSet:
            # print self, 'convert to SlicableSet'
            self.child_nodes = SlicableSet(self.child_nodes)
            self.child_nodes_hidden = SlicableSet(self.child_nodes_hidden)
            self.child_sprites = SlicableSet(self.child_sprites)
            self.child_sprites_hidden = SlicableSet(self.child_sprites_hidden)
            self.cached_representation_sprite_list = SlicableSet(self.cached_representation_sprite_list)
        self.__order_matters = bool

    order_matters = property(__get_order_matters, __set_order_matters)

    def set_caching(self, bool):
        if bool:
            if self.cached_representation is None:
                self.cached_representation = True
        else:
            if self.cached_representation is not None:
                # TODO correctly remove sprite and restore children

                self.cached_representation = None
                self.cached_representation_sprite_list.clear()

    # @time
    def on_node_added(self, display, node=None, hard=True):
        '''Event is being called when being added to Node object.'''
        attach_required = self.display != display and display
        self.display = display
        self.parent_node = node
        self.update_inherited_rgba()
        self.update_inherited_gamma()
        self._recalc_real_pos()
        self._update_real_pos_in_tree()
        if attach_required:  # Add node to node with display which we have not?
            self.attach_to_display(display=display)
        self.inherit_clipping_region()

    # @time
    def on_node_removed(self, node=None, hard=True):
        if self.display:
            self.detach_from_display()
        self.parent_node = None
        self.pos_real = (0, 0)
        if self.display:
            self.display.on_node_child_removed(self)

    def __repr__(self):
        pos = '%d,%d' % self.pos
        try:
            pos_real_in_tree = '%d,%d' % self.pos_real_in_tree
        except TypeError:
            pos_real_in_tree = 'None'
        if self.name:
            name = 'Node(%s@%s => %s)' % (self.name, pos, pos_real_in_tree)
        else:
            name = 'Node(@%s => %s)' % (pos, pos_real_in_tree)
        # if self.parent_node:
        #     return '%s -> %s' % (self.parent_node, name)
        # else:
        #     return name
        return name

    # @time
    def add(self, child, hard=True):
        if isinstance(child, Node):
            if child.is_hidden:
                self.child_nodes_hidden.add(child)
            else:
                self.child_nodes.add(child)
            if self.manage_order_pos and child.order_pos == 0:
                child.order_pos = len(self.child_nodes) - 1
        else:
            if child.is_hidden:
                self.child_sprites_hidden.add(child)
            else:
                self.child_sprites.add(child)
        # Notify child that it has been assigned and should setup itself properly.
        child.on_node_added(node=self, display=self.display, hard=hard)
        # Notify display to rebuild DL.
        if self.display:
            self.display.on_node_child_added(self)

    # @time
    def add_children(self, children):
        nodes = filter(lambda item: isinstance(item, Node), children)
        sprites = filter(lambda item: isinstance(item, Sprite), children)

        # Begin: Nodes
        child_nodes_type = type(self.child_nodes)
        to_be_hidden = child_nodes_type(filter(lambda child: child.is_hidden, nodes))
        to_be_shown = child_nodes_type(filter(lambda child: not child.is_hidden, nodes))

        self.child_nodes_hidden |= to_be_hidden
        self.child_nodes |= to_be_shown

        # Notify children that they have been assigned and should setup themself properly.
        [child.on_node_added(node=self, display=self.display) for child in to_be_hidden]
        [child.on_node_added(node=self, display=self.display) for child in to_be_shown]
        # End: Nodes

        # Begin: Sprites
        to_be_hidden = set(filter(lambda child: child.is_hidden, sprites))
        to_be_shown = set(filter(lambda child: not child.is_hidden, sprites))

        self.child_sprites_hidden |= to_be_hidden
        self.child_sprites |= to_be_shown

        # Notify children that they have been assigned and should setup themself properly.
        # TODO do we need this order_pos thingy?
        # order_pos = len(self.child_nodes) - 1
        for child in to_be_hidden:
            # if self.manage_order_pos and child.order_pos == 0:
            #     child.order_pos = order_pos
            child.on_node_added(node=self, display=self.display)
            # order_pos += 1
        for child in to_be_shown:
            # if self.manage_order_pos and child.order_pos == 0:
            #     child.order_pos = order_pos
            child.on_node_added(node=self, display=self.display)
            # order_pos += 1
        # End: Sprites

        # Notify display to rebuild DL.
        if self.display:
            self.display.on_node_children_added(nodes + sprites)
        self.cached_representation_dirty = True

    # @dump_args
    def remove_all(self, cascade=True):
        if cascade:
            for child in chain(self.child_nodes, self.child_nodes_hidden):
                child.remove_all(True)
                child.on_node_removed(node=self)
        for child in chain(self.child_sprites, self.child_sprites_hidden):
            # Notify child that it has been unassigned and should setup itself properly.
            child.on_node_removed(node=self)
        if self.display:
            self.display.on_node_children_removed(chain(self.child_sprites, self.child_sprites_hidden, self.child_nodes, self.child_nodes_hidden))
        self.child_sprites.clear()
        self.child_sprites_hidden.clear()
        self.child_nodes.clear()
        self.child_nodes_hidden.clear()
        self.set_cached_tree_is_dirty()

    # @time
    def remove(self, child, cascade=False, hard=True):
        if isinstance(child, Node):
            if child.is_hidden:
                self.child_nodes_hidden.discard(child)
            else:
                self.child_nodes.discard(child)
            if cascade:
                child.remove_all(True)
        else:
            if child.is_hidden:
                self.child_sprites_hidden.discard(child)
            else:
                self.child_sprites.discard(child)
        # Notify child that it has been unassigned and should setup itself properly.
        child.on_node_removed(node=self, hard=hard)
        # self.display.on_node_child_removed(child)  # TODO isn't this obsolete due to child.on_node_removed()?
        self.set_cached_tree_is_dirty()

    # @time
    def remove_children(self, children, cascade=False):
        nodes = filter(lambda item: isinstance(item, Node), children)
        sprites = filter(lambda item: isinstance(item, Sprite), children)

        # Begin: Nodes
        hidden = filter(lambda child: child.is_hidden, nodes)
        shown = filter(lambda child: not child.is_hidden, nodes)

        [self.child_nodes_hidden.discard(child) for child in hidden]
        [self.child_nodes.discard(child) for child in shown]

        # Notify children that they have been unassigned and should teardown themself properly.
        [child.on_node_removed(node=self) for child in hidden]
        [child.on_node_removed(node=self) for child in shown]
        # End: Nodes

        # Begin: Sprites
        hidden = filter(lambda child: child.is_hidden, sprites)
        shown = filter(lambda child: not child.is_hidden, sprites)

        [self.child_sprites_hidden.discard(child) for child in hidden]
        [self.child_sprites.discard(child) for child in shown]

        # Notify children that they have been assigned and should setup themself properly.
        [child.on_node_removed(node=self) for child in hidden]
        [child.on_node_removed(node=self) for child in shown]
        # End: Sprites

        # Notify display to rebuild DL.
        if self.display:
            self.display.on_node_children_removed(shown)

    def remove_from_parent(self, cascade=True):
        self.parent_node.remove(self, cascade)

    # @time
    def add_to(self, parent):
        '''Convenience function.'''
        parent.add(self)

    def translate_pos(self, pos, other_node):
        # TODO BUG returns strange(?) values when using expand_in_fullscreen.
        o_x, o_y = pos
        o_xn, o_yn = self.get_real_pos_in_tree()
        n_xn, n_yn = other_node.get_real_pos_in_tree()
        # print 'o =', o_xn, o_yn
        # print 'n =', n_xn, n_yn
        x = o_xn - n_xn + o_x
        y = o_yn - n_yn + o_y
        return x, y

    def get_child_nodes(self):
        return self.child_nodes.copy()

    def get_hidden_child_nodes(self):
        return self.child_nodes_hidden.copy()

    def get_child_sprites(self):
        return self.child_sprites.copy()

    def get_hidden_child_sprites(self):
        return self.child_sprites_hidden.copy()

    def get_all_nodes(self):
        return self.child_nodes | self.child_nodes_hidden

    def get_all_sprites(self):
        return self.child_sprites | self.child_sprites_hidden

    def get_children(self):
        return self.child_nodes | self.child_nodes_hidden | self.child_sprites | self.child_sprites_hidden

    def get_ancestor_nodes(self):
        nodes = [self]
        if self.parent_node:
            nodes += self.parent_node.get_ancestor_nodes()
        return nodes

    def get_inherited_rgba(self):
        # print 'get_inherited_rgba:', self, self.rgba
        r1, g1, b1, a1 = self.rgba
        # print 'me', self, r1, g1, b1, a1
        try:
            r2, g2, b2, a2 = self.parent_node.rgba_inherited
            # print 'parent', self.parent_node, r2, g2, b2, a2
            return r1 * r2, g1 * g2, b1 * b2, a1 * a2
        except AttributeError:
            return r1, g1, b1, a1

    def update_inherited_rgba(self):
        self.rgba_inherited = self.get_inherited_rgba()
        for node in self.child_nodes:
            node.update_inherited_rgba()
        for sprite in self.child_sprites:
            sprite.update_inherited_rgba()
        self._add_to_update_list()

    def set_alpha(self, alpha):
        r, g, b, a = self.rgba
        alpha = max(0.0, min(1.0, alpha / 100.0))
        if a != alpha:
            self.rgba = r, g, b, alpha
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
            self.update_inherited_rgba()

    def get_tint(self):
        return self.rgba[:3]

    def get_inherited_gamma(self):
        # print 'get_inherited_gamma:', self, self.gamma
        g1 = self.gamma
        # print 'me', self, g1
        try:
            g2 = self.parent_node.gamma_inherited
            # print 'parent', self.parent_node, g2
            return g1 * g2
        except AttributeError:
            return g1

    def update_inherited_gamma(self):
        self.gamma_inherited = self.get_inherited_gamma()
        for node in self.child_nodes:
            node.update_inherited_gamma()
        for sprite in self.child_sprites:
            sprite.update_inherited_gamma()
        self._add_to_update_list()

    def set_gamma(self, value):
        value = max(0.0, min(2.0, value / 100.0))
        if self.gamma != value:
            self.gamma = value
            self.update_inherited_gamma()

    def get_gamma(self):
        return self.gamma * 100

    # TODO rework for using simple path system?
    def find_node(self, name):
        for item in chain(self.child_nodes, self.child_nodes_hidden):
            if item.name == name:
                return item
        return None

    # @dump_args
    def on_child_hidden(self, child):
        if not isinstance(child, Node):
            self.child_sprites.discard(child)
            self.child_sprites_hidden.add(child)
        else:
            self.child_nodes.discard(child)
            self.child_nodes_hidden.add(child)
        if self.display:
            self.display.on_node_child_hidden(child)

    # @dump_args
    def on_child_shown(self, child):
        if not isinstance(child, Node):
            self.child_sprites_hidden.discard(child)
            self.child_sprites.add(child)
            self.child_sprites_need_reorder = True if self.order_matters else self.child_sprites_need_reorder
        else:
            self.child_nodes_hidden.discard(child)
            self.child_nodes.add(child)
            self.child_nodes_need_reorder = True if self.order_matters else self.child_nodes_need_reorder
            self.set_cached_tree_is_dirty()
        child.update_inherited_rgba()
        child.update_inherited_gamma()
        if self.display:
            self.display.on_node_child_shown(child)

    def hide(self):
        self.is_hidden = True
        if self.parent_node:
            self.parent_node.on_child_hidden(self)

    def show(self):
        self.is_hidden = False
        if self.parent_node:
            self.parent_node.on_child_shown(self)

    # @time
    def hide_children(self, children):
        nodes = filter(lambda item: isinstance(item, Node), children)
        sprites = filter(lambda item: isinstance(item, Sprite), children)
        # print len(nodes)
        # print len(sprites)

        child_nodes_remove = self.child_nodes.discard
        child_sprites_remove = self.child_sprites.discard
        for child in nodes:
            child.is_hidden = True
        [child_nodes_remove(child) for child in nodes]
        self.child_nodes_hidden.update(nodes)

        for child in sprites:
            child.is_hidden = True
        [child_sprites_remove(child) for child in sprites]
        self.child_sprites_hidden.update(sprites)

        if self.display and sprites:
            self.display.on_node_children_hidden(sprites)

    def hide_all_children(self):
        children = self.child_nodes | self.child_sprites
        if children:
            self.hide_children(children)

    # @time
    def show_children(self, children):
        nodes = filter(lambda item: isinstance(item, Node), children)
        sprites = filter(lambda item: isinstance(item, Sprite), children)
        # print len(nodes)
        # print len(sprites)

        child_nodes_hidden_remove = self.child_nodes_hidden.discard
        child_sprites_hidden_remove = self.child_sprites_hidden.discard
        for child in nodes:
            child.is_hidden = False
            child.update_inherited_rgba()
            child.update_inherited_gamma()
        [child_nodes_hidden_remove(child) for child in nodes]
        self.child_nodes.update(nodes)

        for child in sprites:
            child.is_hidden = False
            child.pos_is_dirty = True
            child.is_dirty = True
            child.update_inherited_rgba()
            child.update_inherited_gamma()
            child.recalc_real_pos(recursive=True)
        [child_sprites_hidden_remove(child) for child in sprites]
        self.child_sprites.update(sprites)
        self.child_sprites_need_reorder = True if self.order_matters else self.child_sprites_need_reorder

        if self.display:
            self.display.on_node_children_shown(nodes + sprites)

    def show_all_children(self):
        children = self.child_nodes_hidden | self.child_sprites_hidden
        if children:
            self.show_children(children)

    def get_node_tree_as_list(self):
        nodes = self.child_nodes
        items = nodes.union(*[child.get_node_tree_as_list() for child in nodes])
        items.add(self)
        return items

    def __node_cmp_key(self, item):
        return int('%d%08d' % (item.order_pos, 10000000 + item.pos[1]))

    def __sprite_cmp_key(self, item):
        return int('%d%08d' % (item.order_pos, 10000000 + item.pos[1]))

    # @time
    def get_tree_as_list(self):
        child_nodes_type = type(self.child_nodes)
        if self.child_nodes_need_reorder:
            # print self, 'nodes', len(self.child_nodes)
            # print 'reorder %d nodes' % len(self.child_nodes)
            # Order nodes by grouping them by order_pos.
            self.child_nodes = child_nodes_type(sorted(self.child_nodes, key=self.__node_cmp_key, reverse=False))
            self.child_nodes_need_reorder = False
            self.cached_tree_dirty = True
        if self.child_sprites_need_reorder:
            # print self, 'sprites', len(self.child_sprites)
            # print 'reorder %d sprites' % len(self.child_sprites)
            # Order sprites by grouping them by order_pos.
            self.child_sprites = child_nodes_type(sorted(self.child_sprites, key=self.__sprite_cmp_key, reverse=False))
            self.child_sprites_need_reorder = False
            self.cached_tree_dirty = True
        if self.cached_representation is True:
            self._create_cached_representation()
        if self.cached_representation_sprite_list:
            items = [self.cached_representation_sprite_list]
        else:
            items = [self.child_sprites]
        if self.cached_tree_dirty:
            # print self
            # self.cached_tree = chain.from_iterable(child.get_tree_as_list() for child in self.child_nodes)
            self.cached_tree = list(chain.from_iterable(child.get_tree_as_list() for child in self.child_nodes))
            self.cached_tree_dirty = False
        items.extend(self.cached_tree)
        return items

    def set_cached_tree_is_dirty(self):
        if self.parent_node is not None:
            # self.parent_node.cached_tree_dirty = True
            self.parent_node.set_cached_tree_is_dirty()
        self.cached_tree_dirty = True

    def get_real_pos_in_tree(self):
        if self.parent_node:
            px, py = self.parent_node.get_real_pos_in_tree()
        else:
            px, py = 0, 0
        mx, my = self.pos_real
        return px + mx, py + my

    # @time
    def _update_real_pos_in_tree(self):
        new_pos = self.get_real_pos_in_tree()
        if new_pos != self.pos_real_in_tree:
            try:
                y_changed = self.pos_real_in_tree[1] != new_pos[1]
            except TypeError:
                y_changed = True
            self.pos_real_in_tree = new_pos
            # print self, self.order_matters
            try:
                if self.order_matters and y_changed:
                    self.display.display_list_dirty = True
                else:
                    self.display.drawables_dirty = True
            except AttributeError:
                pass  # It might happen that we don't have a display yet.
            if self.parent_node:  # and self.parent_node.order_matters:
                if y_changed:
                    self.parent_node.child_nodes_need_reorder = True
                    self.set_cached_tree_is_dirty()
            # Only update children which are not hidden!
            [child.update_real_pos_in_tree() for child in self.child_nodes]
            # Avoid function calls by not calling the childs method.
            # Keep in sync with Sprite._recalc_real_pos_in_tree !
            # [child._recalc_real_pos_in_tree() for child in self.child_sprites]
            for child in self.child_sprites:
                try:
                    px, py = self.pos_real_in_tree
                    ix, iy = child.pos_real
                    child.pos_real_in_tree = (px + ix, py + iy)
                except TypeError:
                    pass
            # if self.order_matters:
            #     self.child_sprites_need_reorder = True
            if self.track_movement:
                event.emit('node.moved', self)
            return True
        return False

    def update_real_pos_in_tree(self):
        self.pos_real_is_dirty = True
        # self._update_real_pos_in_tree()
        self._add_to_update_list()

    # @time
    def _recalc_real_pos(self):
        old_pos = self.pos_real
        new_pos = (self.pos[0] - self.hotspot[0], self.pos[1] - self.hotspot[1])
        if new_pos != old_pos:
            self.pos_real = new_pos
            self.update_real_pos_in_tree()

    def recalc_real_pos(self):
        self.pos_is_dirty = True
        # self._recalc_real_pos()
        self._add_to_update_list()

    # @time
    def set_pos(self, x, y):
        self.pos = x, y
        self.recalc_real_pos()

    # @time
    def set_pos_rel(self, rx, ry):
        self.pos = self.pos[0] + rx, self.pos[1] + ry
        self.recalc_real_pos()

    # @time
    def set_order_pos(self, z):
        self.order_pos = z
        self.recalc_real_pos()

    # @time
    def attach_to_display(self, display=None):
        if display is not None:
            self.display = display
        for child in chain(self.child_sprites, self.child_sprites_hidden, self.child_nodes, self.child_nodes_hidden):
            child.attach_to_display(display=display)
        self.display.on_node_child_added(self)
        self._add_to_update_list()
        event.emit('node.attached', self)

    # @time
    def detach_from_display(self):
        for child in chain(self.child_sprites, self.child_sprites_hidden, self.child_nodes, self.child_nodes_hidden):
            child.detach_from_display()
        self.display.on_node_child_removed(self)
        self._remove_from_update_list()
        event.emit('node.detached', self)

    # @time
    def get_rect(self, exclude_hidden=True):
        '''
        Returns a combined pygame.Rect with the real pos and size of itself
        and all its children.
        '''
        if exclude_hidden:
            children = chain(self.child_nodes, self.child_sprites)
        else:
            children = chain(self.child_nodes, self.child_nodes_hidden, self.child_sprites, self.child_sprites_hidden)
        if self.pos_real_in_tree is None:
            self._recalc_real_pos()
        rect = pygame.Rect(self.pos_real_in_tree[0], self.pos_real_in_tree[1], 0, 0)
        rects = [child.get_rect(exclude_hidden=exclude_hidden) for child in children]
        # print len(rects)
        rect.unionall_ip(rects)
        return rect

    def __del__(self):
        # print 'Node.__del__(%s)' % self
        pass

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

    # @time
    def _create_cached_representation(self):
        # TODO exclude animated sprites.
        # Gather range of child sprites.
        # print(self.child_sprites, len(self.child_sprites), self.child_sprites_hidden)
        # if not len(self.child_sprites) and not len(self.child_sprites_hidden):
        #     return
        get_rect = lambda child: pygame.Rect(
            child.pos[0], child.pos[1],
            child.size[0], child.size[1],
        )
        rects = [get_rect(child) for child in self.child_sprites]
        # print(rects)
        skip_sprites = False
        if rects:
            rect = rects[0]
            rect.unionall_ip(rects)
        else:
            rect = pygame.Rect(0, 0, 1, 1)
            skip_sprites = True
        # print(rect)

        # Create surface to draw on.
        # image = pygame.Surface((rect.w, rect.h), pygame.locals.SRCALPHA).convert_alpha()
        vault = GeneratedVault()
        image = vault.generate_surface(*rect.size)
        image.fill((0, 0, 0, 0))
        # image.fill((255, 255, 255, 128))

        repr_list = []

        if not skip_sprites:
            # Draw sprites on surface.
            for child in self.child_sprites:
                if not child.is_cacheable:
                    repr_list.append(child)
                    continue
                child.is_drawable = False
                # Skip empty or uninitialized sprites.
                if child.size == (0, 0):
                    continue
                # print(child, child.frame)
                frame = child.frame
                gamma = str(frame['current_gamma'])
                surface = frame['surfaces'][gamma]
                pos = child.pos[0] - rect.x, child.pos[1] - rect.y
                # print(surface, pos)
                image.blit(surface, pos, surface.get_rect())
            for child in self.child_sprites_hidden:
                child.is_drawable = False
        else:
            for child in chain(self.child_sprites, self.child_sprites_hidden):
                if not child.is_cacheable:
                    repr_list.append(child)
                    continue
                child.is_drawable = False

        # Generate final sprite.
        sprite = vault.add_sprite('cached node')
        action = sprite.add_action('none')
        action.add_frame((0, 0, rect.w, rect.h), (0, 0), (0, 0))
        sprite = Sprite.make(vault)

        # Set it up.
        sprite.pos = (rect.x, rect.y)
        sprite.add_to(self)

        # And save it.
        repr_list.append(sprite)
        self.cached_representation = sprite
        self.cached_representation_dirty = False
        list_type = type(self.cached_representation_sprite_list)
        self.cached_representation_sprite_list = list_type(repr_list)
        self.set_cached_tree_is_dirty()

    # @time
    def _rebuild_cached_representation(self):
        if type(self.cached_representation) is not Sprite:
            return

        self.remove(self.cached_representation)
        self._create_cached_representation()
        self.cached_representation.update()

    def update(self):
        if self.parent_node is None:
            return
        if self.cached_representation is True:
            self._create_cached_representation()
        elif self.cached_representation_dirty:
            if self.cached_representation is not None:
                self._rebuild_cached_representation()
            else:
                self.cached_representation_dirty = False
        if self.pos_is_dirty:
            self._recalc_real_pos()
            self.pos_is_dirty = False
        if self.pos_real_is_dirty:
            self._update_real_pos_in_tree()
