# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

import os
import sys
import ConfigParser
from collections import OrderedDict
from math import ceil, floor

from diamond import pyglet
from diamond.rect import Rect
from diamond.vault import Vault

from diamond.matrix import Matrix
from diamond.node import Node

from diamond.decorators import time
from diamond.clock import Timer


class DummyFrame(object):
    rect = [0, 0, 0, 0]


class TileMatrixSector(object):

    # TODO REWORK!!!
    # we need an index of all the sprites we place in the vertex list.
    # then we can modify vertex lists without sparse data.
    # replace operation would then replace in place..
    # remove operation would set the color and texture coords to 0.
    # set operation would search for an empty place or add a new one.
    # a periodic scan should remove all sparse data. perhaps user driven event?

    def __init__(self, vaults, batch, group, matrices, matrix_size, tile_size):
        super(TileMatrixSector, self).__init__()

        self._vaults = vaults
        self._tile_size = tile_size
        self._matrices = matrices
        self._matrix_size = matrix_size
        self._sprite_data = sprite_data = self._gather_sprite_data(matrices, vaults)
        self._vertex_lists = dict()
        self._opacity = 255
        self._rgb = (255, 255, 255)
        self._sprite_groups = dict()
        self._visible = True

        for sheet, matrix in matrices.iteritems():
            vault = vaults[sheet]
            texture = vault.image.get_texture()

            # Setup sprite group.
            blend_src = pyglet.gl.GL_SRC_ALPHA
            blend_dest = pyglet.gl.GL_ONE_MINUS_SRC_ALPHA
            sprite_group = pyglet.sprite.SpriteGroup(texture, blend_src, blend_dest, group)
            self._sprite_groups[sheet] = sprite_group

            tex_coords = self._gather_tex_cords(matrix, sprite_data[sheet], texture.height)
            # print len(tex_coords)
            # print len(self._flat_data)
            num_coords = 4 * len(matrix)
            # print num_coords
            # Setup vertex list.
            self._batch = batch
            self._vertex_lists[sheet] = self._batch.add(
                num_coords, pyglet.gl.GL_QUADS, sprite_group,
                'v2i/dynamic',
                'c4B', ('t3f', tex_coords)
            )

            # Update color.
            r, g, b = self._rgb
            self._vertex_lists[sheet].colors[:] = [r, g, b, int(self._opacity)] * 4 * len(matrix)

            # print self._vertex_list

        # Setup position.
        self._x = 0
        self._y = 0
        self._rect = Rect(
            self._x,
            self._y,
            matrix_size[0] * tile_size[0],
            matrix_size[1] * tile_size[1],
        )
        self._update_position()

    def __del__(self):
        # print('TileMatrixSector.__del__(%s)' % self)
        for vertex_list in self._vertex_lists.itervalues():
            if vertex_list is not None:
                vertex_list.delete()

    def _gather_sprite_data(self, matrices, vaults):
        sprite_data = dict()
        for sheet, matrix in matrices.iteritems():
            vault = vaults[sheet]
            result = dict()
            ids = set(matrix.values())
            ids.discard(-1)
            for id in ids:
                result[id] = vault.get_sprite(str(id)).get_action('none').get_frames()
            result[-1] = [DummyFrame()]
            sprite_data[sheet] = result
        return sprite_data

    def _gather_tex_cords(self, matrix, sprite_data, texture_height):
        coords = []
        for pos, id in matrix.iteritems():
            frame = sprite_data[id][0]  # TODO for now just take the first frame.
            # print pos, id, frame
            x, y, w, h = frame.rect
            # print frame.rect
            # Flip our y coord. TODO can't we do this somehow else?
            y = texture_height - y - h
            # bottom-left, bottom-right, top-right and top-left
            tex_coord = (
                x, y + h, 0.,  # bottom left
                x + w, y + h, 0.,  # bottom right
                x + w, y, 0.,  # top right
                x, y, 0.,  # top left
            )
            # print tex_coord
            coords.extend(tex_coord)
        return coords

    # @time
    def _update_position(self):
        x, y = self._x, self._y
        w, h = self._tile_size
        self._rect.x = x
        self._rect.y = y
        sprite_data = self._sprite_data
        for sheet, matrix in self._matrices.iteritems():
            vertices = []
            sprites = sprite_data[sheet]
            for pos, id in matrix.iteritems():
                # print frame
                if self._visible:
                    s_w, s_h = sprites[id][0].rect[2:]
                    x1 = int(x) + pos[0] * w
                    y1 = int(y) + pos[1] * h
                    x2 = x1 + s_w
                    y2 = y1 + s_h
                    vertices.extend([x1, y1, x2, y1, x2, y2, x1, y2])
                else:
                    vertices.extend([0, 0, 0, 0, 0, 0, 0, 0])
            self._vertex_lists[sheet].vertices[:] = vertices

    def _set_x(self, x):
        if x != self._x:
            self._x = x
            self._update_position()

    x = property(lambda self: self._x, _set_x)

    def _set_y(self, y):
        if y != self._y:
            self._y = y
            self._update_position()

    y = property(lambda self: self._y, _set_y)

    def set_position(self, x, y):
        self._x, self._y = x, y
        self._update_position()

    position = property(lambda self: (self._x, self._y),
                        lambda self, pos: self.set_position(*pos))

    rect = property(lambda self: self._rect)

    # @time
    def _set_visible(self, visible):
        if self._visible != visible:
            self._visible = visible
            self._update_position()

    visible = property(lambda self: self._visible, _set_visible)

    @time
    def set_tile(self, x, y, id):
        s_x, s_y, s_w = x, y, self._matrix_size[0]
        sheet, id = id.split('/')
        sprite_data = self._sprite_data[sheet]
        vault = self._vaults[sheet]
        if id not in sprite_data:
            sprite_data[id] = vault.get_sprite(str(id)).get_action('none').get_frames()
        frame = sprite_data[id][0]  # TODO for now just take the first frame.
        # print frame
        x, y, w, h = frame.rect
        # print frame.rect
        # bottom-left, bottom-right, top-right and top-left
        tex_coord = [
            x, y + h, 0.,  # bottom left
            x + w, y + h, 0.,  # bottom right
            x + w, y, 0.,  # top right
            x, y, 0.,  # top left
        ]
        # print 1, tex_coord
        # print 2, s_x, s_y, s_w
        pos = (s_w * s_y * 12 + s_x * 12)
        # print 3, len(self._vertex_list.tex_coords), pos
        vertex_list = self._vertex_lists[sheet]
        tex_coords = vertex_list.tex_coords
        tex_coords = tex_coords[:pos] + tex_coord + tex_coords[pos + 12:]
        # print 4, len(tex_coords)
        vertex_list.tex_coords[:] = tex_coords


class TileMatrixLayer(Node):

    def __init__(self, suborder_id, vaults):
        super(TileMatrixLayer, self).__init__()
        # print 'TileMatrixLayer.__init__', self, suborder_id
        self.order_id = suborder_id
        self._vaults = vaults
        self._sectors = dict()

    # def _set_suborder_id(self, id):
    #     self._suborder_id = id
    #     # TODO Update group id of this node by placing id after the comma of the node.

    # suborder_id = property(lambda self: self._suborder_id, _set_suborder_id)

    def has_sector(self, id):
        return id in self._sectors

    # @time
    def add_sector(self, id, x, y, matrices, matrix_size, tile_size):
        batch = self.window._batch
        group = self._sprite_group
        # for sheet, matrix in matrices.iteritems():
        #     print 'sheet', sheet, matrix
        # print 'sector real pos =', self._x_real, self._y_real
        sector = TileMatrixSector(self._vaults, batch, group, matrices, matrix_size, tile_size)
        sector.visible = self._inherited_visibility
        # sector.set_position(self._x_real + x, self._y_real + y)
        sector.set_position(x, y)
        self._sectors[id] = (x, y, sector)

    # @time
    def remove_sector(self, id):
        del self._sectors[id]

    def _set_visible(self, visible):
        super(TileMatrixLayer, self)._set_visible(visible)
        for x, y, sector in self._sectors.itervalues():
            sector.visible = self._inherited_visibility

    # @time
    # def _update_real_position(self):
    #     super(TileMatrixLayer, self)._update_real_position()
    #     # print len(self._sectors)
    #     for x, y, sector in self._sectors.itervalues():
    #         # print x, y, sector
    #         old_pos = sector.position
    #         # new_pos = self._x_real + x, self._y_real + y
    #         new_pos = x, y
    #         if new_pos != old_pos:
    #             sector.set_position(*new_pos)


class TileMatrix(Node):

    def __init__(self):
        super(TileMatrix, self).__init__()
        self.__config = ConfigParser.ConfigParser()

        self.__vaults = dict()
        self.__default_sheet = None
        self.__tile_size = 32, 32  # Never go less than 4x4 or doom awaits you!
        self.__sector_size = 10, 10  # Default for visual sectors.

        matrix = Matrix()
        matrix.set_sector_size(*self.__sector_size)  # Default until a config is being loaded.
        self.__matrix = matrix
        # For debugging. DISABLE ME!
        # matrix.set_default_value({0: '72'})

        self.__layers = dict()
        self.__layer_config = dict()

        self.__last_map_pos = (None, None), (None, None)
        self.__last_matrix_rect = None

    def add_sheet(self, sheet_vault, alias=None):
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
        self.__vaults[alias] = vault
        filename = os.path.relpath(sheet_vault.__file__, os.getcwd())
        filename = os.path.splitext(filename)[0]  # Throw away extension - Python shall decide.
        if not self.__config.has_section('tilesheets'):
            self.__config.add_section('tilesheets')
        self.__config.set('tilesheets', alias, filename)

        if not self.__default_sheet:
            self.__default_sheet = self.__vaults.keys()[0]

    def load_matrix(self, path, config_file='config.ini'):
        self.__matrix.set_data_path(path, config_file)
        if not self.__config.has_section('matrix'):
            self.__config.add_section('matrix')
        self.__config.set('matrix', 'data_path', path)

    def load_sheet_file(self, filename, alias=None):
        sheet_path = os.path.dirname(filename)
        sheet_file = os.path.basename(filename)
        if sheet_path:
            sys.path.insert(0, os.path.abspath(sheet_path))
        sheet_file = os.path.splitext(sheet_file)[0]  # Throw away extension - Python shall decide.
        module = __import__(sheet_file, globals(), locals(), [], -1)
        self.add_sheet(module, alias)

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

    # @time
    def update_sectors(self):
        # timer = Timer()
        # timer.start()

        # Gather the boundaries.
        m_x, m_y = map(float, self.real_position)  # real position of tilematrix
        t_w, t_h = map(float, (self.__tile_size))  # tile size
        s_w, s_h = map(float, (self.__sector_size))  # sector size
        w_w, w_h = map(float, (self.window.width, self.window.height))  # window size
        # m_w, m_h = map(int, (ceil(w_w / t_w), ceil(w_h / t_h)))  # map size

        # Calculate all necessary sector rects.
        top_left = map(floor, (-m_x / t_w, -m_y / t_h))
        bottom_right = map(ceil, ((-m_x + w_w) / t_w, (-m_y + w_h) / t_h))
        o_x, o_y = ceil(top_left[0] % s_w / s_w) * s_w, ceil(top_left[1] % s_h / s_h) * s_h
        m_w, m_h = (bottom_right[0] - top_left[0] + o_x), (bottom_right[1] - top_left[1] + o_y)
        # m_w, m_h = (bottom_right[0] - top_left[0]), (bottom_right[1] - top_left[1])
        s_num_w, s_num_h = map(ceil, (m_w / s_w, m_h / s_h))

        # print(m_x, t_w, m_y, t_h)
        # print('tl =', top_left)
        # print(m_x, w_w, t_w, m_y, w_h, t_h)
        # print('br =', bottom_right)
        # print('s_w, s_h =', s_w, s_h)
        # print('o_x, o_y =', o_x, o_y)
        # print('num horiz tiles =', m_w)
        # print('num vert tiles =', m_h)
        # print('num horiz sectors =', s_num_w)
        # print('num vert sectors =', s_num_h)

        # And make them ints.
        top_left = map(int, top_left)
        bottom_right = map(int, bottom_right)
        t_w, t_h = map(int, (t_w, t_h))
        m_w, m_h = map(int, (m_w, m_h))
        s_w, s_h = map(int, (s_w, s_h))
        s_num_w, s_num_h = map(int, (s_num_w, s_num_h))

        # Guess our default if no sheet is being mentioned in a coord.
        default_sheet = self.__default_sheet

        # timer.stop()
        # print 1, timer.result
        # timer.start()

        matrix_rect = (
            top_left[0] // s_w * s_w,
            top_left[1] // s_h * s_h,
            s_w * s_num_w,
            s_h * s_num_h,
        )
        if matrix_rect == self.__last_matrix_rect:
            return
        self.__last_matrix_rect = matrix_rect
        # Get the rect.
        matrix = self.__matrix.get_rect(*matrix_rect)
        # print matrix
        # print len(matrix[0]), len(matrix)

        # timer.stop()
        # print 2, timer.result
        # timer.start()

        # Separate layer and sector data.
        layer_data = dict()
        for y, row in enumerate(matrix):
            pos_y = (matrix_rect[1] + y) // s_h
            y = y % s_h
            for x, col in enumerate(row):
                if col is None:
                    continue
                pos_x = (matrix_rect[0] + x) // s_w
                x = x % s_w
                # print '*** sector', pos_x, pos_y

                # Separate data.
                # DISABLE THIS AFTER DEBUGGING!
                # if (x, y) == (0, 0):
                #     col = {0: '73'}
                # print x, y, col
                for layer_no, id in col.iteritems():
                    # Normalize data format.
                    if '/' not in id:
                        sheet = default_sheet
                    else:
                        sheet, id = id.split('/', 1)
                    # Ensure layer.
                    try:
                        layer_matrix = layer_data[layer_no]
                    except KeyError:
                        layer_matrix = layer_data[layer_no] = dict()
                    # Ensure sector.
                    try:
                        sector_matrix = layer_matrix[(pos_x, pos_y)]
                    except KeyError:
                        sector_matrix = layer_matrix[(pos_x, pos_y)] = dict()
                    # Set sector data.
                    try:
                        sector_matrix[sheet][x, y] = id
                    except KeyError:
                        sector_matrix[sheet] = {(x, y): id}

        # timer.stop()
        # print 3, timer.result
        # timer.start()

        # Build layers and sectors.
        layers = self.__layers
        vaults = self.__vaults
        required_sectors = set()
        for order_id, layer_data in layer_data.items():
            # print 'layer', order_id
            try:
                layer = layers[order_id]
            except KeyError:
                if order_id in self.__layer_config:
                    _order_id = self.__layer_config[order_id].get('reorder', order_id)
                else:
                    _order_id = order_id
                layer = layers[order_id] = TileMatrixLayer(_order_id, vaults)
                # print layer
                # We do this because we need a valid window and group for the next step.
                self.add_node(layer)
            for pos, sector_data in layer_data.iteritems():
                if not layer.has_sector(pos):
                    # print 12345, top_left, pos
                    x = pos[0] * t_w * s_w
                    y = pos[1] * t_h * s_h
                    # print 'sector', pos, x, y
                    layer.add_sector(pos, x, y, sector_data, self.__sector_size, self.__tile_size)
                required_sectors.add((order_id, pos))

        # timer.stop()
        # print 4, timer.result
        # timer.start()

        # return
        # print(required_sectors)
        # Cleanup sectors which are off the screen.
        for order_id, layer in layers.items():
            for id, data in layer._sectors.items():
                x, y, sector = data
                pos = sector.position

                sector_id = (order_id, (x // (t_w * s_w), y // (t_h * s_h)))
                # print sector_id

                if sector_id not in required_sectors:
                    # print('***********', id, data, pos, (w_w, w_h), (-t_w * s_w, -t_h * s_h))
                    # print('drop', id)
                    layer.remove_sector(id)

        # timer.stop()
        # print 5, timer.result

    # @time
    def rebuild(self):
        # Throw away old layers.
        self.remove_all()
        self.__layers.clear()
        self.__last_map_pos = (None, None), (None, None)
        self.__last_matrix_rect = None

        self.update_sectors()

    # @time
    def add_to(self, node):
        super(TileMatrix, self).add_to(node)
        if not self._child_nodes:
            self.rebuild()
            # self._update_real_position()

    def set_sector_size(self, width, height):
        self.__sector_size = width, height
        if self.window:
            self.rebuild()

    # @time
    def _update_real_position(self):
        super(TileMatrix, self)._update_real_position()
        if not self.window:
            return

        x, y = map(lambda v: -v, self.real_position)
        t_w, t_h = self.__tile_size
        # s_w, s_h = self.__sector_size

        w = t_w  # * s_w
        h = t_h  # * s_h

        last_map_pos, last_map_coords = self.__last_map_pos
        if x > last_map_coords[0]:
            crp_x = ceil(x / float(w))
        else:
            crp_x = floor(x / float(w))
        if y > last_map_coords[1]:
            crp_y = ceil(y / float(h))
        else:
            crp_y = floor(y / float(h))
        cur_map_pos = crp_x, crp_y

        # print (cur_map_pos, (x, y)), self.__last_map_pos
        if last_map_pos != cur_map_pos:
            # print (cur_map_pos, (x, y)), self.__last_map_pos
            self.update_sectors()
            self.__last_map_pos = cur_map_pos, (x, y)

    def find_in_matrix_by_tilesheet(self, value):
        return self.__matrix.find_in_matrix_by_tilesheet(value)

    # @time
    def get_layer(self, z):
        layers = self.__layers
        vaults = self.__vaults
        try:
            layer = layers[z]
        except KeyError:
            if z in self.__layer_config:
                order = self.__layer_config[z].get('reorder', z)
            else:
                order = z
            layer = layers[z] = TileMatrixLayer(order, vaults)
            # print layer
            self.add_node(layer)
        return layer

    def translate_to_pos(self, x, y):
        tile_size = self.__tile_size
        return x * tile_size[0], y * tile_size[1]

    def get_tile_id_at(self, x, y, z=None):
        value = self.__matrix.get_point(x, y, z)
        if value is not None:
            if type(value) is dict:
                return value.copy()
            else:
                return value
        return None
