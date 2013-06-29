# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

# TODO Try to implement loading and creation of sectors via background thread.
#      I think the complete update_sectors method could be within an own thread.
#      This way we would block the main loop much less.

# TODO Can we take snapshots of nodes using glCopyTexSubImage2D and just redraw
#      them if something changed?

import os
import sys
import ConfigParser
import csv
from math import floor, ceil
from itertools import chain
from collections import OrderedDict
from weakref import proxy
from threading import RLock

import pygame

from diamond.ticker import Ticker
from diamond.node import Node
from diamond.sprite import Sprite
from diamond.vault import Vault
from diamond.vault import GeneratedVault
from diamond import event
from diamond.font import Font

from diamond.decorators import dump_args, time

# Fix for Python 3 where xrange is absent and range is a generator.
try:
    xrange
except NameError:
    xrange = range


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
        index_filename = os.path.join(self.__data_path, 'b.csv')
        if os.path.exists(index_filename):
            reader = csv.reader(open(index_filename), skipinitialspace=True)
            data = map(int, reader.next())
            self.__top, self.__left, self.__bottom, self.__right = data

    def __rebuild_index(self):
        s_w, s_h = self.__sector_size
        print('Rebuilding matrix index...')
        for root, dirs, files in os.walk(self.__data_path):
            for filename in files:
                if filename.startswith('i.') and filename.endswith('.csv'):
                    os.remove(os.path.join(root, filename))
        indexes = dict()
        top, left, bottom, right = self.__top, self.__left, self.__bottom, self.__right
        for root, dirs, files in os.walk(self.__data_path):
            files = sorted(files)
            # print(root, dirs, files)
            print('Found %d sectors to index...' % len(files))
            for filename in files:
                if not (filename.startswith('s.') and filename.endswith('.csv')):
                    continue
                # print('Inspecting sector file: %s' % filename)
                reader = csv.reader(open(os.path.join(root, filename)), skipinitialspace=True)
                s_x, s_y = map(int, filename[2:-4].split(','))
                for x, y, z, id in reader:
                    x = (s_x * s_w) + int(x)
                    y = (s_y * s_h) + int(y)
                    top = min(top, y)
                    left = min(left, x)
                    bottom = max(bottom, y)
                    right = max(right, x)
                    # TODO track z axis min and max.
                    sheet, tile_id = id.split('/')
                    # Update index of specific tile.
                    if id not in indexes:
                        id_ = '%s,%s' % (sheet, tile_id)
                        index_filename = os.path.join(self.__data_path, 'i.%s.csv' % id_)
                        indexes[id] = csv.writer(open(index_filename, 'w'))
                    indexes[id].writerow((x, y, z))
                    # Update index of used tilesheet.
                    if sheet not in indexes:
                        index_filename = os.path.join(self.__data_path, 'i.%s.csv' % sheet)
                        indexes[sheet] = csv.writer(open(index_filename, 'w'))
                    indexes[sheet].writerow((x, y, z, tile_id))
        index_filename = os.path.join(self.__data_path, 'b.csv')
        writer = csv.writer(open(index_filename, 'w'))
        writer.writerow((top, left, bottom, right))
        self.__top, self.__left, self.__bottom, self.__right = top, left, bottom, right
        print('Finished rebuilding matrix index.')

    def __point_cmp_key(self, item):
        return int('%d%d%d' % (item[2], item[1], item[0]))

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
                points = sorted(points, key=self.__point_cmp_key)
                # print points
                writer = csv.writer(open(filename, 'w'))
                for point in points:
                    writer.writerow(point)
            else:
                if os.path.exists(filename):
                    os.remove(filename)
        self.__rebuild_index()

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
    def __get_rect(self, range_x, range_y):
        matrix_get = self.__matrix.get
        default_value = self.__default_value
        if default_value is not None:
            copy = default_value.copy
            matrix = [
                [matrix_get((x_, y_), copy()) for x_ in range_x]
                for y_ in range_y
            ]
        else:
            matrix = [
                [matrix_get((x_, y_), None) for x_ in range_x]
                for y_ in range_y
            ]
        return matrix

    # @time
    def get_sector(self, s_x, s_y):
        self.__ensure_sector_loaded(s_x, s_y)
        s_w, s_h = self.__sector_size
        x = s_x * s_w
        y = s_y * s_h
        range_x = xrange(x, x + s_w, 1)
        range_y = xrange(y, y + s_h, 1)
        return self.__get_rect(range_x, range_y)

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
        return self.__get_rect(range_x, range_y)

    # @time
    def find_in_rect(self, x, y, w, h, data):
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
        default_value = self.__default_value
        if default_value is not None:
            copy = default_value.copy
        else:
            copy = lambda: None
        results = []
        results_append = results.append
        for y in range_y:
            for x in range_x:
                point = matrix_get((x, y), copy())
                if point is not None:
                    result = [key for key, val in point.iteritems() if val == data]
                    if result:
                        results_append((x, y, result[0]))
        # print results
        # exit()
        return results

    # Tilesheet find and index above should be moved into TileMatrix class.
    def find_in_matrix_by_tilesheet(self, data):
        if '/' in data:
            data = '%s,%s' % tuple(data.split('/'))
        index_filename = os.path.join(self.__data_path, 'i.%s.csv' % data)
        if os.path.exists(index_filename):
            reader = csv.reader(open(index_filename))
            return [map(int, row[:3]) + row[3:] for row in reader]
        else:
            return []

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

    def __create_repr_vault(self, z, surface=None):
        """Returns a new sector vault based either on an empty or given image."""
        width, height = self.__repr_image_size
        vault = GeneratedVault()
        if surface is not None:
            vault.set_surface(surface)
        else:
            image = vault.generate_surface(width, height)
            image.fill((0, 0, 0, 0))
        sprite = vault.add_sprite('cached sector')
        action = sprite.add_action('none')
        action.add_frame((0, 0, width, height), (0, 0), (0, 0))
        self.__representations[z] = vault
        return self.__representations[z]

    def __get_repr_vault(self, z):
        """Returns new or existing sector vault."""
        try:
            return self.__representations[z]
        except KeyError:
            return self.__create_repr_vault(z)

    def __init__(self, tilematrix, offset, sector, pos, tile_size, vaults, sprite_bin, show_coords):
        name = 'TileMatrixSector%s' % str(pos)
        super(TileMatrixSector, self).__init__(name=name)
        # print '__init__(%s)' % self
        self.__tilematrix = proxy(tilematrix)
        self.__offset = offset
        self.__sector_pos = pos  # Just to keep track of it. Easier debugging.
        self.order_matters = False
        self.manage_order_pos = False  # We manage our order_pos ourselves.
        sector_map = self.__sector_map = dict()
        all_sprites = self.__all_sprites = dict()
        self.hidden_tiles = set()
        self.shown_tiles = set()
        self.__vaults = vaults
        self.__tile_size = tile_size
        self.__sector_size = (len(sector[0]), len(sector))
        self.__representations = dict()

        # Prepare flattened down size of the map.
        self.__repr_image_size = (len(sector[0]) * tile_size[0], len(sector) * tile_size[0])

        # print sector
        # print pos, tile_size
        if show_coords:
            label_node = Node('TileMatrixSectorLabel')
            label_node.order_matters = False
            # label_node.set_order_pos(1000)
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

        # Prepare repr image filename template.
        cache_path = tilematrix._sector_cache_path
        if cache_path is not None:
            fn_pos = '%d,%d' % pos
            fn_path = cache_path
            fn_s_template = '%s/tm.s.%s.%%d.tga' % (fn_path, fn_pos)
            # print fn_s_template
            fn_i_template = '%s/tm.i.%s' % (fn_path, fn_pos)
            # print fn_i_template

        if cache_path is not None and os.path.exists(fn_i_template):
            idx_layers = []
            with open(fn_i_template, 'r') as handle:
                data = handle.read()
                if len(data):
                    idx_layers = map(int, data.split(','))
            create_repr_vault = self.__create_repr_vault
            for z in idx_layers:
                filename = fn_s_template % z
                # print filename
                surface = pygame.image.load(filename)
                create_repr_vault(z, surface)
        else:
            get_repr_vault = self.__get_repr_vault
            splitted_vault_cache = {}
            for y, row in enumerate(sector):
                for x, col in enumerate(row):
                    # print x, y, col
                    if col is None:
                        continue
                    tile_pos = t_w * x, t_h * y
                    # print tile_pos
                    for z, id in col.iteritems():
                        if id != 'None' and id is not None:
                            # print z, id, sprite_bin
                            # if id in sprite_bin and sprite_bin[id]:
                            #     tile = sprite_bin[id].pop()
                            #     # print 'pop'
                            #     # print tile, 'PARENT =', tile.parent_node
                            # else:
                            #     vault, s_id = split_vault_and_id_from_path(id)
                            #     # print 'make'
                            #     tile = sprite_make(vault, s_id)
                            #     tile.matrix_id = id
                            # tile.pos = offset[0] + t_w * x, offset[1] + t_h * y
                            # # tile.hide()  # Do not hide with cached nodes.
                            # # print tile.pos, tile.pos_real_in_tree
                            # try:
                            #     all_sprites[id].append(tile)
                            # except KeyError:
                            #     all_sprites[id] = [tile]
                            # try:
                            #     to_be_added[z].append((z, tile))
                            # except KeyError:
                            #     to_be_added[z] = [(z, tile)]
                            repr_vault = get_repr_vault(z)
                            repr_image = repr_vault.surface

                            # Now get requested vault and surface to copy from.
                            try:
                                vault, s_id = splitted_vault_cache[id]
                            except:
                                vault, s_id = splitted_vault_cache[id] = split_vault_and_id_from_path(id)
                            # print vault, s_id

                            try:
                                # Avoid func call in favor of speed.
                                sprite = vault.sprites[s_id]
                            except KeyError:
                                print('Could not find sprite data "%s" for sector %s of pos %s.' % (id, pos, (x, y)))
                                repr_image.fill((255, 255, 255, 255), (tile_pos, tile_size))
                            else:
                                # print sprite
                                # Avoid func call in favor of speed.
                                action = sprite.actions['none']
                                # print action
                                # Avoid func call in favor of speed.
                                frame = action.frames[0]
                                # Get repr vault and surface to draw on.
                                # print frame
                                surface = frame.get_surface()
                                # print surface
                                # And finally draw it.
                                repr_image.blit(surface, tile_pos)
                            # Set tile to id when blitting on the repr image.
                            tile = id
                            # # Fill sector_map for later use.
                            key = (x, y)
                            try:
                                # TODO can we change the list to dict?
                                sector_map[key].append((z, tile))
                            except KeyError:
                                sector_map[key] = [(z, tile)]

            # Write repr images to disk.
            if cache_path is not None:
                idx_layers = []
                for z, vault in self.__representations.iteritems():
                    filename = fn_s_template % z
                    # print filename
                    pygame.image.save(vault.surface, filename)
                    idx_layers.append(str(z))
                with open(fn_i_template, 'w') as handle:
                    handle.write(','.join(idx_layers))

        # Prepare adding everything to the layer.
        for z, vault in self.__representations.iteritems():
            sprite = sprite_make(vault)
            sprite.pos = offset
            try:
                to_be_added[z].append((z, sprite))
            except KeyError:
                to_be_added[z] = [(z, sprite)]
            key = (-1, -1)
            try:
                # TODO can we change the list to dict?
                sector_map[key].append((z, sprite))
            except KeyError:
                sector_map[key] = [(z, sprite)]

        if to_be_added:
            # print 'adding'
            for z, items in to_be_added.iteritems():
                # print z, items
                if items:
                    layer = self.__tilematrix.get_layer(z)
                    if layer is None:
                        layer = self.__tilematrix.add_layer(z)
                    layer.add_children([item[1] for item in items])

    def remove_from_parent(self, cascade=True):
        # print 'remove_from_parent(%s)' % self
        groups = group_by(chain(*self.__sector_map.itervalues()), key=lambda item: item[0], val=lambda item: item[1])
        layers = self.get_layers()
        # name = self.name
        for z, children in groups.iteritems():
            # print z, children
            layers[z].remove_children(children)
        self.__sector_map.clear()
        self.__all_sprites.clear()
        self.hidden_tiles.clear()
        self.shown_tiles.clear()
        # print
        super(TileMatrixSector, self).remove_from_parent(cascade=cascade)

    def on_node_removed(self, node=None, hard=True):
        # print 'on_node_removed(%s)' % self
        groups = group_by(chain(*self.__sector_map.itervalues()), key=lambda item: item[0], val=lambda item: item[1])
        layers = self.get_layers()
        # name = self.name
        for z, children in groups.iteritems():
            # print z, children
            layers[z].remove_children(children)
        self.__sector_map.clear()
        self.__all_sprites.clear()
        self.hidden_tiles.clear()
        self.shown_tiles.clear()
        super(TileMatrixSector, self).on_node_removed(node=node, hard=hard)

    def get_layer(self, z):
        for layer in self.get_child_nodes():
            if layer.order_pos == z:
                return layer
        return None

    def get_layers(self):
        return self.__tilematrix.get_layers()

    # @time
    def get_all_sprites(self):
        return self.__all_sprites

    def get_sprites_at(self, x, y):
        return self.__sector_map.get((x, y), [])

    # @time
    def set_sprites_at(self, points):
        # print points
        pos = self.__sector_pos
        groups = dict()
        for x, y, z, id in points:
            try:
                groups[z].append((x, y, id))
            except KeyError:
                groups[z] = [(x, y, id)]

        tilematrix__get_layer = self.__tilematrix.get_layer
        tilematrix__add_layer = self.__tilematrix.add_layer
        t_w, t_h = self.__tile_size
        split_vault_and_id_from_path = self.__split_vault_and_id_from_path
        sector_map = self.__sector_map
        splitted_vault_cache = {}
        for z, points in groups.iteritems():
            layer = tilematrix__get_layer(z)
            if layer is None:
                # print('adding layer %d' % z)
                layer = tilematrix__add_layer(z)

            repr_vault = self.__get_repr_vault(z)
            repr_image = repr_vault.surface

            for x, y, id in points:
                tile_pos = t_w * x, t_h * y
                # print(tile_pos, z, id)

                # Get old tile info.
                try:
                    # print sector_map[(x, y)]
                    old_tile = dict(sector_map[(x, y)])[z]
                    # print old_tile
                except KeyError:
                    pass
                else:
                    # Get vault of old tile.
                    try:
                        vault, s_id = splitted_vault_cache[old_tile]
                    except:
                        vault, s_id = splitted_vault_cache[old_tile] = split_vault_and_id_from_path(old_tile)
                    # print vault, s_id

                    try:
                        # Avoid func call in favor of speed.
                        sprite = vault.sprites[s_id]
                    except KeyError:
                        print('Could not find sprite data "%s" for sector %s of pos %s.' % (old_tile, pos, (x, y)))
                        rect_size = (t_w, t_h)
                    else:
                        # print sprite
                        # Avoid func call in favor of speed.
                        action = sprite.actions['none']
                        # print action
                        # Avoid func call in favor of speed.
                        frame = action.frames[0]
                        # Get size of frame.
                        rect_size = frame.rect[2:]
                    # Clear old data.
                    repr_image.fill((0, 0, 0, 0), (tile_pos, rect_size))

            for x, y, id in points:
                if id is not None:
                    tile_pos = t_w * x, t_h * y
                    # print(tile_pos, z, id)

                    # Now get requested vault and surface to copy from.
                    try:
                        vault, s_id = splitted_vault_cache[id]
                    except:
                        vault, s_id = splitted_vault_cache[id] = split_vault_and_id_from_path(id)
                    # print vault, s_id

                    try:
                        # Avoid func call in favor of speed.
                        sprite = vault.sprites[s_id]
                    except KeyError:
                        print('Could not find sprite data "%s" for sector %s of pos %s.' % (id, pos, (x, y)))
                        repr_image.fill((255, 255, 255, 255), (tile_pos, (t_w, t_h)))
                    else:
                        # print sprite
                        # Avoid func call in favor of speed.
                        action = sprite.actions['none']
                        # print action
                        # Avoid func call in favor of speed.
                        frame = action.frames[0]
                        # Get repr vault and surface to draw on.
                        surface = frame.get_surface()
                        # print surface
                        # And finally draw it.
                        repr_image.blit(surface, tile_pos)
                    # Set tile to id when blitting on the repr image.
                    tile = id
                    # Manage sector_map.
                    key = (x, y)
                    try:
                        # TODO can we change the list to dict?
                        sector_map[key].append((z, tile))
                    except KeyError:
                        sector_map[key] = [(z, tile)]

            try:
                repr_sprite = dict(self.__sector_map[(-1, -1)])[z]
            except KeyError:
                # print 'make', z
                repr_sprite = Sprite.make(repr_vault)
                repr_sprite.pos = self.__offset
                layer.add(repr_sprite)
                _key = (-1, -1)
                try:
                    # TODO can we change the list to dict?
                    sector_map[_key].append((z, repr_sprite))
                except KeyError:
                    sector_map[_key] = [(z, repr_sprite)]
            else:
                # print 'reuse', z
                repr_sprite._unload_frames()
                repr_sprite.frames_is_dirty = True
                repr_sprite._add_to_update_list()
                self.display.drawables_dl_dirty = True

            # print repr_sprite

    def get_sector_map(self):
        return self.__sector_map

    def get_child_nodes(self):
        return super(TileMatrixSector, self).get_child_nodes() - set([self.label_node])

    def get_sector_size(self):
        return self.__sector_size

    def get_sector_pos(self):
        return self.__sector_pos

    # def show_children(self, children):
    #     self.hidden_tiles -= set(children)
    #     self.shown_tiles |= set(children)
    #     # print '*****'
    #     # print children
    #     groups = group_by(children, key=lambda item: item[0], val=lambda item: item[1])
    #     # print groups
    #     # print '====='
    #     layers = self.get_layers()
    #     # print layers
    #     for z, children in groups.iteritems():
    #         layers[z].find_node(self.name).show_children(children)

    # def hide_children(self, children):
    #     self.hidden_tiles |= set(children)
    #     self.shown_tiles -= set(children)
    #     # print '*****'
    #     # print children
    #     groups = group_by(children, key=lambda item: item[0], val=lambda item: item[1])
    #     # print groups
    #     # print '====='
    #     layers = self.get_layers()
    #     # print layers
    #     for z, children in groups.iteritems():
    #         layers[z].find_node(self.name).hide_children(children)

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
        self._sector_cache_path = None  # Shared with TileMatrixSector class.

        self.__last_visible_sectors = dict()
        self.__last_visibility_map_pos = (None, None), (None, None)

        self.__layers = dict()
        self.__layer_config = dict()

        matrix = Matrix()
        matrix.set_default_value(None)
        matrix.set_sector_size(*self.__sector_size)
        self.__matrix = matrix

        # TODO Implement some kind of monitoring and GC for this.
        self.__sprite_bin = dict()

        self.order_matters = True  # Keep our layers in order.

        self.show_sector_coords = False
        # self.track_movement = True  # Not necessary without the events below.

        self.__sector_node = Node('TileMatrixSectors')
        self.__sector_node.order_matters = False
        self.__sector_node.set_order_pos(1000)
        self.__sector_node.add_to(self)

        self.lock = RLock()
        self.ticker = Ticker()
        self.ticker.start()
        self.ticker.add(self.__housekeeping, 16, onetime=False, dropable=True)

        # For our idle house keeping task.
        self.__sector_status = {}

        self.__listeners = [
            # Disabled in favor of the overridden methods below (speed).
            # event.add_listener(self.update_sectors, 'node.moved',
            #                    instance__is=self),
            # event.add_listener(self.update_sectors, 'node.attached',
            #                    instance__is=self)
            # event.add_listener(self.__housekeeping, 'display.update.cpu_is_idle')
        ]

    # def update(self):
    #     super(TileMatrix, self).update()
    #     self.__update_sectors()

    def __del__(self):
        # print 'del', self
        # print self.__sprite_bin
        # print self.__last_visible_sectors
        self.ticker.join()
        event.remove_listeners(self.__listeners)
        super(TileMatrix, self).__del__()

    # BEGIN: Overrides of node methods for making them thread safe.
    def _update_real_pos_in_tree(self, *args, **kwargs):
        with self.lock:
            if super(TileMatrix, self)._update_real_pos_in_tree(*args, **kwargs):
                self.update_sectors()

    def attach_to_display(self, *args, **kwargs):
        self.ticker.pause()
        with self.lock:
            super(TileMatrix, self).attach_to_display(*args, **kwargs)
            self.update_sectors()
        self.ticker.unpause()

    def show(self, *args, **kwargs):
        self.ticker.pause()
        with self.lock:
            super(TileMatrix, self).show(*args, **kwargs)
            self.update_sectors()
        self.ticker.unpause()

    def hide(self, *args, **kwargs):
        self.ticker.pause()
        with self.lock:
            super(TileMatrix, self).hide(*args, **kwargs)
        self.ticker.unpause()

    def update_inherited_rgba(self, *args, **kwargs):
        self.ticker.pause()
        with self.lock:
            super(TileMatrix, self).update_inherited_rgba(*args, **kwargs)
        self.ticker.unpause()

    def update_inherited_gamma(self, *args, **kwargs):
        self.ticker.pause()
        with self.lock:
            super(TileMatrix, self).update_inherited_gamma(*args, **kwargs)
        self.ticker.unpause()

    def remove_all(self, *args, **kwargs):
        self.ticker.clear()
        super(TileMatrix, self).remove_all(*args, **kwargs)

    def on_node_removed(self, *args, **kwargs):
        # print 'on_node_removed(%s)' % self
        self.ticker.clear()
        self.__sector_status.clear()
        self.__last_visible_sectors.clear()
        super(TileMatrix, self).on_node_removed(*args, **kwargs)
    # END: Overrides of node methods for making them thread safe.

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
            elif section == 'layer.order_change':
                for z, new_z in config.items('layer.order_change'):
                    z = int(z)
                    new_z = int(new_z)
                    try:
                        self.__layer_config[z]['reorder'] = new_z
                    except KeyError:
                        self.__layer_config[z] = dict(reorder=new_z)
            elif section == 'layer.sector':
                for key, val in config.items('layer.sector'):
                    if key == 'size':
                        val = tuple(map(int, val.split(',')))
                        self.__sector_size = val
                    elif key == 'cache_path':
                        val = os.path.join(base_dir, val)
                        self._sector_cache_path = val
                        if not os.path.exists(val):
                            os.makedirs(val)
            # We just ignore unknown sections.
            # else:
            #     raise Exception('Unknown section in config file found: %s' % section)
        # config.write(sys.stdout)

    def get_config(self):
        return self.__config

    def rebuild(self):
        # If already attached drop all sectors on display.
        # sprite_bin = self.__sprite_bin
        for key, data in self.__last_visible_sectors.iteritems():
            sector = data[1]
            if sector is True:
                if key in self.__sector_status:
                    self.__sector_status[key]['wanted'] = False
                data[1] = None
            elif sector is not None:
                # print 'remove sector instance from display:', key, data
                # for key, sprites in sector.get_all_sprites().iteritems():
                #     try:
                #         sprite_bin[key].extend(sprites)
                #     except KeyError:
                #         sprite_bin[key] = sprites
                # sector.remove_from_parent()
                try:
                    self.__sector_status[key]['wanted'] = False
                except KeyError:
                    self.__sector_status[key] = dict(
                        sector=sector,
                        wanted=False,
                        init_args=None,
                    )
                data[1] = None
        # self.__last_visible_sectors = dict()
        self.__last_visibility_map_pos = (None, None), (None, None)
        self.update_sectors()

    # FIXME When extending a matrix something goes wrong and e.g. selections
    # don't show up in the extended area. Someone is still using the old size.
    def set_sector_size(self, width, height):
        self.__sector_size = width, height
        self.rebuild()

    def get_sector_size(self):
        return self.__sector_size

    def __drop_sector(self, sector):
        with self.lock:
            event.emit('tilematrix.sector.dropped.before', sector)
            # print 'remove sector instance from display:', sector
            # print len(sector_.get_all_sprites())
            sprite_bin = self.__sprite_bin
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

    # @time
    def __create_sector(self, *args):
        key, ss_w, ss_h, sp_w, sp_h, data = args
        sprite_bin = self.__sprite_bin

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
        offset = pos[0] * sp_w, pos[1] * sp_h
        matrix = self.__matrix.get_rect(*rect)
        # event.emit('tilematrix.sector.created.before', matrix)
        sector_ = TileMatrixSector(self, offset, matrix,
                                   pos, self.__tile_size, self.__vaults,
                                   sprite_bin, self.show_sector_coords)
        sector_.pos = offset
        # print sector_.pos
        with self.lock:
            # Only attach sector_ if really necessary.
            # TODO Find a smarter solution not having to create it in the first way!
            # if self.show_sector_coords or sector_.get_layers():
            sector_.add_to(self.__sector_node)
            data[1] = sector_
            # Only update if already present.
            if key in self.__last_visible_sectors:
                self.__last_visible_sectors[key][1] = sector_
            event.emit('tilematrix.sector.created.after', sector_)
        # TODO can we somehow sync animations of same tiles?
        # del sector_
        return sector_

    def __housekeeping(self):
        for key, data in self.__sector_status.copy().iteritems():
            wanted, sector, init_args = data['wanted'], data['sector'], data['init_args']
            if not wanted and sector is not None:
                self.__drop_sector(sector)
                data['sector'] = None
            elif wanted and sector is None:
                data['sector'] = self.__create_sector(*init_args)
            if self.display.frame_length_clock.get_time() > 30:
                break

    def pause_housekeeping(self):
        self.ticker.pause()

    def unpause_housekeeping(self):
        self.ticker.unpause()

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
            return

        # Catch deleted sprites in temporary bin for eventual re-use.
        # sprite_bin = self.__sprite_bin

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
            sector_ = data[1]
            if sector_ is True:
                if key in self.__sector_status:
                    self.__sector_status[key]['wanted'] = False
                data[1] = None
            elif sector_ is not None:
                # event.emit('tilematrix.sector.dropped.before', sector_)
                # print 'remove sector_ instance from display:', key, data
                # print len(sector_.get_all_sprites())
                # for key, sprites in sector_.get_all_sprites().iteritems():
                #     try:
                #         sprite_bin[key].extend(sprites)
                #     except KeyError:
                #         sprite_bin[key] = sprites
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
                # sector_.remove_from_parent()  # TODO move this removal into a idle housekeeping task.
                # self.ticker.add(self.__drop_sectors, 1000, onetime=True, dropable=False)
                # self.__sector_drop_list.append(sector_)
                try:
                    self.__sector_status[key]['wanted'] = False
                except KeyError:
                    self.__sector_status[key] = dict(
                        sector=sector_,
                        wanted=False,
                        init_args=None,
                    )
                data[1] = None
                # For now nobody needs this.
                # event.emit('tilematrix.sector.dropped.after', sector_)
            del sector_

        # Handle sectors to hold.
        for key in keys_to_be_held:
            data = last_visible_sectors[key]
            # Copy instance into new view grid.
            # print 'keep sector instance on display', key, data
            sectors_to_display[key][1] = data[1]
            try:
                self.__sector_status[key]['wanted'] = True
            except KeyError:
                self.__sector_status[key] = dict(
                    sector=data[1],
                    wanted=True,
                    init_args=None,
                )

        # if not self.lock.acquire(False):
        #     return

        # Handle sectors new to display.
        # matrix__get_rect = self.__matrix.get_rect
        for key in keys_to_be_added:
            data = sectors_to_display[key]
            if data[1] is None:
                # # print 'create sector instance on display:', key, data
                # pos = key  # map(int, key.split(','))
                # # Try to re-use sprites-to-be-deleted from bin.
                # rect = (pos[0] * ss_w, pos[1] * ss_h, ss_w, ss_h)
                # # NOTE Enable this loop for debugging only!
                # # for key, vals in sprite_bin.iteritems():
                # #     # print key
                # #     for val in vals:
                # #         # print val.vault.name, val.matrix_id
                # #         if val.vault.name != val.matrix_id:
                # #             print 'found sprite %s with wrong matrix_id %s.' % (val.vault.name, val.matrix_id)
                # #             exit()
                # #         if val.matrix_id != key:
                # #             print 'found wrong sprite %s in bin %s.' % (val.matrix_id, key)
                # #             exit()
                # offset = pos[0] * sp_w, pos[1] * sp_h
                # matrix = matrix__get_rect(*rect)
                # # event.emit('tilematrix.sector.created.before', matrix)
                # sector_ = TileMatrixSector(self, offset, matrix,
                #                            pos, self.__tile_size, self.__vaults,
                #                            sprite_bin, self.show_sector_coords)
                # sector_.pos = offset
                # # print sector_.pos
                # # Only attach sector_ if really necessary.
                # # TODO Find a smarter solution not having to create it in the first way!
                # # if self.show_sector_coords or sector_.get_layers():
                # sector_.add_to(self.__sector_node)
                # data[1] = sector_
                # event.emit('tilematrix.sector.created.after', sector_)
                # # TODO can we somehow sync animations of same tiles?
                # del sector_
                data[1] = True
                # self.__sector_create_list.append((key, ss_w, ss_h, sp_w, sp_h, data))
                try:
                    self.__sector_status[key]['wanted'] = True
                except KeyError:
                    self.__sector_status[key] = dict(
                        sector=None,
                        wanted=True,
                        init_args=(key, ss_w, ss_h, sp_w, sp_h, data),
                    )

        self.__last_visible_sectors = sectors_to_display

        # self.lock.release()

    def get_tile_id_at(self, x, y, z=None):
        value = self.__matrix.get_point(x, y, z)
        if value is not None:
            if type(value) is dict:
                return value.copy()
            else:
                return value
        return None

    def _get_tile_sector_at(self, x, y):
        s_w, s_h = self.__sector_size
        s_x = x // s_w
        s_y = y // s_h
        sector = self.__last_visible_sectors.get((s_x, s_y), [None, None])[1]
        # print sector
        # print self.__last_visible_sectors.get((s_x, s_y))
        # print self.__sector_status.get((s_x, s_y))
        return sector if sector is not True else None

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

    def set_tiles_at(self, points):
        sector_points = dict()
        matrix__get_point = self.__matrix.get_point
        matrix__set_point = self.__matrix.set_point
        get_tile_sector_at = self._get_tile_sector_at
        for x, y, z, id in points:
            new_point_data = (x, y, z, id)
            old_point = matrix__get_point(*new_point_data[:2])
            if z in old_point and old_point[z] == id:
                continue
            sector = get_tile_sector_at(x, y)
            if sector is not None:
                try:
                    point_list = sector_points[sector]
                except KeyError:
                    point_list = sector_points[sector] = []
                s_w, s_h = self.__sector_size
                s_x = x // s_w
                s_y = y // s_h
                x -= s_x * s_w
                y -= s_y * s_h
                point_list.append((x, y, z, id))
            # else:
            #     raise SectorNotAvailableException()
            matrix__set_point(*new_point_data)
        # print len(sector_points)
        for sector, point_list in sector_points.iteritems():
            sector.set_sprites_at(point_list)

    def on_node_added(self, *args, **kwargs):
        super(TileMatrix, self).on_node_added(*args, **kwargs)
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

    def get_sector_pos(self, x, y):
        s_w, s_h = self.__sector_size
        s_x = x // s_w
        s_y = y // s_h
        return s_x, s_y

    def translate_to_sector_pos(self, x, y):
        s_w, s_h = self.__sector_size
        s_x, s_y = self.get_sector_pos(x, y)
        x -= s_x * s_w
        y -= s_y * s_h
        return x, y

    def add_layer(self, z):
        if z in self.__layers:
            raise Exception('Layer does alreay exist: %s' % z)
        layer = Node(name='TileMatrixLayer[%d]' % z)
        layer.order_matters = False
        if z in self.__layer_config:
            order = self.__layer_config[z].get('reorder', z)
            # print self.__layer_config
        else:
            order = z
        # print z, order
        layer.set_order_pos(order)
        layer.add_to(self)
        try:
            alpha = self.__layer_config[z]['alpha']
            layer.set_alpha(alpha)
        except KeyError:
            pass
        self.__layers[z] = layer
        return layer

    def get_layer(self, z, auto_create=False):
        try:
            return self.__layers[z]
        except KeyError:
            if auto_create:
                return self.add_layer(z)
            else:
                return None

    def remove_layer(self, z):
        if z not in self.__layers:
            raise Exception('Layer does not exist: %s' % z)
        self.__layers[z].remove_from_parent()
        del self.__layers[z]

    def get_layers(self):
        return self.__layers

    def set_alpha_of_layer(self, z, value):
        try:
            self.__layer_config[z]['alpha'] = value
        except KeyError:
            self.__layer_config[z] = dict(alpha=value)
        try:
            self.__layers[z].set_alpha(value)
        except KeyError:
            pass

    # @dump_args
    def find_in_sector(self, s_x, s_y, value):
        w, h = self.__sector_size
        results = self.__matrix.find_in_rect(s_x * w, s_y * h, w, h, value)
        return results

    def find_in_matrix_by_tilesheet(self, value):
        return self.__matrix.find_in_matrix_by_tilesheet(value)
