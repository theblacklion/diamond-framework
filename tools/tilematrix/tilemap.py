# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

import ConfigParser

import pygame

from diamond.scene import Scene
from diamond.tilematrix import TileMatrix
from diamond import event
from diamond.ticker import Ticker
from diamond.node import Node
from diamond.fps import Fps
from diamond.font import Font
from diamond.decorators import dump_args, time

from diamond.tools.tilematrix.selection import Selection
from diamond.tools.tilematrix.camera import Camera


class TilemapScene(Scene):

    def __setup_fps(self):
        screen_width = self.scene_manager.display.screen_size[0]
        fps_node = Node('fps node')
        fps_node.order_matters = False
        fps_node.add_to(self.root_node)
        fps_node.set_order_pos(1000)
        fps = Fps(ticker=self.ticker, details=True)
        fps.set_alpha(75)
        fps.set_background_color(0, 0, 0, 230)
        fps.set_background_border(3)
        fps.add_to(fps_node)
        fps.set_align_box(screen_width, 0, 'right')

    def __setup_layer_hud(self):
        screen_width = self.scene_manager.display.screen_size[0]
        node = Node('layer hud node')
        node.order_matters = False
        node.add_to(self.root_node)
        node.set_order_pos(1000)
        hud = Font()
        hud.set_alpha(75)
        hud.set_background_color(0, 0, 0, 230)
        hud.set_background_border(3)
        hud.add_to(node)
        hud.set_align_box(screen_width, 0, 'center')
        self.layer_hud = hud

    def setup(self, shared_data):
        super(TilemapScene, self).setup()
        self.shared_data = shared_data
        self.add_default_listeners()

        self.ticker = Ticker()
        self.camera_ticker = Ticker()
        self.camera_ticker.is_threaded = False  # Keep in sync with display.
        self.bind(self.ticker, self.camera_ticker)

        self.__setup_fps()
        self.__setup_layer_hud()

        tilematrix = TileMatrix()
        tilematrix.load_config(shared_data['config_file'])
        tilematrix.show_sector_coords = True
        tilematrix.add_to(self.root_node)
        self.tilematrix = tilematrix

        # We don't hold a ref to our camera - it holds this scene already and
        # would result in the gc not being able to clean us up properly.
        camera = Camera(tilematrix, self)
        self.camera_ticker.add(camera.tick, 16)

        self.__default_cursor = pygame.mouse.get_cursor()
        self._cursor_pos = (0, 0)

        config = ConfigParser.ConfigParser()
        config.read(shared_data['config_file'])
        self.layer_names = list([(int(z), id) for z, id in config.items('layer.names')])
        self.layer_name_index = -1
        self.tilematrix_z = None
        self.use_layer(self.layer_name_index)

        self.selection = Selection(self.root_node)
        self.selection.add_tilematrix(tilematrix)
        self.selection.skip_empty_tiles = False

        self.history = []
        self.history_pos = 0

        # TODO Make sure that specific events only fire in specific situations.
        #      E.g. undo/redo should never fire while having an active selection.
        self.bind(
            event.add_listener(self.__on_mouse_motion_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.MOUSEMOTION),
            event.add_listener(self.__on_switch_scene_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_SPACE),
            event.add_listener(self.__on_mouse_button_pressed_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.MOUSEBUTTONDOWN),
            event.add_listener(self.__on_mouse_button_released_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.MOUSEBUTTONUP),
            event.add_listener(self.__on_next_layer_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_PLUS),
            event.add_listener(self.__on_previous_layer_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_MINUS),
            event.add_listener(self.__on_save_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_s),
            event.add_listener(self.__on_change_bg_color_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__in=(
                                   pygame.locals.K_2,
                                   pygame.locals.K_1,
                                   pygame.locals.K_3,
                                   pygame.locals.K_4,
                                   pygame.locals.K_5,
                                   pygame.locals.K_6,
                                   pygame.locals.K_7)),
            event.add_listener(self.__on_undo_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__mod__in=(pygame.locals.KMOD_NONE, pygame.locals.KMOD_NUM),
                               context__event__key__eq=pygame.locals.K_z),
            event.add_listener(self.__on_redo_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__mod__in=(pygame.locals.KMOD_LSHIFT, pygame.locals.KMOD_NUM | pygame.locals.KMOD_LSHIFT),
                               context__event__key__eq=pygame.locals.K_z),
            # TODO implement different draw methods: freehand, stamp, rectangle, ellipse/circle, fill selection
            # TODO implement selection methods: rectangle, ellipse/circle, add, substract
            # TODO implement: color picker
            # event.add_listener(self.__on_debug_event, 'scene.event.system'),
        )

    def hide(self):
        super(TilemapScene, self).hide()
        self.pause()

    def show(self):
        super(TilemapScene, self).show()
        self._cursor_pos = pygame.mouse.get_pos()
        self.unpause()

    def __on_debug_event(self, context):
        print(context)

    def __on_switch_scene_keyup_event(self, context):
        self.scene_manager.hide_scene('tilemap')
        self.scene_manager.show_scene('tilesheet')

    def draw_points(self, points):
        self.add_to_history(points)
        self.tilematrix.set_tiles_at(points)

    def __on_mouse_motion_event(self, context):
        '''
        Tracks mouse movements and drags the map around.
        Updates the selection while lmb is being pressed down.
        '''
        pos = context.event.pos
        # print 'pos =', pos
        self._cursor_pos = pos

        lmb_pressed = context.event.buttons == (1, 0, 0)
        rmb_pressed = context.event.buttons == (0, 0, 1)
        mmb_pressed = context.event.buttons == (0, 1, 0)

        if self.layer_name_index != -1 and (lmb_pressed or rmb_pressed):
            self.selection.end_selection(self.tilematrix.name, pos, translate_pos=True)
        elif mmb_pressed or (self.layer_name_index == -1 and (lmb_pressed or rmb_pressed)):
            self.tilematrix.set_pos_rel(*context.event.rel)

    def __on_mouse_button_pressed_event(self, context):
        pos = context.event.pos
        # print 'pos =', pos

        lmb_pressed = context.event.button == 1
        rmb_pressed = context.event.button == 3

        if self.layer_name_index != -1 and (lmb_pressed or rmb_pressed):
            if lmb_pressed:
                pygame.mouse.set_cursor(*pygame.cursors.ball)
            elif rmb_pressed:
                pygame.mouse.set_cursor(*pygame.cursors.diamond)
            self.selection.begin_selection(self.tilematrix.name, pos, translate_pos=True)

    def __on_mouse_button_released_event(self, context):
        pos = context.event.pos
        # print 'pos =', pos

        lmb_pressed = context.event.button == 1
        rmb_pressed = context.event.button == 3

        if self.layer_name_index != -1 and (lmb_pressed or rmb_pressed):
            # TODO should we increase the selection to a minimum size of a 2x2 quad if its an autotile a?
            #      If yes also do this within the self.__on_mouse_motion_event() method.
            self.selection.end_selection(self.tilematrix.name, pos, translate_pos=True)
            # print self.shared_data
            selection = self.selection.get_selection(self.tilematrix.name)
            # print 'selection =', selection
            fill_pool = self.shared_data['selection']
            print('fill_pool =', fill_pool)

            self.selection.clear_selection(self.tilematrix.name)

            if rmb_pressed or fill_pool is None:
                fill_alias = ''
                fill_points = {(0, 0): None}
            else:
                fill_alias = fill_pool['alias']
                fill_points = fill_pool['points']

            # Find rect of all points.
            x = min(pos[0] for pos in fill_points)
            y = min(pos[1] for pos in fill_points)
            w = max(pos[0] for pos in fill_points) - x + 1
            h = max(pos[1] for pos in fill_points) - y + 1
            fill_rect = pygame.Rect(x, y, w, h)
            # print 'fill_rect =', fill_rect

            selection_points = selection.keys()
            # print 'selection_points =', selection_points
            x = min(pos[0] for pos in selection_points)
            y = min(pos[1] for pos in selection_points)
            w = max(pos[0] for pos in selection_points) - x + 1
            h = max(pos[1] for pos in selection_points) - y + 1
            selection_rect = pygame.Rect(x, y, w, h)
            # print 'selection_rect =', selection_rect

            draw_points = []

            first_point = fill_points.values()[0]
            if len(fill_points) == 1 and len(selection_points) > 1 and first_point is not None and first_point.startswith(':') and first_point.endswith(':inner'):
                autotile_group_id = first_point[len(': :'):-len(':inner')]
                print('autotile_group_id =', autotile_group_id)
                if first_point.startswith(':A:'):
                    for s_x, s_y in selection_points:
                        id = None
                        if s_x > x and s_x < x + w - 1 and s_y > y and s_y < y + h - 1:
                            id = '%s/:A:%s:m' % (fill_alias, autotile_group_id)
                        elif s_x == x and s_y == y:
                            id = '%s/:A:%s:tl' % (fill_alias, autotile_group_id)
                        elif s_x == x + w - 1 and s_y == y:
                            id = '%s/:A:%s:tr' % (fill_alias, autotile_group_id)
                        elif s_x == x and s_y == y + h - 1:
                            id = '%s/:A:%s:bl' % (fill_alias, autotile_group_id)
                        elif s_x == x + w - 1 and s_y == y + h - 1:
                            id = '%s/:A:%s:br' % (fill_alias, autotile_group_id)
                        elif s_x == x:
                            id = '%s/:A:%s:l' % (fill_alias, autotile_group_id)
                        elif s_x == x + w - 1:
                            id = '%s/:A:%s:r' % (fill_alias, autotile_group_id)
                        elif s_y == y:
                            id = '%s/:A:%s:t' % (fill_alias, autotile_group_id)
                        elif s_y == y + h - 1:
                            id = '%s/:A:%s:b' % (fill_alias, autotile_group_id)
                        draw_points.append((s_x, s_y, self.tilematrix_z, id))
                elif first_point.startswith(':B:'):
                    pass
                else:
                    raise Exception('Unknown autotile type:' % first_point[1:2])
            else:
                # Normalize points of fill pattern.
                fill_points = dict(((key[0] - fill_rect.x, key[1] - fill_rect.y), val) for key, val in fill_points.iteritems())
                # print 'fill_points =', fill_points

                normalize_x = lambda x: (x - selection_rect.x) % fill_rect.w
                normalize_y = lambda y: (y - selection_rect.y) % fill_rect.h
                for s_x, s_y in selection_points:
                    x = normalize_x(s_x)
                    y = normalize_y(s_y)
                    id = fill_points.get((x, y), None)
                    # print (s_x, s_y), (x, y), id
                    if fill_alias and id is not None:
                        id = '%s/%s' % (fill_alias, id)
                    draw_points.append((s_x, s_y, self.tilematrix_z, id))

            self.draw_points(draw_points)
            if self.layer_name_index != -1:
                pygame.mouse.set_cursor(*pygame.cursors.tri_left)
            else:
                pygame.mouse.set_cursor(*self.__default_cursor)

    def use_layer(self, layer_name_index, hide_inactive_passability_layer=False):
        if layer_name_index >= 0 and layer_name_index < len(self.layer_names):
            pygame.mouse.set_cursor(*pygame.cursors.tri_left)
            self.tilematrix_z = self.layer_names[layer_name_index][0]
            self.layer_hud.set_text('Current layer: %d %s' % self.layer_names[layer_name_index])
            self.layer_name_index = layer_name_index
            layer = self.layer_names[layer_name_index][0]
            for z, name in self.layer_names:
                # print z, name
                if z == layer:
                    self.tilematrix.set_alpha_of_layer(z, 100)
                elif 'passability' in name and hide_inactive_passability_layer:
                    self.tilematrix.set_alpha_of_layer(z, 0)
                else:
                    self.tilematrix.set_alpha_of_layer(z, 30)
        elif layer_name_index == -1:
            pygame.mouse.set_cursor(*self.__default_cursor)
            self.layer_hud.set_text('Showing all layers.')
            self.layer_name_index = layer_name_index
            for z, name in self.layer_names:
                # print z, name
                if 'passability' in name and hide_inactive_passability_layer:
                    self.tilematrix.set_alpha_of_layer(z, 0)
                else:
                    self.tilematrix.set_alpha_of_layer(z, 100)

    def __on_next_layer_keyup_event(self, context):
        self.use_layer(self.layer_name_index + 1)

    def __on_previous_layer_keyup_event(self, context):
        self.use_layer(self.layer_name_index - 1)

    def __on_save_keyup_event(self, context):
        self.tilematrix.save_matrix()

    def __on_change_bg_color_keyup_event(self, context):
        # TODO Move this into a class var.
        colors = {
            '49': (0.0, 0.0, 0.0, 1.0),
            '50': (1.0, 0.0, 0.0, 1.0),
            '51': (0.0, 1.0, 0.0, 1.0),
            '52': (0.0, 0.0, 1.0, 1.0),
            '53': (1.0, 0.0, 1.0, 1.0),
            '54': (0.0, 1.0, 1.0, 1.0),
            '55': (1.0, 1.0, 0.0, 1.0),
        }
        key = str(context.event.key)
        if key in colors:
            self.scene_manager.display.set_gl_clear_color(*colors[key])

    # @dump_args
    def __on_undo_keyup_event(self, context):
        history = self.history
        pos = self.history_pos
        if pos == 0:
            return
        points = history[pos - 1]['before']
        self.tilematrix.set_tiles_at(points)
        self.history_pos -= 1

    # @dump_args
    def __on_redo_keyup_event(self, context):
        history = self.history
        pos = self.history_pos
        if pos == len(history):
            return
        points = history[pos]['after']
        self.tilematrix.set_tiles_at(points)
        self.history_pos += 1

    # @dump_args
    def add_to_history(self, points):
        history = self.history
        pos = self.history_pos
        del history[pos:]
        backup = []
        tilematrix__get_tile_id_at = self.tilematrix.get_tile_id_at
        for x, y, z, value in points:
            backup.append((x, y, z, tilematrix__get_tile_id_at(x, y, z)))
        history.append(dict(
            before=backup,
            after=points,
        ))
        self.history_pos += 1
