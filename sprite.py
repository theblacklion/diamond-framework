# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)


from diamond import pyglet
from diamond.vault import Vault


class Sprite(pyglet.sprite.Sprite):

    def __init__(self, vault, parent_node=None, position=None, name=None, usage='dynamic'):
        self._vault = vault
        self._name = name
        self._action = 'none'
        self._parent_node = parent_node
        self._my_visibility = True
        if parent_node:
            parent_node._child_sprites.append(self)
            group = parent_node._sprite_group
            try:
                batch = parent_node.window._batch
            except AttributeError:
                batch = None
        else:
            batch, group = None, None
        # if position:
        #     self._x_rel, self._y_rel = position
        # else:
        #     self._x_rel, self._y_rel = 0, 0
        self._anim = vault.actions[self._action].animation
        # self._update_real_position()
        x, y = position if position is not None else (0, 0)
        super(Sprite, self).__init__(
            img=self._anim,
            # x=self._x,
            # y=self._y,
            x=x,
            y=y,
            batch=batch,
            group=group,
            usage=usage,
        )

    # def _update_real_position(self):
    #     if self._parent_node:
    #         self._x = self._parent_node._x_real + self._x_rel
    #         self._y = self._parent_node._y_real + self._y_rel
    #     else:
    #         self._x = self._x_rel
    #         self._y = self._y_rel
    #     self._x = self._x_rel
    #     self._y = self._y_rel
    #     if self._vertex_list:
    #         self._update_position()

    # def _set_x(self, x):
    #     if x != self._x_rel:
    #         self._x_rel = x
    #         self._update_real_position()

    # x = property(lambda self: self._x_rel, _set_x)

    # def _set_y(self, y):
    #     if y != self._y_rel:
    #         self._y_rel = y
    #         self._update_real_position()

    # y = property(lambda self: self._y_rel, _set_y)
    
    # def set_position(self, x, y):
    #     self._x_rel, self._y_rel = x, y
    #     self._update_real_position()

    # position = property(lambda self: (self._x_rel, self._y_rel),
    #                     lambda self, pos: self.set_position(*pos))

    def _update_inherited_visibility(self):
        self._visible = self._parent_node._inherited_visibility

    def _set_visible(self, visible):
        self._my_visibility = visible
        self._update_inherited_visibility()
        self._update_position()

    visible = property(lambda self: self._visible, _set_visible)

    def set_action(self, name):
        if name != self._action:
            self._action = name
            self._anim = self._vault.actions[name].animation
            self.image = self._anim

    action = property(lambda self: self._action, set_action)

    @classmethod
    def make(cls, vault_module, sprite_name=None, **kwargs):
        '''Factory which creates a vault and returns a proper Sprite object.'''
        if not isinstance(vault_module, Vault):
            vault = Vault.get_instance(vault_module)
        else:
            vault = vault_module
        if sprite_name is not None:
            vault = vault.get_sprite(str(sprite_name))
        else:
            vault = vault.get_sprites().values()[0]
        return cls(vault=vault, **kwargs)

    @classmethod
    def make_many(cls, vault_module, sprite_name=None, amount=1, **kwargs):
        '''Factory which creates a vault and returns x Sprite objects within a list.'''
        if not isinstance(vault_module, Vault):
            vault = Vault.get_instance(vault_module)
        else:
            vault = vault_module
        if sprite_name is not None:
            vault = vault.get_sprite(sprite_name)
        else:
            vault = vault.get_sprites().values()[0]
        return [cls(vault=vault, **kwargs) for count in xrange(0, amount)]

    def add_to(self, node):
        node.add_sprite(self)

    def remove_from_parent(self):
        self._parent_node.remove_sprite(self)
