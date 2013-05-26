# Camera class which moves the scene around to keep the target in the center.
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

import pygame

from diamond.node import Node
from diamond.scene import Scene


class Camera(object):

    def __init__(self, scene, target):
        assert isinstance(scene, Node)
        assert isinstance(target, Scene)
        self.scene = scene
        self.target = target

    def tick(self):
        # Back out if our pointer is not in our window.
        if not pygame.mouse.get_focused():
            return
        # First try to follow mouse pointer.
        screen_size = self.scene.display.screen_size
        pos = self.target._cursor_pos
        r_x, r_y = 0, 0
        edge_top = (screen_size[1] / 5)
        edge_bottom = screen_size[1] - (screen_size[1] / 5)
        edge_left = (screen_size[0] / 5)
        edge_right = screen_size[0] - (screen_size[0] / 5)
        if pos[1] < edge_top:
            r_y = (edge_top - pos[1]) / 10.0
        elif pos[1] > edge_bottom:
            r_y = (edge_bottom - pos[1]) / 10.0
        if pos[0] < edge_left:
            r_x = (edge_left - pos[0]) / 10.0
        elif pos[0] > edge_right:
            r_x = (edge_right - pos[0]) / 10.0
        if r_x or r_y:
            self.scene.set_pos_rel(int(r_x), int(r_y))
        else:
            return
        # Now keep used matrix in view.
        rect = self.scene.get_virtual_rect()
        pos = self.scene.pos
        r_x, r_y = 0, 0
        # print rect, pos
        edge_bottom = (screen_size[1] / 5)
        edge_top = screen_size[1] - (screen_size[1] / 5)
        edge_right = (screen_size[0] / 5)
        edge_left = screen_size[0] - (screen_size[0] / 5)
        if -pos[0] < rect.x - edge_left:
            r_x = (-pos[0] - (rect.x - edge_left))
        elif -pos[0] > rect.x + rect.w - edge_right:
            r_x = (-pos[0] - (rect.x + rect.w - edge_right))
        if -pos[1] < rect.y - edge_top:
            r_y = (-pos[1] - (rect.y - edge_top))
        elif -pos[1] > rect.y + rect.h:
            r_y = (-pos[1] - (rect.y + rect.h))
        if r_x or r_y:
            # print r_x, r_y
            self.scene.set_pos_rel(int(r_x), int(r_y))
