# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

from diamond import pyglet
from diamond import event
from diamond.decorators import time


class ClipGroup(pyglet.graphics.OrderedGroup):
    """Sprite group that clips to a rectangle."""

    def __init__(self, order=0, parent=None, x=0, y=0, w=0, h=0):
        super(ClipGroup, self).__init__(order=order, parent=parent)
        self.x, self.y, self.w, self.h = x, y, w, h
        # Some kind of weird ctypes issue here, need to re-cast.
        self.x, self.y, self.w, self.h = [int(i) for i in (self.x, self.y, self.w, self.h)]

    def set_state(self):
        pyglet.gl.glScissor(int(self.x), int(self.y), int(self.w), int(self.h))
        pyglet.gl.glEnable(pyglet.gl.GL_SCISSOR_TEST)

    def unset_state(self):
        pyglet.gl.glDisable(pyglet.gl.GL_SCISSOR_TEST)


class PositionalGroup(pyglet.graphics.OrderedGroup):
    """Sprite group that also moves the children to some specific offset."""

    def __init__(self, order=0, parent=None):
        super(PositionalGroup, self).__init__(order=order, parent=parent)
        self.x, self.y = 0, 0

    def set_state(self):
        pyglet.gl.glTranslated(self.x, self.y, 0)

    def unset_state(self):
        pyglet.gl.glTranslated(-self.x, -self.y, 0)


class Node(object):

    def __init__(self, name=None):
        super(Node, self).__init__()
        self._name = name or '<%s>' % (type(self).__name__)
        self._x, self._y = 0, 0
        # self._x_real, self._y_real = 0, 0
        self._window = None
        self._child_nodes = []
        self._child_sprites = []
        self._order_id = 0
        self._group = PositionalGroup(0)
        self._parent_node = None
        self._visible = True
        self._inherited_visibility = True

    def __repr__(self):
        pos = '%d,%d' % (self._x, self._y)
        # try:
        #     pos_real_in_tree = ' => %d,%dr' % (self._x_real, self._y_real)
        # except TypeError:
        #     pos_real_in_tree = ''
        pos_real_in_tree = ''
        if self._name:
            name = 'Node(%s[%d]@%sv%s)' % (self._name, self._order_id, pos, pos_real_in_tree)
        else:
            name = 'Node([%d]@%sv%s)' % (self._order_id, pos, pos_real_in_tree)
        # if self.parent_node:
        #     return '%s -> %s' % (self._parent_node, name)
        # else:
        #     return name
        return name

    # @time
    def _update_real_position(self):
        self._group.x = self._x
        self._group.y = self._y
    #     try:
    #         self._x_real = self._parent_node._x_real + self._x
    #         self._y_real = self._parent_node._y_real + self._y
    #     except AttributeError:
    #         self._x_real = self._x
    #         self._y_real = self._y
    #     # [sprite._update_real_position() for sprite in self._child_sprites]
    #     [node._update_real_position() for node in self._child_nodes]

    def _set_x(self, x):
        if x != self._x:
            self._x = x
            self._update_real_position()

    x = property(lambda self: self._x, _set_x)

    def _set_y(self, y):
        if y != self._y:
            self._y = y
            self._update_real_position()

    y = property(lambda self: self._y, _set_y)

    def set_position(self, x, y):
        if (x, y) != (self._x, self._y):
            self._x, self._y = x, y
            self._update_real_position()

    position = property(lambda self: (self._x, self._y),
                        lambda self, pos: self.set_position(*pos))

    def _get_real_position(self):
        x, y = self._x, self._y
        if self._parent_node:
            x2, y2 = self._parent_node._get_real_position()
            x += x2
            y += y2
        return x, y

    real_position = property(_get_real_position)

    def set_position_relative(self, r_x, r_y):
        self._x += r_x
        self._y += r_y
        self._update_real_position()

    # @time
    def _update_group_order(self):
        self._group.order = int('%s%05d' % (self._parent_node._order_id, self._order_id))
        # self._group.order = self._order_id
        # print self, self._group.order

    # @time
    def _set_order_id(self, id):
        self._order_id = id
        if self._parent_node:
            self._update_group_order()

    order_id = property(lambda self: self._order_id, _set_order_id)

    def _update_inherited_visibility(self):
        try:
            self._inherited_visibility = self._visible and self._parent_node._inherited_visibility
        except AttributeError:
            self._inherited_visibility = self._visible
        [sprite._update_inherited_visibility() for sprite in self._child_sprites]
        [node._update_inherited_visibility() for node in self._child_nodes]

    def _set_visible(self, visible):
        self._visible = visible
        self._update_inherited_visibility()

    visible = property(lambda self: self._visible, _set_visible)

    def hide(self):
        if self._visible:
            self._set_visible(False)

    def show(self):
        if not self._visible:
            self._set_visible(True)

    # @time
    def _set_window(self, window):
        self._window = window
        batch = window._batch
        for sprite in self._child_sprites:
            sprite.batch = batch
            # print self, 'SET BATCH OF SPRITE', sprite, 'TO', batch
        [node._set_window(window) for node in self._child_nodes]
        if window:
            event.emit('node.attached', self)
        else:
            event.emit('node.detached', self)

    window = property(lambda self: self._window, _set_window)

    # @time
    def add_node(self, node):
        if node._parent_node:
            node.remove_from_parent()
        self._child_nodes.append(node)
        node._parent_node = self
        if self._window:
            node._set_window(self._window)
        # print 'ORDER ID =', node.order_id
        if node.order_id is None:
            node.order_id = len(self._child_nodes)
        node._group.parent = self._group
        node._update_inherited_visibility()
        node._update_real_position()
        node._update_group_order()

    # @time
    def add_nodes(self, nodes):
        order_id = len(self._child_nodes)
        self._child_nodes.extend(nodes)
        for node in nodes:
            if node._parent_node:
                node._parent_node.remove_node(node)
            node._parent_node = self
            node._set_window(self._window)
            if node.order_id is None:
                node.order_id = order_id
            order_id += 1
            node._group.parent = self._group
            node._update_inherited_visibility()
            node._update_real_position()
            node._update_group_order()

    # @time
    def add_sprite(self, sprite):
        if sprite._parent_node:
            sprite._parent_node.remove_sprite(sprite)
        self._child_sprites.append(sprite)
        try:
            sprite.batch = self._window._batch
            # print 'ADDED SPRITE TO BATCH'
        except AttributeError:
            pass
        sprite.group = self._group
        sprite._parent_node = self
        # sprite._update_real_position()
        sprite._update_inherited_visibility()

    # @time
    def add_sprites(self, sprites):
        for sprite in sprites:
            if sprite._parent_node:
                sprite.remove_from_parent()
            sprite.group = self._group
            try:
                sprite.batch = self._window._batch
                # print 'ADDED ONE OF MANY SPRITES TO BATCH'
            except AttributeError:
                pass
            # sprite._update_real_position()
            sprite._update_inherited_visibility()
        self._child_sprites.extend(sprites)

    def add_to(self, node):
        node.add_node(self)

    def remove_all(self):
        for node in self._child_nodes:
            node.remove_all()
        for sprite in self._child_sprites:
            sprite._parent_node = None
            sprite.group = None
            sprite.batch = None            
        del self._child_sprites[:]
        del self._child_nodes[:]

    def remove_from_parent(self):
        self._parent_node.remove_node(self)

    def remove_node(self, node):
        self._child_nodes.remove(node)
        node._parent_node = None
        node._group.parent = None

    def remove_sprite(self, sprite):
        self._child_sprites.remove(sprite)
        sprite._parent_node = None
        sprite.group = None
        sprite.batch = None
