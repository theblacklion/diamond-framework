# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

import os
import ConfigParser
import csv

from diamond import event
from diamond.decorators import time


class Matrix(object):

    def __init__(self):
        self._matrix = dict()
        self._top = 0
        self._bottom = 0
        self._left = 0
        self._right = 0
        self._default_value = None
        self._sector_size = 10, 10  # Is being filled from config file.
        self._data_path = None
        self._sectors_loaded = set()

    def _set_default_value(self, value):
        assert type(value) is dict or value is None
        self._default_value = value

    default_value = property(lambda self: self._default_value, _set_default_value)

    def _set_sector_size(self, width, height):
        if self._data_path is not None:
            raise Exception('Cannot change sector size after setting a data path.')
        self._sector_size = max(1, width), max(1, height)

    sector_size = property(lambda self: self._sector_size, _set_sector_size)

    def _set_data_path(self, path):
        self._data_path = path
        config_file = 'config.ini'
        config = ConfigParser.ConfigParser()
        config.read(os.path.join(path, config_file))
        self._sector_size = map(int, config.get('general', 'sector_size').split(','))
        index_filename = os.path.join(self._data_path, 'b.csv')
        if os.path.exists(index_filename):
            reader = csv.reader(open(index_filename), skipinitialspace=True)
            data = map(int, reader.next())
            self._top, self._left, self._bottom, self._right = data

    data_path = property(lambda self: self._data_path, _set_data_path)

    top = property(lambda self: self._top)
    bottom = property(lambda self: self._bottom)
    left = property(lambda self: self._left)
    right = property(lambda self: self._right)
    boundaries = property(lambda self: (self._left, self._top, self._right, self._bottom))
    rect = property(lambda self: (self._left, self._top,
                                  self._right - self._left, self._bottom - self._top))

    def _point_cmp_key(self, item):
        return int('%05d%05d%05d' % (item[2], item[1], item[0]))

    # TODO REWORK!
    # @time
    def save_data(self):
        if not self._data_path:
            return
        s_w, s_h = self._sector_size
        sectors = dict((tuple(map(int, id.split(','))), []) for id in self._sectors_loaded)
        for (x, y), data in self._matrix.iteritems():
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
            filename = os.path.join(self._data_path, 's.%s.csv' % id)
            # print filename
            # print points
            if points:
                points = sorted(points, key=self._point_cmp_key)
                # print points
                writer = csv.writer(open(filename, 'w'))
                for point in points:
                    writer.writerow(point)
            else:
                if os.path.exists(filename):
                    os.remove(filename)
        event.emit('matrix.data.saved', self)

    def _ensure_sector_loaded(self, s_x, s_y):
        id = '%d,%d' % (s_x, s_y)
        if id in self._sectors_loaded:
            return
        self._sectors_loaded.add(id)
        # If possible try loading data from disk.
        if self._data_path:
            filename = os.path.join(self._data_path, 's.%s.csv' % id)
            # print filename
            if os.path.exists(filename):
                s_w, s_h = self._sector_size
                left, top, right, bottom = self.boundaries
                matrix = self._matrix
                for row in csv.reader(open(filename), skipinitialspace=True):
                    x, y, z = map(int, row[0:3])
                    data = row[3]
                    # print (x, y, z), data
                    x += s_x * s_w
                    y += s_y * s_h
                    # print (x, y, z), data
                    try:
                        matrix[z][(x, y)] = data
                    except KeyError:
                        matrix[z] = {(x, y): data}

    # @time
    def get_point(self, x, y, z):
        s_w, s_h = self._sector_size
        s_x = x // s_w
        s_y = y // s_h
        self._ensure_sector_loaded(s_x, s_y)
        pos = (x, y)
        data = self._matrix.get(z, {}).get(pos, None)
        return data

    def _set_point(self, x, y, z, data):
        self._top = min(self._top, y)
        self._left = min(self._left, x)
        self._bottom = max(self._bottom, y)
        self._right = max(self._right, x)
        # TODO track z axis min and max.
        pos = (x, y)
        if data is not None:
            # Set new point data.
            try:
                self._matrix[z][pos] = data
            except KeyError:
                self._matrix[z] = {pos: data}
            # print 'changed:', self._matrix[z][pos]
        else:
            # Remove old point data.
            try:
                del self._matrix[z][pos]
                # print 'removed:', self._matrix[z][pos]
            except KeyError:
                pass

    # @time
    def set_point(self, x, y, z, data):
        # First make sure that our sector has been loaded.
        s_w, s_h = self._sector_size
        s_x = x // s_w
        s_y = y // s_h
        self._ensure_sector_loaded(s_x, s_y)
        self._set_point(x, y, z, data)

    # @time
    def _get_rect(self, coords):
        default_value = self._default_value
        layers = {}

        if default_value is None:
            for layer_no, matrix in self._matrix.iteritems():
                result = {
                    coord: matrix[coord]
                    for coord in coords if coord in matrix
                }
                if result:
                    layers[layer_no] = result
        else:
            default_value = default_value.copy()
            for layer_no, matrix in self._matrix.iteritems():
                result = {
                    coord: matrix.get(coord, default_value)
                    for coord in coords
                }
                if result:
                    layers[layer_no] = result

        return layers

    # TODO deprecated?
    # @time
    # def get_sector(self, s_x, s_y):
    #     self._ensure_sector_loaded(s_x, s_y)
    #     s_w, s_h = self._sector_size
    #     x = s_x * s_w
    #     y = s_y * s_h
    #     range_x = xrange(x, x + s_w, 1)
    #     range_y = xrange(y, y + s_h, 1)
    #     return self._get_rect(range_x, range_y)

    # @time
    def get_rect(self, x, y, w, h):
        s_w, s_h = self._sector_size
        range_x = xrange(x, x + w)
        range_y = xrange(y, y + h)
        coords = set((x, y) for x in range_x for y in range_y)
        sectors_to_prefetch = set((x // s_w, y // s_h) for x, y in coords)
        # print sectors_to_prefetch
        [self._ensure_sector_loaded(*pos) for pos in sectors_to_prefetch]
        # print self._sectors_loaded
        return self._get_rect(coords)

    # @time
    # def find_in_rect(self, x, y, w, h, data):
    #     s_w, s_h = self._sector_size
    #     range_x = xrange(x, x + w)
    #     range_y = xrange(y, y + h)
    #     sectors_to_prefetch = set(
    #         (x // s_w, y // s_h)
    #         for x in range_x
    #         for y in range_y
    #     )
    #     # print sectors_to_prefetch
    #     [self._ensure_sector_loaded(*pos) for pos in sectors_to_prefetch]
    #     # print self._sectors_loaded
    #     matrix_get = self._matrix.get
    #     default_value = self._default_value
    #     if default_value is not None:
    #         copy = default_value.copy
    #     else:
    #         copy = lambda: None
    #     results = []
    #     results_append = results.append
    #     for y in range_y:
    #         for x in range_x:
    #             point = matrix_get((x, y), copy())
    #             if point is not None:
    #                 result = [key for key, val in point.iteritems() if val == data]
    #                 if result:
    #                     results_append((x, y, result[0]))
    #     # print results
    #     # exit()
    #     return results

    # def get_raw_matrix(self):
    #     return self._matrix
