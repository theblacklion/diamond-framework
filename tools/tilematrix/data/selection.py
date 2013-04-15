from collections import OrderedDict

import pygame

from diamond.sprite import SpritePrimitives


class Selection(object):

    def __init__(self, root_node):
        self.root_node = root_node
        self.selection = OrderedDict()
        self.tilematrix_z = 999
        self.alias2matrix = {}
        self.selection_rect = pygame.Rect(0, 0, 0, 0)
        self.skip_empty_tiles = True

    def add_tilematrix(self, tilematrix):
        t_w, t_h = tilematrix.get_tile_size()
        selection_box = SpritePrimitives.make_rectangle(t_w + 2, t_h + 2, color=(255, 255, 255, 192), background=(255, 255, 255, 96), hotspot=(1, 1))
        selection_vault = selection_box.vault.get_vault()
        tilematrix.load_vault(selection_vault, 'selection')
        self.selection[tilematrix.name] = OrderedDict()
        self.alias2matrix[tilematrix.name] = tilematrix

    def __translate_pos(self, tilematrix, pos):
        # Translate pos to possible tile.
        x, y = self.root_node.translate_pos(pos, tilematrix)
        pos = tilematrix.translate_to_matrix(x, y)
        # print pos
        return pos

    def remove_selection(self, alias, points, translate_pos=False):
        selection = self.selection[alias]
        tilematrix = self.alias2matrix[alias]
        z = self.tilematrix_z

        for pos in points:
            if translate_pos:
                pos = self.__translate_pos(tilematrix, pos)
            x, y = pos
            tilematrix.set_tile_at(x, y, z, None)
            del selection[pos]

    def add_selection(self, alias, points, translate_pos=False):
        selection = self.selection[alias]
        tilematrix = self.alias2matrix[alias]
        z = self.tilematrix_z

        for x, y in points:
            if translate_pos:
                x, y = self.__translate_pos(tilematrix, (x, y))
            id = tilematrix.get_tile_id_at(x, y)
            # print 'ids =', id
            if self.skip_empty_tiles and not id:
                continue
            tilematrix.set_tile_at(x, y, z, 'selection/default')
            if z in id:
                del id[z]
            selection[(x, y)] = id

    def set_selection(self, alias, points, translate_pos=False):
        selection = self.selection[alias]
        tilematrix = self.alias2matrix[alias]
        t_w, t_h = tilematrix.get_tile_size()

        if translate_pos:
            points = [self.__translate_pos(tilematrix, pos) for pos in points]
        points = set(points)

        # Clear present selection.
        if selection:
            obsolete = set(selection.iterkeys()) - points
            self.remove_selection(alias, obsolete)

        # Create new selection.
        self.add_selection(alias, points)

    def get_selection(self, alias, sort=False):
        selection = self.selection[alias]
        if sort:
            selection = OrderedDict(sorted(
                selection.iterkeys(),
                key=lambda point: '%08d,%08d' % tuple(reversed(point))
            ))
        else:
            selection = selection.copy()
        return selection

    def __update_selection_rect(self, tilematrix):
        rect = self.selection_rect
        x, y, w, h = rect.x, rect.y, rect.w, rect.h

        copy = rect.copy()
        copy.normalize()
        # print 'copy =', copy, copy.topleft, copy.bottomright
        x, y, w, h = copy.x, copy.y, copy.w, copy.h

        range_x = xrange(x, x + w + 1, 1)
        range_y = xrange(y, y + h + 1, 1)

        points = []
        for y in range_y:
            for x in range_x:
                points.append((x, y))

        # print points

        self.set_selection(tilematrix.name, points)

    def begin_selection(self, alias, pos, translate_pos=False):
        tilematrix = self.alias2matrix[alias]

        if translate_pos:
            pos = self.__translate_pos(tilematrix, pos)

        self.selection_rect = pygame.Rect(pos, (0, 0))
        self.__update_selection_rect(tilematrix)

    def end_selection(self, alias, pos, translate_pos=False):
        tilematrix = self.alias2matrix[alias]

        if translate_pos:
            pos = self.__translate_pos(tilematrix, pos)

        x1, y1 = self.selection_rect.topleft
        x2, y2 = pos
        # print (x1, y1), (x2, y2), (x2 - x1, y2 - y1)
        self.selection_rect.size = (x2 - x1, y2 - y1)
        self.__update_selection_rect(tilematrix)

    def clear_selection(self, alias):
        self.selection_rect = pygame.Rect(0, 0, 0, 0)
        self.set_selection(alias, [])
