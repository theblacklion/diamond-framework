# Camera class which moves the scene around to keep the target in the center.
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

from diamond.node import Node
from diamond.scene import Scene


class Camera(object):

    def __init__(self, scene, target):
        assert isinstance(scene, Node)
        assert isinstance(target, Scene)
        self.scene = scene
        self.target = target

    def tick(self):
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
