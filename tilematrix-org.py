# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

# TODO Try to implement loading and creation of sectors via background thread.
#      I think the complete update_sectors method could be within an own thread.
#      This way we would block the main loop much less.

import os
import sys
import ConfigParser
import csv
from math import floor, ceil
from itertools import chain
from collections import OrderedDict

import pygame

from diamond.node import Node
from diamond.sprite import Sprite
from diamond.vault import Vault
from diamond import event
from diamond.font import Font

from diamond.decorators import dump_args, time


class SectorNotAvailableException(Exception):
    pass


def combine_dicts(dicts):
    result = dict()
    for dict_ in dicts:
        for key, val in dict_.iteritems():
            try:
                result[key].append(val)
            except KeyError:
                result[key] = [val]
    return result


def group_by(items, key=None, val=None):
    if key is None:
        key = lambda item: item
    if val is None:
        val = lambda item: item
    result = dict()
    for item in items:
        key_ = key(item)
        val_ = val(item)
        try:
            result[key_].append(val_)
        except KeyError:
            result[key_] = [val_]
    return result


class Matrix(object):

    # TODO let get_sector request x, y, w, h. preload all sectors. create and return matrix.

    def __init__(self):
        self.__matrix = dict()
        self.__top = 0
        self.__bottom = 0
        self.__left = 0
        self.__right = 0
        self.__default_value = None
        self.__sector_size = 10, 10  # Is being filled from config file.
        self.__data_path = None
        self.__sectors_loaded = set()

    def set_default_value(self, value):
        assert type(value) is dict or value is None
        self.__default_value = value

    def get_default_value(self):
        return self.__default_value

    def set_sector_size(self, width, height):
        if self.__data_path is not None:
            raise Exception('Cannot change sector size after setting a data path.')
        self.__sector_size = max(1, width), max(1, height)

    def get_sector_size(self):
        return self.__sector_size

    def set_data_path(self, path, config_file='config.ini'):
        self.__data_path = path
        config = ConfigParser.ConfigParser()
        config.read(os.path.join(path, config_file))
        self.__sector_size = map(int, config.get('general', 'sector_size').split(','))

    # @time
    def save_data(self):
        if not self.__data_path:
            return
        s_w, s_h = self.__sector_size
        sectors = dict((tuple(map(int, id.split(','))), []) for id in self.__sectors_loaded)
        for (x, y), data in self.__matrix.iteritems():
            # print (x, y), data
            s_x = x // s_w
            s_y = y // s_h
            # print s_x, s_y
            for z, id in data.iteritems():
                point = (x - s_w * s_x, y - s_h * s_y, z, id)
                try:
                    sectors[(s_x, s_y)].append(point)
                except KeyError:
                    sectors[(s_x, s_y)] = [point]
        for id, points in sectors.iteritems():
            id = '%d,%d' % id
            filename = os.path.join(self.__data_path, 's.%s.csv' % id)
            # print filename
            # print points
            if points:
                writer = csv.writer(open(filename, 'w'))
                for point in points:
                    writer.writerow(point)
            else:
                if os.path.exists(filename):
                    os.remove(filename)

    # @time
    def set_point(self, x, y, z, data):
        # First make sure that our sector has been loaded.
        s_w, s_h = self.__sector_size
        s_x = x // s_w
        s_y = y // s_h
        self.__ensure_sector_loaded(s_x, s_y)

        self.__top = min(self.__top, y)
        self.__left = min(self.__left, x)
        self.__bottom = max(self.__bottom, y)
        self.__right = max(self.__right, x)
        # TODO track z axis min and max.
        pos = (x, y)
        if data is not None:
            # Set new point data.
            if pos in self.__matrix:
                self.__matrix[pos][z] = data
            else:
                self.__matrix[pos] = {z: data}
            # print 'changed:', self.__matrix[pos]
        else:
            # Remove old point data.
            try:
                del self.__matrix[pos][z]
                # print 'removed:', self.__matrix[pos]
            except KeyError:
                pass

    def get_point(self, x, y, z=None):
        s_w, s_h = self.__sector_size
        s_x = x // s_w
        s_y = y // s_h
        self.__ensure_sector_loaded(s_x, s_y)
        pos = (x, y)
        data = self.__matrix.get(pos, {})
        if z is not None:
            data = data.get(z, None)
        # print 'get_point(%s, %s, %s, %s) -> %s' % (self, x, y, z, data)
        return data

    def get_boundaries(self):
        return dict(
            left=self.__left,
            right=self.__right,
            top=self.__top,
            bottom=self.__bottom,
        )

    def __ensure_sector_loaded(self, s_x, s_y):
        s_w, s_h = self.__sector_size
        id = '%d,%d' % (s_x, s_y)
        if id not in self.__sectors_loaded:
            self.__sectors_loaded.add(id)
            # If possible try loading data from disk.
            if self.__data_path:
                filename = os.path.join(self.__data_path, 's.%s.csv' % id)
                # print filename
                if os.path.exists(filename):
                    for row in csv.reader(open(filename), skipinitialspace=True):
                        x, y, z = map(int, row[0:3])
                        data = row[3]
                        # print (x, y, z), data
                        x += s_x * s_w
                        y += s_y * s_h
                        # print (x, y, z), data
                        self.set_point(x, y, z, str(data))

    # @time
    def get_sector(self, s_x, s_y):
        self.__ensure_sector_loaded(s_x, s_y)
        s_w, s_h = self.__sector_size
        x = s_x * s_w
        y = s_y * s_h
        horiz_range = xrange(x, x + s_w, 1)
        vert_range = xrange(y, y + s_h, 1)
        matrix_get = self.__matrix.get
        matrix = []
        matrix_append = matrix.append
        default_value = self.__default_value
        if default_value is not None:
            copy = lambda: default_value.copy()
        else:
            copy = lambda: None
        for y in vert_range:
            row = []
            row_append = row.append
            for x in horiz_range:
                pos = (x, y)
                row_append(matrix_get(pos, copy()))
            matrix_append(row)
        return matrix

    # @time
    def get_rect(self, x, y, w, h):
        s_w, s_h = self.__sector_size
        range_x = xrange(x, x + w)
        range_y = xrange(y, y + h)
        sectors_to_prefetch = set(
            (x // s_w, y // s_h)
            for x in range_x
            for y in range_y
        )
        # print sectors_to_prefetch
        [self.__ensure_sector_loaded(*pos) for pos in sectors_to_prefetch]
        # print self.__sectors_loaded
        matrix_get = self.__matrix.get
        matrix = []
        matrix_append = matrix.append
        default_value = self.__default_value
        if default_value is not None:
            copy = lambda: default_value.copy()
        else:
            copy = lambda: None
        for y in range_y:
            row = []
            row_append = row.append
            for x in range_x:
                pos = (x, y)
                row_append(matrix_get(pos, copy()))
            matrix_append(row)
            # print row
        # exit()
        return matrix

    # def get_raw_matrix(self):
    #     return self.__matrix


class TileMatrixSector(Node):

    def __split_vault_and_id_from_path(self, id):
        vaults = self.__vaults
        vault, s_id = None, None
        id = str(id)  # TODO is this really a good idea?
        if '/' in id:
            v_id, s_id = id.split('/', 1)
            try:
                vault = vaults[v_id]
            except KeyError:
                raise Exception('Tile "%s" not found. Vault "%s" not loaded!' % (id, v_id))
        else:
            try:
                vault = vaults.itervalues().next()
            except StopIteration:
                raise Exception('Tile "%s" not found. No vault loaded!' % id)
            s_id = id
            # print vault, s_id
        return vault, s_id

    def __get_layer_config(self, z):
        defaults = self.__defaults['layer_defaults']
        specific = self.__defaults['layer_specific']
        config = defaults.copy()
        if z in specific:
            config.update(specific[z])
        return config

    def __init__(self, sector, pos, tile_size, vaults, sprite_bin, show_coords, defaults):
        # TODO SPEED how can we start with tiles shown instead of hidden?
        super(TileMatrixSector, self).__init__(name='TileMatrixSector%s' % str(pos))
        self.__defaults = defaults
        self.order_matters = True  # We just keep this in order for our layers.
        self.manage_order_pos = False  # We manage our order_pos ourselves.
        sector_map = self.__sector_map = dict()
        all_sprites = self.__all_sprites = dict()
        self.hidden_tiles = set()
        self.shown_tiles = set()
        self.__vaults = vaults
        self.__tile_size = tile_size
        # print sector
        # print pos, tile_size
        if show_coords:
            label_node = Node('TileMatrixSectorLabel')
            label_node.set_order_pos(1000)
            label_node.add_to(self)
            label = Font()
            label.set_text(pos)
            label.add_to(label_node)
            self.label_node = label_node
        else:
            self.label_node = None
        t_w, t_h = tile_size
        sprite_make = Sprite.make
        split_vault_and_id_from_path = self.__split_vault_and_id_from_path
        to_be_added = dict()
        for y, row in enumerate(sector):
            for x, col in enumerate(row):
                # print x, y, col
                if col is None:
                    continue
                for z, id in col.iteritems():
                    if id != 'None' and id is not None:
                        # print z, id, sprite_bin
                        if id in sprite_bin and sprite_bin[id]:
                            tile = sprite_bin[id].pop()
                            # print 'pop'
                        else:
                            vault, s_id = split_vault_and_id_from_path(id)
                            # print 'make'
                            tile = sprite_make(vault, s_id)
                            tile.matrix_id = id
                        tile.pos = t_w * x, t_h * y
                        tile.hide()
                        # print tile.pos, tile.pos_real_in_tree
                        try:
                            all_sprites[id].append(tile)
                        except:
                            all_sprites[id] = [tile]
                        try:
                            to_be_added[z].append((z, tile))
                        except KeyError:
                            to_be_added[z] = [(z, tile)]
                        # Fill sector_map for later use.
                        key = (x, y)
                        try:
                            # TODO can we change the list to dict?
                            sector_map[key].append((z, tile))
                        except KeyError:
                            sector_map[key] = [(z, tile)]
        if to_be_added:
            # max_z = max([item[0] for item in to_be_added.iteritems()])
            # for z in range(0, max_z):
            #     if z not in to_be_added:
            #         to_be_added[z] = []
            layers = sorted(to_be_added.iteritems(), key=lambda item: item[0])
            l_to_be_added = []
            l_to_be_added_append = l_to_be_added.append
            for z, items in layers:
                layer = Node(name='TileMatrixSectorLayer[%d]' % z)
                layer.order_matters = False
                layer.set_order_pos(z)
                config = self.__get_layer_config(z)
                layer.set_alpha(config['alpha'])
                if items:
                    layer.add_children([item[1] for item in items])
                    self.hidden_tiles |= set(items)
                l_to_be_added_append(layer)
            self.add_children(l_to_be_added)

    def get_layer(self, z):
        for layer in self.get_child_nodes():
            if layer.order_pos == z:
                return layer
        return None

    def get_layers(self):
        layers = dict()
        for layer in self.get_child_nodes():
            layers[layer.order_pos] = layer
        return layers

    # @time
    def get_all_sprites(self):
        return self.__all_sprites

    def get_sprites_at(self, x, y):
        return self.__sector_map.get((x, y), [])

    # @time
    def set_sprite_at(self, x, y, z, id, hide=True):
        # print 'set_sprite_at(%s, %d, %d, %d, %s)' % (self, x, y, z, id)
        groups = dict(self.__sector_map.get((x, y), {}))
        # print groups
        tile = groups.get(z, None)

        # Catch same id.
        if tile is not None and tile.matrix_id == id:
            return

        layer = self.get_layer(z)

        # Remove existing tile?
        if tile is not None:
            id_ = tile.matrix_id
            # print '*', tile
            layer.remove(tile)
            # Remove from all sprites registry.
            all_sprites = self.__all_sprites
            all_sprites[id_].remove(tile)
            # Remove from sector map.
            sector_map = self.__sector_map
            key = (x, y)
            groups = group_by(sector_map[key], key=lambda item: item[0], val=lambda item: item)
            # print 1, groups[z]
            # print 2, sector_map[key]
            sector_map[key].remove(groups[z][0])

        # Create new tile?
        if id is not None:
            vault, s_id = self.__split_vault_and_id_from_path(id)
            tile = Sprite.make(vault, s_id)
            tile.matrix_id = id
            t_w, t_h = self.__tile_size
            tile.pos = t_w * x, t_h * y
            if hide:
                tile.hide()
            # Add to all sprites registry.
            all_sprites = self.__all_sprites
            try:
                all_sprites[id].append(tile)
            except:
                all_sprites[id] = [tile]
            # Fill sector_map for later use.
            sector_map = self.__sector_map
            key = (x, y)
            try:
                sector_map[key].append((z, tile))
            except KeyError:
                sector_map[key] = [(z, tile)]
            # Create missing layers if necessary.
            if layer is None:
                layer = Node(name='TileMatrixSectorLayer[%d]' % z)
                layer.order_matters = False
                layer.set_order_pos(z)
                config = self.__get_layer_config(z)
                layer.set_alpha(config['alpha'])
                layer.add_to(self)
            # Add tile to layer.
            tile.add_to(layer)
            if hide:
                self.hidden_tiles |= set([tile])
            else:
                self.shown_tiles |= set([tile])

        # print vault, s_id
        # print tile

        # Drop layer if empty.
        if layer is not None and len(layer.get_all_sprites()) == 0:
            # print 'remove layer', z
            layer.parent_node.remove(layer, cascade=True)

    def get_sector_map(self):
        return self.__sector_map

    def get_child_nodes(self):
        return super(TileMatrixSector, self).get_child_nodes() - set([self.label_node])

    def show_children(self, children):
        self.hidden_tiles -= set(children)
        self.shown_tiles |= set(children)
        # print '*****'
        # print children
        groups = group_by(children, key=lambda item: item[0], val=lambda item: item[1])
        # print groups
        # print '====='
        layers = self.get_layers()
        # print layers
        for z, children in groups.iteritems():
            layers[z].show_children(children)

    def hide_children(self, children):
        self.hidden_tiles |= set(children)
        self.shown_tiles -= set(children)
        # print '*****'
        # print children
        groups = group_by(children, key=lambda item: item[0], val=lambda item: item[1])
        # print groups
        # print '====='
        layers = self.get_layers()
        # print layers
        for z, children in groups.iteritems():
            layers[z].hide_children(children)

    def set_alpha_of_layer(self, z, value):
        layers = self.get_layers()
        for z_, node in layers.iteritems():
            if z_ == z:
                node.set_alpha(value)


class TileMatrix(Node):

    def __init__(self, name='TileMatrix'):
        super(TileMatrix, self).__init__(name=name)

        self.__config = ConfigParser.ConfigParser()

        self.__vaults = OrderedDict()
        self.__tile_size = 32, 32  # Never go less than 4x4 or doom awaits you!
        self.__sector_size = 10, 10

        self.__last_visible_sectors = dict()
        self.__last_visibility_map_pos = (None, None), (None, None)

        matrix = Matrix()
        matrix.set_default_value(None)
        matrix.set_sector_size(*self.__sector_size)
        self.__matrix = matrix

        self.__listeners = [
            event.add_listener(self.update_sectors, 'node.moved',
                               instance__is=self),
            event.add_listener(self.update_sectors, 'node.attached',
                               instance__is=self)
        ]

        # TODO Implement some kind of monitoring and GC for this.
        self.__sprite_bin = dict()

        self.__sector_defaults = dict(
            layer_defaults=dict(alpha=100),
            layer_specific=dict(),
        )

        self.order_matters = False

        self.show_sector_coords = False
        self.track_movement = True

    def __del__(self):
        event.remove_listeners(self.__listeners)
        # super(TileMatrix, self).__del__()

    def load_vault(self, vault, alias):
        self.__vaults[alias] = vault

    def load_sheet(self, sheet_vault, alias=None):
        if not self.__vaults:
            self.__tile_size = sheet_vault.tile_size
            t_w, t_h = self.__tile_size
            if t_w < 4 or t_h < 4:
                raise Exception('Tile size cannot be smaller than 4x4. Current size: %dx%d' % (t_w, t_h))
        else:
            if sheet_vault.tile_size != self.__tile_size:
                raise Exception('Cannot load sheet vault with incompatible tile size: %s' % sheet_vault)
        vault = Vault.get_instance(sheet_vault)
        alias = sheet_vault.__name__ if alias is None else alias
        self.load_vault(vault, alias)
        filename = os.path.relpath(sheet_vault.__file__, os.getcwd())
        filename = os.path.splitext(filename)[0]  # Throw away extension - Python shall decide.
        if not self.__config.has_section('tilesheets'):
            self.__config.add_section('tilesheets')
        self.__config.set('tilesheets', alias, filename)

    def get_sheet(self, alias):
        return self.__vaults[alias]

    def get_tile_size(self):
        return self.__tile_size

    def load_points(self, points):
        for x, y, z, value in points:
            self.__matrix.set_point(x, y, z, value)

    def load_matrix(self, path, config_file='config.ini'):
        self.__matrix.set_data_path(path, config_file)
        if not self.__config.has_section('matrix'):
            self.__config.add_section('matrix')
        self.__config.set('matrix', 'data_path', path)

    def save_matrix(self):
        self.__matrix.save_data()

    def load_sheet_file(self, filename, alias=None):
        sheet_path = os.path.dirname(filename)
        sheet_file = os.path.basename(filename)
        if sheet_path:
            sys.path.insert(0, os.path.abspath(sheet_path))
        sheet_file = os.path.splitext(sheet_file)[0]  # Throw away extension - Python shall decide.
        module = __import__(sheet_file, globals(), locals(), [], -1)
        self.load_sheet(module, alias)

    def load_config(self, filename):
        # TODO do we need to reset everything here or can we block somehow if something has been set?
        config = self.__config
        config.read(filename)
        base_dir = os.path.dirname(filename)
        for section in config.sections():
            if section == 'tilesheets':
                for alias, filename in config.items('tilesheets'):
                    filename = os.path.join(base_dir, filename)
                    self.load_sheet_file(filename, alias)
            elif section == 'matrix':
                for key, val in config.items('matrix'):
                    if key == 'data_path':
                        val = os.path.join(base_dir, val)
                        self.load_matrix(val)
                    else:
                        raise Exception('Unknown key for section matrix found: %s' % key)
            # We just ignore unknown sections.
            # else:
            #     raise Exception('Unknown section in config file found: %s' % section)
        # config.write(sys.stdout)

    def rebuild(self):
        # If already attached drop all sectors on display.
        sprite_bin = self.__sprite_bin
        for key, data in self.__last_visible_sectors.iteritems():
            sector = data[1]
            if sector is not None:
                # print 'remove sector instance from display:', key, data
                for key, sprites in sector.get_all_sprites().iteritems():
                    try:
                        sprite_bin[key].extend(sprites)
                    except KeyError:
                        sprite_bin[key] = sprites
                sector.remove_from_parent()
                data[1] = None
        self.__last_visible_sectors = dict()
        self.__last_visibility_map_pos = (None, None), (None, None)
        self.update_sectors()

    def set_sector_size(self, width, height):
        self.__sector_size = width, height
        self.rebuild()

    # @time
    def __update_tile_visibility(self):
        if self.clipping_region_inherited is None:
            return

        # print '******'
        t_w, t_h = self.__tile_size
        clipping_region = self.clipping_region_inherited
        s_w, s_h = (int(ceil((clipping_region.w + clipping_region.x) / float(t_w)) * t_w),
                    int(ceil((clipping_region.h + clipping_region.y) / float(t_h)) * t_h))
        # print 'screen size in pixels:', (s_w, s_h)
        ss_w, ss_h = self.__sector_size
        # print 'sector size in points:', (ss_w, ss_h)
        sp_w = ss_w * t_w
        sp_h = ss_h * t_h
        # print 'sector size in pixels:', (sp_w, sp_h)

        sectors = self.__last_visible_sectors

        # full_sectors = set()
        # clipped_sectors = set()
        full_range_x = range(0, ss_w)
        full_range_y = range(0, ss_h)
        all_coords = set(((c_x, c_y) for c_x in full_range_x for c_y in full_range_y))

        for pos, data in sectors.iteritems():
            # print '*', pos, data
            sector = data[1]
            if sector is None:
                continue
            x, y = sector.pos_real_in_tree
            # print 'pos:', x, y
            sector_map = sector.get_sector_map()
            # print sector_map
            clipped_coords = set()

            if x <= -t_w:
                # print '\tsector should be clipped from left'
                cur_range_x = range(0, -x // t_w - 1)
                cur_range_y = full_range_y
                # print 'range x:', cur_range_x
                # print 'range y:', cur_range_y
                clipped_coords |= set(((c_x, c_y) for c_x in cur_range_x for c_y in cur_range_y))
            if y <= -t_h:
                # print '\tsector should be clipped from top'
                cur_range_x = full_range_x
                cur_range_y = range(0, -y // t_h - 1)
                # print 'range x:', cur_range_x
                # print 'range y:', cur_range_y
                clipped_coords |= set(((c_x, c_y) for c_x in cur_range_x for c_y in cur_range_y))

            if x + sp_w >= s_w + t_w:
                # print '\tsector should be clipped from right'
                cur_range_x = range(ss_w - (x + sp_w - s_w) // t_w + 1, ss_w)
                cur_range_y = full_range_y
                # print 'range x:', cur_range_x
                # print 'range y:', cur_range_y
                clipped_coords |= set(((c_x, c_y) for c_x in cur_range_x for c_y in cur_range_y))
            if y + sp_h >= s_h + t_h:
                # print '\tsector should be clipped from bottom'
                cur_range_x = full_range_x
                cur_range_y = range(ss_h - (y + sp_h - s_h) // t_h + 1, ss_h)
                # print 'range x:', cur_range_x
                # print 'range y:', cur_range_y
                clipped_coords |= set(((c_x, c_y) for c_x in cur_range_x for c_y in cur_range_y))

            shown_coords = all_coords - clipped_coords
            # print 'clipped coords:', clipped_coords
            # print 'shown coords:', shown_coords

            to_be_shown = set(chain(*[sector_map.get(coord, dict()) for coord in shown_coords]))
            # print 'to_be_shown =', to_be_shown

            to_be_hidden = set(chain(*[sector_map.get(coord, dict()) for coord in clipped_coords]))
            # print 'to_be_hidden =', to_be_hidden

            show_diff = to_be_shown - sector.shown_tiles
            hide_diff = to_be_hidden - sector.hidden_tiles

            if show_diff:
                # print 'show_diff =', show_diff
                sector.show_children(show_diff)
                # if pos == (1, 0):
                #     print len(show_diff)
                #     for item in show_diff:
                #         print item
                #     print
                #     print shown_coords
                #     print all_coords
                #     print clipped_coords  # <- problem resides here.
            if hide_diff:
                # print 'hide_diff =', hide_diff
                sector.hide_children(hide_diff)

    # @time
    def update_sectors(self):
        if self.clipping_region_inherited is None:
            return

        t_w, t_h = self.__tile_size

        # Begin: Check if map has been moved enough.
        last_map_pos, last_map_coords = self.__last_visibility_map_pos
        cur_map_coords = self.pos_real_in_tree

        if cur_map_coords[0] > last_map_coords[0]:
            cmp_x = ceil(cur_map_coords[0] / float(t_w))
        else:
            cmp_x = floor(cur_map_coords[0] / float(t_w))

        if cur_map_coords[1] > last_map_coords[1]:
            cmp_y = ceil(cur_map_coords[1] / float(t_h))
        else:
            cmp_y = floor(cur_map_coords[1] / float(t_h))

        cur_map_pos = cmp_x, cmp_y
        # print last_map_pos, '->', cur_map_pos, (diff_x, diff_y)
        if cur_map_pos == last_map_pos:
            return
        self.__last_visibility_map_pos = cur_map_pos, cur_map_coords
        # End: Check if map has been moved enough.

        # TODO test if c_x and c_y are wrong if the matrix parent is being moved.

        clipping_region = self.clipping_region_inherited
        s_w, s_h = (int(ceil((clipping_region.w + clipping_region.x) / float(t_w)) * t_w),
                    int(ceil((clipping_region.h + clipping_region.y) / float(t_h)) * t_h))
        # print 'screen size in pixels:', (s_w, s_h)
        ss_w, ss_h = self.__sector_size
        # print 'sector size in points:', (ss_w, ss_h)
        sp_w = ss_w * t_w
        sp_h = ss_h * t_h
        # print 'sector size in pixels:', (sp_w, sp_h)
        o_x, o_y = self.pos_real_in_tree
        # print 'matrix pos in pixels:', (o_x, o_y)
        o_x *= -1
        o_y *= -1
        # print 'matrix offset in pixels:', (o_x, o_y)
        sector = int(floor(o_x / float(sp_w))), int(floor(o_y / float(sp_h)))
        c_x, c_y = sector[0] * sp_w - o_x, sector[1] * sp_h - o_y
        # print 'top left sector:', (sector), 'at', (c_x, c_y)
        # offset = -o_x // t_w * t_w + o_x, c_y
        # offset = -o_x, -o_y
        # print 'offset:', offset

        # First find sectors to display.
        # print s_w, s_h
        d_x, d_y = s_w - c_x, s_h - c_y
        # print d_x, d_y
        r_w, r_h = int(ceil(d_x / float(sp_w))), int(ceil(d_y / float(sp_h)))
        # print r_w, r_h
        sectors_to_display = dict(
            ((x + sector[0], y + sector[1]), [(c_x + x * sp_w, c_y + y * sp_h), None])
            for x in xrange(0, r_w)
            for y in xrange(0, r_h)
        )
        # print 'sectors_to_display =', sectors_to_display

        # print c_x + sp_w * r_w, c_y + sp_h * r_h
        # exit()

        last_visible_sectors = self.__last_visible_sectors
        last_keys = set(last_visible_sectors.keys())
        current_keys = set(sectors_to_display.keys())

        if last_keys == current_keys:
            self.__update_tile_visibility()
            return

        # Catch deleted sprites in temporary bin for eventual re-use.
        sprite_bin = self.__sprite_bin

        keys_to_be_removed = last_keys - current_keys
        keys_to_be_added = current_keys - last_keys
        keys_to_be_held = current_keys.intersection(last_keys)

        # print
        # print keys_to_be_removed
        # print keys_to_be_added
        # print keys_to_be_held

        # Handle sectors not to display anymore.
        for key in keys_to_be_removed:
            data = last_visible_sectors[key]
            sector = data[1]
            if sector is not None:
                # print 'remove sector instance from display:', key, data
                for key, sprites in sector.get_all_sprites().iteritems():
                    try:
                        sprite_bin[key].extend(sprites)
                    except KeyError:
                        sprite_bin[key] = sprites
                # NOTE Enable this loop for debugging only!
                # for key, vals in sprite_bin.iteritems():
                #     # print key
                #     for val in vals:
                #         # print val.vault.name, val.matrix_id
                #         if val.vault.name != val.matrix_id:
                #             print 'found sprite %s with wrong matrix_id %s.' % (val.vault.name, val.matrix_id)
                #             exit()
                #         if val.matrix_id != key:
                #             print 'found wrong sprite %s in bin %s.' % (val.matrix_id, key)
                #             exit()
                sector.remove_from_parent()
                data[1] = None

        # Handle sectors to hold.
        for key in keys_to_be_held:
            data = last_visible_sectors[key]
            # Copy instance into new view grid.
            # print 'keep sector instance on display', key, data
            sectors_to_display[key][1] = data[1]

        # Handle sectors new to display.
        for key in keys_to_be_added:
            data = sectors_to_display[key]
            if data[1] is None:
                # print 'create sector instance on display:', key, data
                pos = key  # map(int, key.split(','))
                # Try to re-use sprites-to-be-deleted from bin.
                rect = (pos[0] * ss_w, pos[1] * ss_h, ss_w, ss_h)
                # NOTE Enable this loop for debugging only!
                # for key, vals in sprite_bin.iteritems():
                #     # print key
                #     for val in vals:
                #         # print val.vault.name, val.matrix_id
                #         if val.vault.name != val.matrix_id:
                #             print 'found sprite %s with wrong matrix_id %s.' % (val.vault.name, val.matrix_id)
                #             exit()
                #         if val.matrix_id != key:
                #             print 'found wrong sprite %s in bin %s.' % (val.matrix_id, key)
                #             exit()
                sector = TileMatrixSector(self.__matrix.get_rect(*rect), pos, self.__tile_size, self.__vaults, sprite_bin, self.show_sector_coords, self.__sector_defaults)
                sector.pos = pos[0] * sp_w, pos[1] * sp_h
                # print sector.pos
                # Only attach sector if really necessary.
                # TODO Find a smarter solution not having to create it in the first way!
                if self.show_sector_coords or sector.get_layers():
                    sector.add_to(self)
                    data[1] = sector

        self.__last_visible_sectors = sectors_to_display
        self.__update_tile_visibility()

    def get_tile_id_at(self, x, y, z=None):
        return self.__matrix.get_point(x, y, z).copy()

    def _get_tile_sector_at(self, x, y):
        s_w, s_h = self.__sector_size
        s_x = x // s_w
        s_y = y // s_h
        # x -= s_x * s_w
        # y -= s_y * s_h
        # print (s_x, s_y), (x, y)
        return self.__last_visible_sectors.get((s_x, s_y), [None, None])[1]

    # @time
    def get_tile_at(self, x, y, z=None):
        sector = self._get_tile_sector_at(x, y)
        if sector is None:
            # raise SectorNotAvailableException()
            return None
        data = dict(sector.get_sprites_at(x, y))
        if z is not None:
            data = data.get(z, None)
        return data

    def _is_tile_visible(self, sector, x, y):
        # TODO SPEED decide if tile is visible or not. see __update_tile_visibility for reference.
        return True

    def set_tile_at(self, x, y, z, id):
        new_point_data = (x, y, z, id)
        sector = self._get_tile_sector_at(x, y)
        if sector is not None:
            s_w, s_h = self.__sector_size
            s_x = x // s_w
            s_y = y // s_h
            x -= s_x * s_w
            y -= s_y * s_h
            is_visible = self._is_tile_visible
            # TODO Move the removal of the default tile into the sector.set_sprite_at.
            if id is not None:
                # Check if default value has been set and remove it.
                sprites = sector.get_sprites_at(x, y)
                point = self.__matrix.get_point(x, y)
                # print '***', sprites, point
                if sprites and not point:
                    set_sprite_at = sector.set_sprite_at
                    for z_, sprite in sprites:
                        set_sprite_at(x, y, z_, None)
                # Set new tile.
                sector.set_sprite_at(x, y, z, id, hide=not is_visible(sector, x, y))
            else:
                # Drop old tile.
                sector.set_sprite_at(x, y, z, None)
                sprites = sector.get_sprites_at(x, y)
                # Place default value if nothing left.
                if not sprites:
                    default_value = self.__matrix.get_default_value()
                    if default_value is not None:
                        set_sprite_at = sector.set_sprite_at
                        for key, val in default_value.iteritems():
                            set_sprite_at(x, y, key, val, hide=not is_visible(sector, x, y))
            # self.__update_tile_visibility()
        # else:
        #     raise SectorNotAvailableException()
        self.__matrix.set_point(*new_point_data)

    # @time
    def set_default_tile_value(self, value):
        is_visible = self._is_tile_visible
        if value is not None:
            # print 'set to value.', value
            if self.__matrix.get_default_value() == value:
                # print 'default value already set:', value
                return
            self.__matrix.set_default_value(value)
            # Add default tiles to sectors.
            s_w, s_h = self.__sector_size
            range_x = range(0, s_w)
            range_y = range(0, s_h)
            get_point = self.__matrix.get_point
            for s_pos, data in self.__last_visible_sectors.iteritems():
                # print '*', s_pos
                # print data
                sector = data[1]
                # TODO move the following code into the sector itself.
                get_sprites_at = sector.get_sprites_at
                set_sprite_at = sector.set_sprite_at
                for y in range_y:
                    for x in range_x:
                        pos = s_pos[0] * s_w + x, s_pos[1] * s_h + y
                        point = get_point(*pos)
                        # if point:
                        #     print 'x, y =', (x, y),
                        #     print 'pos =', (pos),
                        #     print point
                        sprites = get_sprites_at(x, y)
                        if not sprites:
                            # if point:
                            #     print 'POINT SET!'
                            for key, val in value.iteritems():
                                set_sprite_at(x, y, key, val, hide=not is_visible(sector, x, y))
            self.__update_tile_visibility()
        else:
            # print 'set to none.'
            # Remove default tiles from sectors.
            s_w, s_h = self.__sector_size
            default_value = self.__matrix.get_default_value()
            if default_value is None:
                # print 'default value is already none.'
                return
            range_x = range(0, s_w)
            range_y = range(0, s_h)
            get_point = self.__matrix.get_point
            for s_pos, data in self.__last_visible_sectors.iteritems():
                # print '*', s_pos
                # print data
                sector = data[1]
                # TODO move the following code into the sector itself.
                get_sprites_at = sector.get_sprites_at
                set_sprite_at = sector.set_sprite_at
                for y in range_y:
                    for x in range_x:
                        pos = s_pos[0] * s_w + x, s_pos[1] * s_h + y
                        point = get_point(*pos)
                        # if point:
                        #     print 'x, y =', (x, y),
                        #     print 'pos =', (pos),
                        #     print point
                        sprites = get_sprites_at(x, y)
                        if sprites and not point:
                            for z, sprite in sprites:
                                set_sprite_at(x, y, z, None)
            self.__matrix.set_default_value(None)
            self.__update_tile_visibility()

    def on_node_added(self, display, node=None):
        super(TileMatrix, self).on_node_added(display=display, node=node)
        self.update_sectors()

    def get_virtual_rect(self):
        tile_size = self.__tile_size
        # print tile_size
        boundaries = self.__matrix.get_boundaries()
        # print boundaries
        width = boundaries['right'] - boundaries['left'] + 1
        height = boundaries['bottom'] - boundaries['top'] + 1
        rect = pygame.Rect(
            boundaries['left'] * tile_size[0],
            boundaries['top'] * tile_size[1],
            width * tile_size[0],
            height * tile_size[1],
        )
        return rect

    def translate_to_matrix(self, x, y):
        tile_size = self.__tile_size
        return x // tile_size[0], y // tile_size[1]

    def translate_to_pos(self, x, y):
        tile_size = self.__tile_size
        return x * tile_size[0], y * tile_size[1]

    def set_alpha_of_layer(self, z, value):
        self.__sector_defaults['layer_specific'][z] = dict(alpha=value)
        for s_pos, data in self.__last_visible_sectors.iteritems():
            # print s_pos, data
            sector = data[1]
            sector.set_alpha_of_layer(z, value)
