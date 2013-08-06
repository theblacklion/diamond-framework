# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

import os
import ConfigParser
import csv

from diamond.decorators import time


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

    def __set_point(self, x, y, z, data):
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

    # @time
    def set_point(self, x, y, z, data):
        # First make sure that our sector has been loaded.
        s_w, s_h = self.__sector_size
        s_x = x // s_w
        s_y = y // s_h
        self.__ensure_sector_loaded(s_x, s_y)
        self.__set_point(x, y, z, data)

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
                        self.__set_point(x, y, z, str(data))

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
