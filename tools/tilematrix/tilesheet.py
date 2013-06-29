# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

from collections import OrderedDict

import pygame

from diamond.scene import Scene
from diamond.tilematrix import TileMatrix
from diamond import event

from diamond.tools.tilematrix.selection import Selection


class TilesheetScene(Scene):

    def setup(self, shared_data):
        super(TilesheetScene, self).setup()
        self.shared_data = shared_data
        self.add_default_listeners()

        s_width, s_height = self.scene_manager.display.screen_size
        self.screen_size = (s_width, s_height)

        self.tilemaps = OrderedDict()
        self.current_tilemap = None

        # self.root_node.set_clipping_region(
        #     0,
        #     0,
        #     s_width,
        #     s_height,
        # )

        self.selection = Selection(self.root_node)
        self.selection_mode = 'REPLACE'

        for alias, filename in shared_data['sheet_files']:
            tilematrix = TileMatrix(alias)
            tilematrix.hide()
            tilematrix.load_sheet_file(filename, alias)
            # tilematrix.show_sector_coords = True
            tilematrix.add_to(self.root_node)

            self.tilemaps[alias] = tilematrix

            vault = tilematrix.get_sheet(alias)
            tile_size = tilematrix.get_tile_size()

            self.selection.add_tilematrix(tilematrix)

            sprites = vault.get_sprites().copy()
            # print 'tile_size =', tile_size
            # print 'found %d sprites' % len(sprites)

            # TODO Remove all autotiles from the list.
            # if hasattr(sheet_module, 'autotiles'):
            #     for item in chain(*sheet_module.autotiles.values()):
            #         del sprites[item]

            rects = OrderedDict()
            # Gain map size from tiles found
            for sprite in sprites.itervalues():
                rects[sprite.name] = pygame.Rect(sprite.get_action('none').get_frame(0).rect)
            # print rects
            size_in_pixel = pygame.Rect(rects.values()[0]).unionall(rects.values()).size
            size_in_tiles = (size_in_pixel[0] / tile_size[0], size_in_pixel[1] / tile_size[1])
            # print size_in_pixel, size_in_tiles

            map_data = dict()
            # Put tiles in proper map position.
            overlapped_tiles = []
            for key, val in rects.iteritems():
                x, y = val.x / tile_size[0], val.y / tile_size[1]
                # print key, val, (x, y)
                pos = (x, y)
                if pos in map_data:
                    overlapped_tiles.append(key)
                else:
                    map_data[pos] = key

            # Append overlapped tiles at the bottom of the map.
            if overlapped_tiles:
                # print overlapped_tiles
                # First create an empty line as separator.
                cur_x, cur_y = 0, size_in_tiles[1]
                # Now add the overlapping tiles.
                for key in overlapped_tiles:
                    if key.startswith(':') and not key.endswith(':inner'):
                        continue
                    if cur_x >= size_in_tiles[0]:
                        cur_x = 0
                        cur_y += 1
                    map_data[(cur_x, cur_y)] = key
                    cur_x += 1
                size_in_tiles = size_in_tiles[0], cur_y + 1

            # print map_data

            points = [(key[0], key[1], 0, val) for key, val in map_data.iteritems()]
            # print points
            tilematrix.load_points(points)

            # UPDATE: We probably don't need it anymore.
            # Align sector to sheet size for faster movement. This also rebuilds
            # the matrix with the data loaded above.
            # print 'size_in_tiles =', size_in_tiles
            # tilematrix.set_sector_size(*size_in_tiles)

        iterator = iter(self.tilemaps)
        # iterator.next()
        self.set_current_tilemap(iterator.next())

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
            # TODO add event for rmb down without shift to clear selection.
            # TODO add event for rmb down with shift to remove selection at pos.
            event.add_listener(self.__on_lshift_key_pressed_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYDOWN,
                               context__event__key__eq=pygame.locals.K_LSHIFT),
            event.add_listener(self.__on_lshift_key_released_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_LSHIFT),
            event.add_listener(self.__on_next_layer_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__scene__selection_mode__eq='REPLACE',
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_PLUS),
            event.add_listener(self.__on_previous_layer_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__scene__selection_mode__eq='REPLACE',
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_MINUS),
            event.add_listener(self.__on_change_bg_color_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__in=(pygame.locals.K_1,
                                    pygame.locals.K_2, pygame.locals.K_3,
                                    pygame.locals.K_4, pygame.locals.K_5,
                                    pygame.locals.K_6, pygame.locals.K_7)),
            event.add_listener(self.__on_combine_frames_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__scene__selection_mode__eq='ADD',
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_c),
            event.add_listener(self.__on_uncombine_frames_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__scene__selection_mode__eq='REPLACE',
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_c),
            event.add_listener(self.__on_speedup_frames_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__scene__selection_mode__eq='ADD',
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_PLUS),
            event.add_listener(self.__on_slowdown_frames_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__scene__selection_mode__eq='ADD',
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_MINUS),
            event.add_listener(self.__on_equalize_frame_speed_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__scene__selection_mode__eq='ADD',
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__mod__eq=pygame.locals.KMOD_LSHIFT,
                               context__event__key__eq=pygame.locals.K_0),
            event.add_listener(self.__on_save_tilemap_vault_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_s),
            event.add_listener(self.__on_extract_autotile_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__mod__eq=pygame.locals.KMOD_LCTRL,
                               context__event__key__eq=pygame.locals.K_a),
        )

    def __on_switch_scene_keyup_event(self, context):
        self.scene_manager.hide_scene('tilesheet')
        self.scene_manager.show_scene('tilemap')

    def __on_lshift_key_pressed_event(self, context):
        self.selection_mode = 'ADD'
        # print self.selection_mode

    def __on_lshift_key_released_event(self, context):
        self.selection_mode = 'REPLACE'
        # print self.selection_mode

    def __on_next_layer_keyup_event(self, context):
        keys = self.tilemaps.keys()
        index = keys.index(self.current_tilemap)
        if index + 1 < len(keys):
            key = keys[index + 1]
            self.set_current_tilemap(key)

    def __on_previous_layer_keyup_event(self, context):
        keys = self.tilemaps.keys()
        index = keys.index(self.current_tilemap)
        if index - 1 >= 0:
            key = keys[index - 1]
            self.set_current_tilemap(key)

    def set_current_tilemap(self, alias):
        if self.current_tilemap == alias:
            return
        [tilematrix.hide() for tilematrix in self.tilemaps.itervalues()]
        tilematrix = self.tilemaps[alias]
        tilematrix.show()
        self.current_tilemap = alias
        self.current_tile_size = tilematrix.get_tile_size()
        self.current_tilemap_rect = tilematrix.get_virtual_rect().size
        self.selection.clear_selection(tilematrix.name)
        print 'Showing tilesheet: %s' % alias

    def __on_mouse_motion_event(self, context):
        '''
        Tracks mouse movements and drags the map around.
        Updates the selection while lmb is being pressed down.
        '''
        pos = context.event.pos
        # print 'pos =', pos

        tilemap = self.tilemaps[self.current_tilemap]
        # tile_size = self.current_tile_size

        # i_width, i_height = self.current_tilemap_rect
        # s_width, s_height = self.screen_size
        # # print self.current_tilemap_rect, self.screen_size

        # # Tolerance boundaries.
        # t_w, t_h = max(tile_size[0], 128), max(tile_size[1], 128)
        # p_x = min(1.0, max(0, (pos[0] - t_w)) / float(s_width - t_w * 2))
        # p_y = min(1.0, max(0, (pos[1] - t_h)) / float(s_height - t_h * 2))
        # # print p_x, p_y

        # x, y = max(0, (i_width - s_width)) * p_x * -1, max(0, (i_height - s_height)) * p_y * -1
        # # print x, y

        # tilemap.set_pos(int(x), int(y))

        lmb_pressed = context.event.buttons == (1, 0, 0)
        # rmb_pressed = context.event.buttons == (0, 0, 1)
        mmb_pressed = context.event.buttons == (0, 1, 0)

        if lmb_pressed:
            # print self.selection_mode
            if self.selection_mode == 'ADD':
                self.selection.add_selection(tilemap.name, [pos], translate_pos=True)
            else:
                self.selection.end_selection(tilemap.name, pos, translate_pos=True)
        elif mmb_pressed:
            tilemap.set_pos_rel(*context.event.rel)

    def __on_mouse_button_pressed_event(self, context):
        pos = context.event.pos
        # print 'pos =', pos

        lmb_pressed = context.event.button == 1
        # rmb_pressed = context.event.button == 3

        if lmb_pressed:
            tilemap = self.tilemaps[self.current_tilemap]
            # print self.selection_mode
            if self.selection_mode == 'ADD':
                self.selection.add_selection(tilemap.name, [pos], translate_pos=True)
            else:
                self.selection.begin_selection(tilemap.name, pos, translate_pos=True)

    def commit_selection(self):
        tilemap = self.tilemaps[self.current_tilemap]
        selection = self.selection.get_selection(tilemap.name)
        selection = dict((key, val[0]) for key, val in selection.iteritems())
        self.shared_data['selection'] = dict(
            alias=tilemap.name,
            points=selection,
        )
        # print self.shared_data

    def __on_mouse_button_released_event(self, context):
        pos = context.event.pos
        # print 'pos =', pos

        lmb_pressed = context.event.button == 1
        # rmb_pressed = context.event.button == 3

        if lmb_pressed:
            tilemap = self.tilemaps[self.current_tilemap]
            # print self.selection_mode
            if self.selection_mode == 'REPLACE':
                self.selection.end_selection(tilemap.name, pos, translate_pos=True)
            self.commit_selection()

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

    def __on_combine_frames_keyup_event(self, context):
        tilemap = self.tilemaps[self.current_tilemap]
        selection = self.selection.get_selection(tilemap.name).items()
        if not selection:
            return
        # print selection
        # id = selection[0][1][0]
        tile = tilemap.get_tile_at(*selection[0][0])[0]
        action = tile.vault.get_actions().items()[0][1]
        # print id
        # print tile
        # print tile.vault
        # print action
        # print 'current frames =',
        # print action.get_frames()
        for pos, layers in selection[1:]:
            tile_ = tilemap.get_tile_at(*pos)[0]
            action_ = tile_.vault.get_actions().items()[0][1]
            frames_ = action_.get_frames()
            # print frames_
            for frame in frames_:
                # print 'adding frame:', frame
                action.add_frame(frame.copy())
        # print 'all frames =',
        # print action.get_frames()
        tile.replace_vault(tile.vault)
        self.selection.clear_selection(tilemap.name)
        self.selection.add_selection(tilemap.name, [selection[0][0]], translate_pos=False)
        self.commit_selection()
        # TODO update sprites on all tilemaps!

    def __on_uncombine_frames_keyup_event(self, context):
        tilemap = self.tilemaps[self.current_tilemap]
        selection = self.selection.get_selection(tilemap.name).items()
        if not selection:
            return
        # print selection
        for pos, layers in selection:
            tile = tilemap.get_tile_at(*pos)[0]
            action = tile.vault.get_actions().items()[0][1]
            frame = action.get_frame(0)
            action.clear_frames()
            action.add_frame(frame.copy())
            tile.replace_vault(tile.vault)
        # TODO update sprites on all tilemaps!

    def __on_speedup_frames_keyup_event(self, context):
        tilemap = self.tilemaps[self.current_tilemap]
        selection = self.selection.get_selection(tilemap.name).items()
        if not selection:
            return
        # print selection
        for pos, layers in selection:
            tile = tilemap.get_tile_at(*pos)[0]
            action = tile.vault.get_actions().items()[0][1]
            for frame in action.get_frames():
                frame.duration -= 10
                frame.duration = max(10, frame.duration)
            tile.replace_vault(tile.vault)
        # TODO update sprites on all tilemaps!

    def __on_slowdown_frames_keyup_event(self, context):
        tilemap = self.tilemaps[self.current_tilemap]
        selection = self.selection.get_selection(tilemap.name).items()
        if not selection:
            return
        # print selection
        for pos, layers in selection:
            tile = tilemap.get_tile_at(*pos)[0]
            action = tile.vault.get_actions().items()[0][1]
            for frame in action.get_frames():
                frame.duration += 10
                frame.duration = min(60000, frame.duration)
            tile.replace_vault(tile.vault)
        # TODO update sprites on all tilemaps!

    def __on_equalize_frame_speed_keyup_event(self, context):
        tilemap = self.tilemaps[self.current_tilemap]
        selection = self.selection.get_selection(tilemap.name).items()
        if not selection:
            return
        # print selection
        duration = []
        for pos, layers in selection:
            tile = tilemap.get_tile_at(*pos)[0]
            action = tile.vault.get_actions().items()[0][1]
            for frame in action.get_frames():
                duration.append(frame.duration // 10 * 10)
        # print duration
        duration = sum(duration) / len(duration)
        print duration
        for pos, layers in selection:
            tile = tilemap.get_tile_at(*pos)[0]
            action = tile.vault.get_actions().items()[0][1]
            for frame in action.get_frames():
                frame.duration = duration
            tile.replace_vault(tile.vault)
            # print tile
        # TODO update sprites on all tilemaps!

    def __on_save_tilemap_vault_keyup_event(self, context):
        print 'Saving tilesheet: %s' % self.current_tilemap
        tilemap = self.tilemaps[self.current_tilemap]
        tilemap.get_sheet(self.current_tilemap).save()

    def _extract_autotile_type_a(self, tilemap, selection):
        tile_size = tilemap.get_tile_size()
        # print 'tile_size =', tile_size
        t_w = tile_size[0] / 2
        t_h = tile_size[1] / 2
        ids = [val[0] for key, val in selection]
        # print 'ids =', ids
        tl_id, tr_id, bl_id, br_id = ids
        vault = tilemap.get_tile_at(*selection[0][0])[0].vault.get_vault()
        # print 'vault =', vault
        autotile_group_id = '%s,%s,%s,%s' % tuple(ids)
        # print 'autotile_group_id =', autotile_group_id

        # Generate tl frame data.
        tl_frames = []
        frames = vault.get_sprite(tl_id).get_actions().values()[0].get_frames()
        # print 'frames =', frames
        for frame in frames:
            tl_frames.append([frame.rect, frame.hotspot, frame.delta, frame.duration, frame.events])
        # Generate tr frame data.
        tr_frames = []
        frames = vault.get_sprite(tr_id).get_actions().values()[0].get_frames()
        # print 'frames =', frames
        for frame in frames:
            tr_frames.append([frame.rect, frame.hotspot, frame.delta, frame.duration, frame.events])
        # Generate bl frame data.
        bl_frames = []
        frames = vault.get_sprite(bl_id).get_actions().values()[0].get_frames()
        # print 'frames =', frames
        for frame in frames:
            bl_frames.append([frame.rect, frame.hotspot, frame.delta, frame.duration, frame.events])
        # Generate br frame data.
        br_frames = []
        frames = vault.get_sprite(br_id).get_actions().values()[0].get_frames()
        # print 'frames =', frames
        for frame in frames:
            br_frames.append([frame.rect, frame.hotspot, frame.delta, frame.duration, frame.events])
        # Generate t frame data.
        t_frames = []
        for idx, frame in enumerate(tl_frames):
            r_a = pygame.Rect(tl_frames[idx][0])
            r_b = pygame.Rect(tr_frames[idx][0])
            rects = [[r_a.x + t_w, r_a.y, r_a.w - t_w, r_a.h], [r_b.x, r_b.y, r_b.w - t_w, r_b.h]]
            h_a = tl_frames[idx][1]
            h_b = tr_frames[idx][1]
            hotspots = [[h_a[0] + t_w, h_a[1]], [h_b[0], h_b[1]]]
            d_a = tl_frames[idx][2]
            d_b = tr_frames[idx][2]
            deltas = [[d_a[0] + t_w, d_a[1]], [d_b[0], d_b[1]]]
            duration = frame[3]
            events = frame[4] + tr_frames[idx][4]
            t_frames.append([rects, hotspots, deltas, duration, events])
        # Generate b frame data.
        b_frames = []
        for idx, frame in enumerate(bl_frames):
            r_a = pygame.Rect(bl_frames[idx][0])
            r_b = pygame.Rect(br_frames[idx][0])
            rects = [[r_a.x + t_w, r_a.y, r_a.w - t_w, r_a.h], [r_b.x, r_b.y, r_b.w - t_w, r_b.h]]
            h_a = bl_frames[idx][1]
            h_b = br_frames[idx][1]
            hotspots = [[h_a[0] + t_w, h_a[1]], [h_b[0], h_b[1]]]
            d_a = bl_frames[idx][2]
            d_b = br_frames[idx][2]
            deltas = [[d_a[0] + t_w, d_a[1]], [d_b[0], d_b[1]]]
            duration = frame[3]
            events = frame[4] + br_frames[idx][4]
            b_frames.append([rects, hotspots, deltas, duration, events])
        # Generate l frame data.
        l_frames = []
        for idx, frame in enumerate(tl_frames):
            r_a = pygame.Rect(tl_frames[idx][0])
            r_b = pygame.Rect(bl_frames[idx][0])
            rects = [[r_a.x, r_a.y + t_h, r_a.w, r_a.h - t_h], [r_b.x, r_b.y, r_b.w, r_b.h - t_h]]
            h_a = tl_frames[idx][1]
            h_b = bl_frames[idx][1]
            hotspots = [[h_a[0], h_a[1] + t_h], [h_b[0], h_b[1]]]
            d_a = tl_frames[idx][2]
            d_b = bl_frames[idx][2]
            deltas = [[d_a[0], d_a[1] + t_h], [d_b[0], d_b[1]]]
            duration = frame[3]
            events = frame[4] + bl_frames[idx][4]
            l_frames.append([rects, hotspots, deltas, duration, events])
        # Generate r frame data.
        r_frames = []
        for idx, frame in enumerate(tr_frames):
            r_a = pygame.Rect(tr_frames[idx][0])
            r_b = pygame.Rect(br_frames[idx][0])
            rects = [[r_a.x, r_a.y + t_h, r_a.w, r_a.h - t_h], [r_b.x, r_b.y, r_b.w, r_b.h - t_h]]
            h_a = tr_frames[idx][1]
            h_b = br_frames[idx][1]
            hotspots = [[h_a[0], h_a[1] + t_h], [h_b[0], h_b[1]]]
            d_a = tr_frames[idx][2]
            d_b = br_frames[idx][2]
            deltas = [[d_a[0], d_a[1] + t_h], [d_b[0], d_b[1]]]
            duration = frame[3]
            events = frame[4] + br_frames[idx][4]
            r_frames.append([rects, hotspots, deltas, duration, events])
        # Generate m frame data.
        m_frames = []
        for idx, frame in enumerate(tl_frames):
            r_a = pygame.Rect(tl_frames[idx][0])
            r_b = pygame.Rect(tr_frames[idx][0])
            r_c = pygame.Rect(bl_frames[idx][0])
            r_d = pygame.Rect(br_frames[idx][0])
            rects = [
                [r_d.x, r_d.y, r_d.w - t_w, r_d.h - t_h],
                [r_c.x + t_w, r_c.y, r_c.w - t_w, r_c.h - t_h],
                [r_b.x, r_b.y + t_h, r_b.w - t_w, r_b.h - t_h],
                [r_a.x + t_w, r_a.y + t_h, r_a.w - t_w, r_a.h - t_h],
            ]
            h_a = tl_frames[idx][1]
            h_b = tr_frames[idx][1]
            h_c = bl_frames[idx][1]
            h_d = br_frames[idx][1]
            hotspots = [
                [h_d[0], h_d[1]],
                [h_c[0] + t_w, h_c[1]],
                [h_b[0], h_b[1] + t_h],
                [h_a[0] + t_w, h_a[1] + t_h],
            ]
            d_a = tl_frames[idx][2]
            d_b = tr_frames[idx][2]
            d_c = bl_frames[idx][2]
            d_d = br_frames[idx][2]
            deltas = [
                [d_d[0], d_d[1]],
                [d_c[0] + t_w, d_c[1]],
                [d_b[0], d_b[1] + t_h],
                [d_a[0] + t_w, d_a[1] + t_h],
            ]
            duration = frame[3]
            events = frame[4] + tr_frames[idx][4]
            m_frames.append([rects, hotspots, deltas, duration, events])
        # Generate inner (representation) frame data.
        inner_frames = []
        for idx, frame in enumerate(tl_frames):
            r_a = pygame.Rect(tl_frames[idx][0])
            r_b = pygame.Rect(tr_frames[idx][0])
            r_c = pygame.Rect(bl_frames[idx][0])
            r_d = pygame.Rect(br_frames[idx][0])
            rects = [
                [r_a.x, r_a.y, r_a.w - t_w, r_a.h - t_h],
                [r_b.x + t_w, r_b.y, r_b.w - t_w, r_b.h - t_h],
                [r_c.x, r_c.y + t_h, r_c.w - t_w, r_c.h - t_h],
                [r_d.x + t_w, r_d.y + t_h, r_d.w - t_w, r_d.h - t_h],
            ]
            h_a = tl_frames[idx][1]
            h_b = tr_frames[idx][1]
            h_c = bl_frames[idx][1]
            h_d = br_frames[idx][1]
            hotspots = [
                [h_a[0], h_a[1]],
                [h_b[0] + t_w, h_b[1]],
                [h_c[0], h_c[1] + t_h],
                [h_d[0] + t_w, h_d[1] + t_h],
            ]
            d_a = tl_frames[idx][2]
            d_b = tr_frames[idx][2]
            d_c = bl_frames[idx][2]
            d_d = br_frames[idx][2]
            deltas = [
                [d_a[0], d_a[1]],
                [d_b[0] + t_w, d_b[1]],
                [d_c[0], d_c[1] + t_h],
                [d_d[0] + t_w, d_d[1] + t_h],
            ]
            duration = frame[3]
            events = frame[4] + tr_frames[idx][4]
            inner_frames.append([rects, hotspots, deltas, duration, events])

        autotile_data = OrderedDict()
        autotile_data['inner'] = {'none': inner_frames}  # Representation.
        autotile_data['tl'] = {'none': tl_frames}
        autotile_data['tr'] = {'none': tr_frames}
        autotile_data['bl'] = {'none': bl_frames}
        autotile_data['br'] = {'none': br_frames}
        autotile_data['t'] = {'none': t_frames}
        autotile_data['b'] = {'none': b_frames}
        autotile_data['l'] = {'none': l_frames}
        autotile_data['r'] = {'none': r_frames}
        autotile_data['m'] = {'none': m_frames}
        # print 'autotile_data =', autotile_data

        # Rewrite keys to reflect autotile group.
        sprite_data = OrderedDict()
        for key, val in autotile_data.iteritems():
            sprite_data[':A:%s:%s' % (autotile_group_id, key)] = val

        for key, val in sprite_data.iteritems():
            vault.add_sprite(key, val)
        # print 'vault sprites =', vault.get_sprites()

        # Now find position to place autotile representation at.
        results = tilemap.find_in_sector(0, 0, sprite_data.keys()[0])
        if results:
            # print results
            tm_x, tm_y = results[0][:2]
            # And place it.
            points = [(tm_x, tm_y, 0, sprite_data.keys()[0])]
            # print 'points =', points
            tile = tilemap.get_tile_at(tm_x, tm_y, 0)
            tile.replace_vault(vault.get_sprite(':A:%s:%s' % (autotile_group_id, 'inner')))
            # TODO update sprites on all tilemaps!
        else:
            tm_width, tm_height = tilemap.get_sector_size()
            # print 'tilemap size =', (tm_width, tm_height)
            tm_x, tm_y = 0, max(0, tm_height - 1)
            found = False
            while found is False:
                for x in range(0, tm_width):
                    if tilemap.get_tile_id_at(x, tm_y, 0) is None:
                        found = x
                        break
                if found is False:
                    tm_y += 1
            tm_x = found
            # And place it.
            points = [(tm_x, tm_y, 0, sprite_data.keys()[0])]
            # print 'points =', points
            tilemap.load_points(points)
            tilemap.set_sector_size(max(tm_width, tm_x + 1), tm_y + 1)

        self.selection.clear_selection(tilemap.name)
        self.selection.add_selection(tilemap.name, [points[0][:2]], translate_pos=False)
        self.commit_selection()

    def _extract_autotile_type_b(self, tilemap, selection):
        pass

    def __on_extract_autotile_keyup_event(self, context):
        tilemap = self.tilemaps[self.current_tilemap]
        selection = self.selection.get_selection(tilemap.name, sort=True).items()
        if not selection:
            return
        # print selection
        if len(selection) == 4:
            print 'Could be autotile type A.'
            self._extract_autotile_type_a(tilemap, selection)
        elif len(selection) == 6:
            print 'Could be autotile type B.'
            self._extract_autotile_type_b(tilemap, selection)
        else:
            print 'Unknown amount of tiles selected. Type A required 6 tiles. Type B requires 4 tiles.'
            return
