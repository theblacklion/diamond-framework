# TODO
# - What should happen when we load a sheet after creating/loading a map?
# - load_map() should fill up and truncate rows as necessary.
# - Handle situations where build_map builds maps of different sizes.

import os.path
import csv
from collections import deque
from math import ceil  #, floor

import pygame

from diamond.node import Node
from diamond.sprite import Sprite
from diamond.vault import Vault, GeneratedVault
from diamond import event
# from diamond.decorators import dump_args, time


class VaultPlaceholder(object):

    def __init__(self, name):
        super(VaultPlaceholder, self).__init__()
        self.name = name


class TilePlaceholder(object):

    def __init__(self, pos=(0, 0), is_hidden=False):
        super(TilePlaceholder, self).__init__()
        self.vault = VaultPlaceholder('-1')
        self.pos = pos
        self.is_hidden = is_hidden
        self.gamma = 1.0

    # def __del__(self):
    #     print 'TilePlaceholder.__del__(%s)' % self

    def show(self):
        self.is_hidden = False

    def hide(self):
        self.is_hidden = True

    def set_gamma(self, value):
        value = max(0.0, min(2.0, value / 100.0))
        self.gamma = value

    def get_gamma(self):
        return self.gamma * 100

    def set_pos(self, pos):
        self.pos = pos


class TileMap(Node):

    TILE_SPACER_ID = '-1'

    def __init__(self, name='TileMap'):
        super(TileMap, self).__init__(name=name)
        self.__sheet = None
        self.__vault = None
        self.__map = None
        self.__tile_size = 0, 0
        self.__map_size = 0, 0
        self.order_matters = False  # Speed up movements of tiles.
        self.__use_spacer = False
        self.__spacer_bin = set()
        # TODO implement step by step removal of spacers from bin (using ticker?).
        self.listeners = [
            event.add_listener(self.update_tile_visibility, 'node.moved',
                               instance__is=self),
            event.add_listener(self.update_tile_visibility, 'node.attached',
                               instance__is=self)
        ]
        self.__last_visibility_map_rect = None
        self.track_movement = True

    def __del__(self):
        event.remove_listeners(self.listeners)
        # super(TileMap, self).__del__()

    # @time
    def enable_spacer(self):
        if not self.__use_spacer:
            to_be_added = []
            to_be_added_append = to_be_added.append
            pop = self.__spacer_bin.pop
            make = Sprite.make
            for y, row in enumerate(self.__map):
                for x, col in enumerate(row):
                    if type(col) is TilePlaceholder:
                        try:
                            tile = pop()
                        except KeyError:
                            tile = make(self.__spacer_vault)
                        # tile.is_hidden = row[x].is_hidden
                        tile.is_hidden = not self.__last_visibility_map_rect.collidepoint(x, y)
                        tile.pos = col.pos
                        tile.gamma = col.gamma
                        to_be_added_append(tile)
                        row[x] = tile
            self.add_children(to_be_added)
        self.__use_spacer = True

    # @time
    def disable_spacer(self):
        if self.__use_spacer:
            to_be_removed = []
            to_be_removed_append = to_be_removed.append
            add = self.__spacer_bin.add
            make = TilePlaceholder
            for row in self.__map:
                for x, col in enumerate(row):
                    if type(col) is not TilePlaceholder and col.vault.name == TileMap.TILE_SPACER_ID:
                        add(col)
                        to_be_removed_append(col)
                        # tile = make(pos=col.pos, is_hidden=row[x].is_hidden)
                        is_hidden = not self.__last_visibility_map_rect.collidepoint(*col.pos)
                        tile = make(pos=col.pos, is_hidden=is_hidden)
                        tile.gamma = col.gamma
                        row[x] = tile
            self.remove_children(to_be_removed)
        self.__use_spacer = False

    def toggle_spacer(self):
        if self.__use_spacer:
            self.disable_spacer()
        else:
            self.enable_spacer()

    def is_spacer_enabled(self):
        return self.__use_spacer

    # @dump_args
    def get_rect(self, *args, **kwargs):
        '''
        Returns a combined pygame.Rect with the real pos and size of itself
        and all its children.
        Due to the fact that this is a tilemap we just calculate our size.
        '''
        if self.pos_real_in_tree is None:
            self.recalc_real_pos()
        rect = pygame.Rect(self.pos_real_in_tree[0], self.pos_real_in_tree[1], 0, 0)
        m_w, m_h = self.__map_size
        t_w, t_h = self.__tile_size
        rect.w = m_w * t_w
        rect.h = m_h * t_h
        return rect

    # @time
    def update_tile_visibility(self):
        if not self.display or not self.__map:
            return

        t_w, t_h = self.__tile_size
        # print 'tile size =', (t_w, t_h)
        n_x, n_y = self.pos_real_in_tree
        # print 'node pos real =', (n_x, n_y)
        view = self.display.get_rect()
        # print 'view =', view
        m_w, m_h = self.__map_size
        # print 'map size =', (m_w, m_h)

        # Calc current view rect on tile basis.
        v_x = ceil(n_x / float(t_w))
        v_y = ceil(n_y / float(t_h))
        v_w = ceil(view.w / float(t_w)) + 1
        v_h = ceil(view.h / float(t_h)) + 1
        v_rect = pygame.Rect(-v_x, -v_y, v_w, v_h)
        # print 'v_rect =', v_rect

        # Get last view rect.
        last_v_rect = self.__last_visibility_map_rect
        # print 'last_v_rect =', last_v_rect

        if last_v_rect is not None and v_rect == last_v_rect:
            # print 'nothing changed'
            return

        self.__last_visibility_map_rect = v_rect

        if m_w <= v_w and m_h <= v_h:
            _view_rect = pygame.Rect(0, 0, v_w, v_h)
            _map_rect = pygame.Rect(v_x, v_y, m_w, m_h)
            # print 'view rect =', _view_rect
            # print 'map rect =', _map_rect
            contains_current = _view_rect.contains(_map_rect)
            if last_v_rect is not None and contains_current and last_v_rect.x <= 0 and last_v_rect.y <= 0 and last_v_rect.x >= -(v_w - m_w) and last_v_rect.y >= -(v_h - m_h):
                # print 'map completely within view. nothing changed.'
                return

        tilemap = self.__map

        # Prepare ranges for faster looping.
        if last_v_rect is not None:
            x = max(0, last_v_rect.x)
            y = max(0, last_v_rect.y)
            last_range_x = range(x, min(last_v_rect.x + last_v_rect.w, m_w))
            last_range_y = range(y, min(last_v_rect.y + last_v_rect.h, m_h))
        else:
            last_range_x = last_range_y = []
        x = max(0, v_rect.x)
        y = max(0, v_rect.y)
        cur_range_x = range(x, min(v_rect.x + v_rect.w, m_w))
        cur_range_y = range(y, min(v_rect.y + v_rect.h, m_h))
        # print last_range_x
        # print last_range_y
        # print cur_range_x
        # print cur_range_y

        to_be_hidden = []
        to_be_hidden_append = to_be_hidden.append
        to_be_shown = []
        to_be_shown_append = to_be_shown.append

        # Do both rects overlap?
        if last_v_rect is not None and v_rect.colliderect(last_v_rect):
            # print 'both overlap'
            # print 'clear old rect minus overlapping'
            for y in last_range_y:
                for x in last_range_x:
                    if not v_rect.collidepoint(x, y):
                        to_be_hidden_append(tilemap[y][x])
            # print 'show new rect minus overlapping'
            for y in cur_range_y:
                for x in cur_range_x:
                    if not last_v_rect.collidepoint(x, y):
                        to_be_shown_append(tilemap[y][x])
            # print 'done'
        else:
            # print 'nothing overlaps'
            # print 'clear old rect'
            if last_v_rect is not None:
                for y in last_range_y:
                    for x in last_range_x:
                        to_be_hidden_append(tilemap[y][x])
            # print 'show new rect'
            for y in cur_range_y:
                for x in cur_range_x:
                    to_be_shown_append(tilemap[y][x])
            # print 'done'

        self.hide_children(to_be_hidden)
        self.show_children(to_be_shown)

    def _init_spacer_vault(self):
        width, height = self.__tile_size
        vault = GeneratedVault()
        surface = vault.generate_surface(width, height)
        surface.fill((255, 255, 255, 32), rect=(0, 0, width, height))
        surface.fill((192, 192, 192, 32), rect=(1, 1, width - 2, height - 2))
        surface.fill((255, 255, 255, 32), rect=(2, 2, width / 2 - 2, height / 2 - 2))
        surface.fill((255, 255, 255, 32), rect=(width / 2, height / 2, width / 2 - 2, height / 2 - 2))
        sprite = vault.add_sprite(TileMap.TILE_SPACER_ID)
        action = sprite.add_action('none')
        action.add_frame((0, 0, width, height))
        self.__spacer_vault = vault

    def load_sheet(self, sheet_vault):
        self.__sheet = sheet_vault
        self.__vault = Vault.get_instance(sheet_vault)
        self.__tile_size = sheet_vault.tile_size
        self._init_spacer_vault()

    def load_map_from_iterable(self, iterable):
        self.__map = tilemap = []
        for row in iterable:
            tilemap.append([col if col != TileMap.TILE_SPACER_ID else None for col in row])
        self.__map_size = len(tilemap[0]), len(tilemap)

    def load_map(self, filename):
        with open(filename) as fhandle:
            self.load_map_from_iterable(csv.reader(fhandle, skipinitialspace=True))

    def save_map(self, filename):
        tilemap = self.__map
        rows = [[self.get_tile_id(tile) for tile in row] for row in tilemap]
        with open(filename, 'wb') as fhandle:
            writer = csv.writer(fhandle)
            writer.writerows(rows)

    def create_map(self, map_width, map_height):
        self.__map = tilemap = []
        width, height = self.__tile_size
        for row_no in range(0, map_height):
            # row = [str(row_no * width + col_no) for col_no in range(0, map_width)]  # For testing.
            row = [None for col_no in range(0, map_width)]
            tilemap.append(row)
            # print row
        self.__map_size = len(tilemap[0] if tilemap else []), len(tilemap)

    # @time
    def build_map(self):
        # TODO Implement lazy spacer vault creation.
        width, height = self.__tile_size
        to_be_added = []
        to_be_hidden = []
        to_be_added_append = to_be_added.append
        to_be_hidden_append = to_be_hidden.append
        Sprite_make = Sprite.make
        for y, row in enumerate(self.__map):
            for x, col in enumerate(row):
                pos = x * width, y * height
                if type(col) is Sprite:
                    if col.pos != pos:
                        col.set_pos(*pos)
                    to_be_hidden_append(col)
                elif type(col) in (str, unicode, int):
                    tile = Sprite_make(self.__vault, col)
                    tile.pos = pos
                    tile.is_hidden = True
                    row[x] = tile
                    to_be_added_append(tile)
                elif col is None and self.__use_spacer is False:
                    tile = TilePlaceholder(pos=pos, is_hidden=True)
                    row[x] = tile
                elif col is None and self.__use_spacer is True:
                    tile = Sprite_make(self.__spacer_vault)
                    tile.pos = pos
                    tile.is_hidden = True
                    row[x] = tile
                    to_be_added_append(tile)
        self.add_children(to_be_added)
        self.hide_children(to_be_hidden)
        self.__map_size = (x + 1, y + 1)
        self.__last_visibility_map_rect = None
        self.update_tile_visibility()

    def get_vault(self):
        return self.__vault

    def get_sheet(self):
        return self.__sheet

    def get_tile_ids(self):
        return self.__vault.get_sprite_names()

    def get_tile_size(self):
        return self.__tile_size

    def get_map_size(self):
        return self.__map_size

    # @dump_args
    def set_map_size(self, width, height):
        self.__map_size = width, height

    def get_map(self):
        return self.__map

    def get_tile_at(self, x, y):
        if x < 0 or y < 0:
            return None
        try:
            return self.__map[y][x]
        except IndexError:
            return None

    def get_tile_id(self, tile):
        return tile.vault.name

    def get_tile_id_at(self, x, y):
        tile = self.get_tile_at(x, y)
        if tile is not None:
            return self.get_tile_id(tile)
        else:
            return None

    def set_tile_at(self, x, y, id):
        if x < 0 or y < 0 or x >= self.__map_size[0] or y >= self.__map_size[1]:
            return None

        tile = self.get_tile_at(x, y)

        # Detect whether the tile has already the same id.
        if self.get_tile_id(tile) == id:
            return

        tile_id = self.get_tile_id(tile)
        # print tile_id, '->', id

        if self.__use_spacer:
            if id != TileMap.TILE_SPACER_ID and tile_id == TileMap.TILE_SPACER_ID:
                # Change from spacer to normal tile.
                vault = self.__vault
            elif id != TileMap.TILE_SPACER_ID and tile_id != TileMap.TILE_SPACER_ID:
                # Change from normal tile to normal tile.
                vault = tile.vault.get_vault()
            elif id == TileMap.TILE_SPACER_ID and tile_id != TileMap.TILE_SPACER_ID:
                # Change from normal tile to spacer.
                vault = self.__spacer_vault

            tile.replace_vault(vault.get_sprite(id))
        else:
            if id != TileMap.TILE_SPACER_ID and tile_id == TileMap.TILE_SPACER_ID:
                # Change from spacer to normal tile.
                vault = self.__vault
                new_tile = Sprite.make(vault, id)
                # Only hide tile if not in view.
                if not self.__last_visibility_map_rect.collidepoint(x, y):
                    new_tile.hide()
                new_tile.pos = tile.pos
                new_tile.set_gamma(tile.get_gamma())
                new_tile.add_to(self)
                self.__map[y][x] = new_tile
            elif id != TileMap.TILE_SPACER_ID and tile_id != TileMap.TILE_SPACER_ID:
                # Change from normal tile to normal tile.
                vault = tile.vault.get_vault()
                tile.replace_vault(vault.get_sprite(id))
            elif id == TileMap.TILE_SPACER_ID and tile_id != TileMap.TILE_SPACER_ID:
                # Change from normal tile to spacer.
                tile.remove_from_parent()
                tile.detach_from_display()
                # Only hide tile if not in view.
                is_hidden = not self.__last_visibility_map_rect.collidepoint(x, y)
                new_tile = TilePlaceholder(pos=tile.pos, is_hidden=is_hidden)
                new_tile.set_gamma(tile.get_gamma())
                self.__map[y][x] = new_tile

    def get_tile_pos(self, tile):
        width, height = self.__tile_size
        x, y = tile.pos
        return x / width, y / height

    def set_tile_id_of(self, tile, tile_id):
        x, y = self.get_tile_pos(tile)
        self.set_tile_at(x, y, tile_id)

    def set_tile_ids_of(self, tiles, tile_id):
        get_tile_pos = self.get_tile_pos
        set_tile_at = self.set_tile_at
        for tile in tiles:
            x, y = get_tile_pos(tile)
            set_tile_at(x, y, tile_id)

    def find_all(self, tile, exclude_self=False):
        results = []
        if exclude_self:
            condition = lambda item: item is not tile and item.vault.name == tile.vault.name
        else:
            condition = lambda item: item.vault.name == tile.vault.name
        results = filter(condition, self.get_all_sprites())
        return results

    # @time
    def find_path(self, tile):
        get_tile_pos = self.get_tile_pos
        get_tile_id = self.get_tile_id
        get_tile_at = self.get_tile_at

        path = set()
        waypoints = deque()

        def can_walk(tile, rx, ry):
            x, y = get_tile_pos(tile)
            test_tile = get_tile_at(x + rx, y + ry)
            return test_tile is not None and test_tile not in path and \
                get_tile_id(tile) == get_tile_id(test_tile)

        while 1:
            # tile_id = get_tile_id(tile)
            x, y = get_tile_pos(tile)
            # print 'tile_id =', tile_id, '; x, y =', (x, y)

            left = can_walk(tile, -1, 0)
            right = can_walk(tile, 1, 0)
            up = can_walk(tile, 0, -1)
            down = can_walk(tile, 0, 1)

            # print 'waypoint =', [(x, y), tile, left, right, up, down]
            possible_directions = sum((left, right, up, down))
            is_waypoint = possible_directions > 1
            # print 'possible_directions =', possible_directions, '; is_waypoint =', is_waypoint

            if is_waypoint:
                waypoints.append(tile)

            path.add(tile)

            if up:
                tile = get_tile_at(x, y - 1)
            elif right:
                tile = get_tile_at(x + 1, y)
            elif down:
                tile = get_tile_at(x, y + 1)
            elif left:
                tile = get_tile_at(x - 1, y)
            elif waypoints:
                # print 'no more directions. waypoints left:', len(waypoints)
                tile = waypoints.pop()
                # print 'returning to previous waypoint:', tile
            else:
                # print 'no more directions and waypoints left.'
                break

        return path

    def add_column(self):
        for row in self.__map:
            row.append(None)

    def add_row(self):
        row = [None for count in range(0, len(self.__map[0]))]
        self.__map.append(row)

    def insert_column(self, pos):
        for row in self.__map:
            row.insert(pos, None)

    def insert_row(self, pos):
        row = [None for count in range(0, len(self.__map[0]))]
        self.__map.insert(pos, row)

    def remove_column(self, pos):
        for row in self.__map:
            if type(row[pos]) is not TilePlaceholder:
                row[pos].remove_from_parent()
            del row[pos]

    def remove_row(self, pos):
        for tile in self.__map[pos]:
            if type(tile) is not TilePlaceholder:
                tile.remove_from_parent()
        del self.__map[pos]


class LayeredTileMap(Node):

    def __init__(self, name='LayeredTileMap'):
        super(LayeredTileMap, self).__init__(name=name)
        self.order_matters = True  # Keep order of layers while drawing.
        self.__layers = []

    def __iter__(self):
        return iter(self.__layers)

    def add_layer_from_iterable(self, sheet_vault, map_iterable, name=None, default_size=(20, 15)):
        if name is None:
            name = 'TileMap[%d]' % len(self.__layers)
        tilemap = TileMap(name=name)
        tilemap.load_sheet(sheet_vault)
        if map_iterable is not None:
            tilemap.load_map_from_iterable(map_iterable)
        else:
            tilemap.create_map(*default_size)
        tilemap.add_to(self)
        self.__layers.append((tilemap, name))
        return tilemap

    def add_layer(self, sheet_vault, map_filename, default_size=(20, 15)):
        tilemap = TileMap(name=map_filename)
        tilemap.load_sheet(sheet_vault)
        if os.path.exists(map_filename):
            tilemap.load_map(map_filename)
        else:
            tilemap.create_map(*default_size)
        tilemap.add_to(self)
        self.__layers.append((tilemap, map_filename))
        return tilemap

    def get_layer(self, level):
        return self.__layers[level][0]

    def get_num_layers(self):
        return len(self.__layers)

    def load_layers(self, layers, default_size=(20, 15)):
        for layer in layers:
            self.add_layer(sheet_vault=layer['sheet_vault'],
                           map_filename=layer['map_filename'],
                           default_size=default_size)

    def build_maps(self):
        for layer in self.__layers:
            layer[0].build_map()

    def save_maps(self):
        for layer in self.__layers:
            layer[0].save_map(layer[1])

    def get_max_map_size(self, in_pixel=False):
        max_width, max_height = 0, 0
        for layer in self.__layers:
            width, height = layer[0].get_map_size()
            if in_pixel:
                t_size = layer[0].get_tile_size()
                width *= t_size[0]
                height *= t_size[1]
            max_width = max(max_width, width)
            max_height = max(max_height, height)
        return max_width, max_height

    def maximize_map_sizes(self):
        max_width, max_height = self.get_max_map_size()
        for layer in self.__layers:
            tilemap = layer[0]
            width, height = tilemap.get_map_size()
            for count in range(width, max_width):
                tilemap.add_column()
            for count in range(height, max_height):
                tilemap.add_row()
