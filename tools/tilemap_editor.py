#!/usr/bin/env python
import os
import sys
import textwrap
import argparse
import re
from itertools import chain
from collections import OrderedDict

import pygame

# Make sure that our diamond engine can be found.
engine_path = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.abspath(engine_path))


from diamond.scene import SceneManager, Scene
from diamond.tilemap import LayeredTileMap, TileMap
from diamond.effects import TransitionEffects
from diamond.node import Node
from diamond.fps import Fps
from diamond.ticker import Ticker
from diamond.font import Font
from diamond.sprite import Sprite, SpritePrimitives
from diamond import event
from diamond.helper.ordered_set import OrderedSet
from diamond.decorators import time


APP_NAME = 'Tilemap Editor'
APP_VERSION = '0.1'

shared_data = dict()


# TODO add highlight box to TilesheetScene.
# TODO clean up TilesheetScene.
# TODO move some palette code including transitions into scene object.
# TODO implement autotile grabber mechanism in the TilesheetScene:
#      1. implement key binding for activating it.
#      2. implement mouse click binding for getting the area.
#      3. look if area has not already been defined and reuse it.
#      4. if not defined create sprites from area and use it.
#      5. if necessary extend the tilesheet file with another sprite set.
#      6. add topleft tile to palette and surround it with a white border.

# TODO perhaps t and b should be out of 2 tiles in reverse order?
AUTOTILE_PARTS = (
    'inner',   # O
    'outter',  # X

    'tl',  # |^
    't',   #  ^
    'tr',  #  ^|
    'l',   # |
    'm',   #  m
    'r',   #   |
    'bl',  # |_
    'b',   #  _
    'br',  #  _|

    'rb',  #   ,
    'lb',  # ,
    'rt',  #   '
    'lt',  # '

    'rtb',  #   =
    'ltb',  # =
    'tlr',  # ' '
    'blr',  # , ,

    'tb',  #  =
    'lr',  # | |

    'rtb_closed',  #  =|
    'ltb_closed',  # |=
    'tlr_closed',  # |^|
    'blr_closed',  # |_|

    'b_tlr',  # '_'
    't_blr',  # ,^,
    'l_rtb',  # | =
    'r_ltb',  # = |

    'bl_rt',  # |_'
    'br_lt',  # '_|
    'tl_rb',  # |^,
    'tr_lb',  # ,^|

    'rtb_lt',  # ' =
    'ltb_rb',  # = ,
    'tlr_lb',  # = '
    'blr_rt',  # , =

    'lt_rb',  # ' ,
    'rt_lb',  # , '

    'l_rb',  # | ,
    'l_rt',  # | '
    'r_lb',  # , |
    'r_lt',  # ' |
    't_rb',  #  ^,
    't_lb',  # ,^
    'b_rt',  #  _'
    'b_lt',  # '_
)

AUTOTILE_SITUATIONS = {
    # Simples.
    'l': 'rtb_closed',
    'r': 'ltb_closed',
    'l,r': 'tb',
    'b,t': 'lr',
    't': 'blr_closed',
    'b': 'tlr_closed',
    'l,r,t': 'b_tlr',
    'bl,l': 'rtb_closed',
    'br,r': 'ltb_closed',
    'b,l,r': 't_blr',
    'b,r,t': 'l_rtb',
    'b,l,t': 'r_ltb',
    'b,l,r,t': 'outter',
    'r,t': 'bl_rt',
    'b,l': 'tr_lb',
    'l,t': 'br_lt',
    'b,r': 'tl_rb',

    # Complex.
    'b,bl,br,l,r,t,tl,tr': 'm',
    'bl,l,r,t,tl,tr': 'b',
    'b,l,r,t,tr': 'ltb_rb',
    'b,bl,l,r,t': 'rtb_lt',
    'b,bl,br,r,t,tl,tr': 'l',
    'b,br,l,r,t': 'tlr_lb',
    'b,bl,br,l,t,tl,tr': 'r',
    'b,bl,br,l,r,tl,tr': 't',
    'br,l,r,t,tl': 'b_rt',
    'b,l,r,t,tl': 'blr_rt',
    'bl,br,l,r,t,tl,tr': 'b',
    'b,bl,l': 'tr',
    'b,br,r': 'tl',
    'bl,l,t,tl': 'br',
    'r,t,tr': 'bl',
    'l,t,tl,tr': 'br',
    'b,bl,br,l': 'tr',
    'l,t,tl': 'br',
    'r,t,tl,tr': 'bl',
    'b,bl,l,tl': 'tr',
    'b,br,r,t,tr': 'l',
    'b,bl,l,t,tl': 'r',
    'l,r,t,tl,tr': 'b',
    'b,bl,br,l,r': 't',
    'b,bl,l,r,t,tr': 'lt_rb',
    'b,br,l,r,t,tl': 'rt_lb',
    'b,bl,br,l,r,t': 'tlr',
    'b,l,r,t,tl,tr': 'blr',
    'b,br,l,r,t,tr': 'ltb',
    'b,bl,l,r,t,tl': 'rtb',
    'b,bl,br,l,r,t,tl': 'rt',
    'b,br,l,r,t,tl,tr': 'lb',
    'b,bl,l,r,t,tl,tr': 'rb',
    'b,bl,br,l,r,t,tr': 'lt',
    'b,r,t,tr': 'l_rb',
    'b,br,r,t': 'l_rt',
    'b,l,t,tl': 'r_lb',
    'b,bl,l,t': 'r_lt',
    'b,bl,l,r': 't_rb',
    'b,br,l,r': 't_lb',
    'l,r,t,tl': 'b_rt',
    'l,r,t,tr': 'b_lt',
}


class TilesheetScene(Scene):

    def setup(self):
        super(TilesheetScene, self).setup()
        self.add_default_listeners()
        self.ticker = Ticker()
        self.transition_manager = TransitionEffects()
        self.bind(self.ticker, self.transition_manager)
        s_width, s_height = self.scene_manager.display.screen_size
        box = SpritePrimitives.make_rectangle(s_width, s_height, color=(64, 64, 64, 255), background=(0, 0, 0, 255))
        box.set_alpha(80)
        box.add_to(self.root_node)
        self.bind(
            event.add_listener(self.__on_mouse_motion_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.MOUSEMOTION),
            event.add_listener(self.__on_hide_tilesheet_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_SPACE),
            event.add_listener(self.__on_mouse_button_released_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.MOUSEBUTTONUP),
            event.add_listener(self.__on_tilemap_switched_layer_event, 'tilemap.switched_layer')
        )

        self.sheet_2_tilemap = dict()
        for layer in shared_data['layers']:
            if id(layer['sheet_vault']) not in self.sheet_2_tilemap:
                self.sheet_2_tilemap[id(layer['sheet_vault'])] = dict(
                    tilemap=None,
                    tilemap_size=None,
                    layer=layer,
                )

        layered_tilemap = LayeredTileMap()
        layered_tilemap.set_order_pos(10)
        layered_tilemap.add_to(self.root_node)
        for container in self.sheet_2_tilemap.itervalues():
            layer = container['layer']

            tilemap = layered_tilemap.add_layer_from_iterable(layer['sheet_vault'], None, default_size=(0, 0))
            vault = tilemap.get_vault()
            sheet_module = layer['sheet_vault']
            tile_size = sheet_module.tile_size
            # print 'tile_size =', tile_size
            sprites = vault.get_sprites().copy()
            # print 'found %d sprites' % len(sprites)

            # Remove all autotiles from the list.
            if hasattr(sheet_module, 'autotiles'):
                for item in chain(*sheet_module.autotiles.values()):
                    del sprites[item]

            rects = OrderedDict()
            # Gain map size from tiles found
            for sprite in sprites.itervalues():
                rects[sprite.name] = pygame.Rect(sprite.get_action('none').get_frame(0).rect)
            # print rects
            size_in_pixel = pygame.Rect(rects.values()[0]).unionall(rects.values()).size
            size_in_tiles = (size_in_pixel[0] / tile_size[0], size_in_pixel[1] / tile_size[1])
            # print size_in_pixel, size_in_tiles

            map_data = [[None for col in xrange(size_in_tiles[0])] for row in xrange(size_in_tiles[1])]
            # Put tiles in proper map position.
            overlapped_tiles = []
            for key, val in rects.iteritems():
                x, y = val.x / tile_size[0], val.y / tile_size[1]
                # print key, val, (x, y)
                if map_data[y][x] is not None:
                    overlapped_tiles.append(key)
                else:
                    map_data[y][x] = key

            # Append overlapped tiles at the bottom of the map.
            if overlapped_tiles:
                # print overlapped_tiles
                # First create an empty line as separator.
                cur_x, cur_y = 0, len(map_data)
                map_data.append([None for col in xrange(size_in_tiles[0])])
                # Now add the overlapping tiles.
                cur_x, cur_y = 0, len(map_data)
                map_data.append([None for col in xrange(size_in_tiles[0])])
                for key in overlapped_tiles:
                    map_data[cur_y][cur_x] = key
                    cur_x += 1
                    if cur_x >= size_in_tiles[0]:
                        cur_x = 0
                        cur_y += 1
                        map_data.append([None for col in xrange(size_in_tiles[0])])

            tilemap.load_map_from_iterable(map_data)
            # tilemap.create_map(*size_in_tiles)
            tilemap.enable_spacer()
            tilemap.build_map()
            tilemap.hide()

            container['tilemap'] = tilemap
            container['tilemap_size'] = tilemap.get_rect().size

        self.highlighted_tile = None
        self.tilemap_layers = layered_tilemap

        # Select tilemap of active sheet from TileMapScene below.
        self.__on_tilemap_switched_layer_event(context=dict(
            tilemap=self.scene_manager.get_scene('tilemap').tilemap,
        ))

        self.screen_size = (s_width, s_height)
        # print 'screen size =', self.screen_size

        self.palette_scene = self.scene_manager.get_scene('palette', instanciate=True)

    def __on_hide_tilesheet_keyup_event(self, context):
        self.scene_manager.hide_scene('tilesheet')
        self.scene_manager.show_scene('tilemap')

    def __on_tilemap_switched_layer_event(self, context):
        tilemap = context['tilemap']
        for container in self.sheet_2_tilemap.itervalues():
            if container['tilemap'].get_vault() is tilemap.get_vault():
                print 'switch tilesheet to layer', id(container)
                self.tilemap = container['tilemap']
                self.tilemap.show()
                self.tile_size = self.tilemap.get_tile_size()
                self.tilemap_size = container['tilemap_size']
            else:
                print 'hide tilesheet layer', id(container)
                container['tilemap'].hide()

    def highlight_map_tile(self, tile):
        self.unhighlight_map_tile()
        tile.set_gamma(130)
        self.highlighted_tile = tile
        # box = self.highlighted_tile_box
        # box.set_pos(*tile.pos)
        # box.show()
        # self.selection = [tile]
        # print tile

    def unhighlight_map_tile(self):
        if self.highlighted_tile:
            self.highlighted_tile.set_gamma(100)
            self.highlighted_tile = None
            # self.highlighted_tile_box.hide()
            # self.selection = []

    def make_tile_current(self, x, y):
        width, height = self.tilemap.get_tile_size()
        # Translate pos to possible tile.
        x, y = self.root_node.translate_pos((x, y), self.tilemap)
        pos = x / width, y / height
        # print pos
        tile = self.tilemap.get_tile_at(*pos)
        # Ensure that it's not the same.
        if self.highlighted_tile is None or tile != self.highlighted_tile:
            if tile is not None:
                self.highlight_map_tile(tile)
            else:
                self.unhighlight_map_tile()

    def __on_mouse_motion_event(self, context):
        '''
        Tracks mouse movements, drags the map around and highlights the tile
        underneath the mouse cursor. TODO
        '''
        pos = context.event.pos
        # print 'pos =', pos

        i_width, i_height = self.tilemap_size
        s_width, s_height = self.screen_size
        # print self.tilemap_size, self.screen_size

        palette_scene = self.palette_scene
        palette_node = palette_scene.palette_node
        palette_rect = palette_node.get_rect()

        # Tolerance boundaries.
        t_w, t_h = max(self.tile_size[0], 64), max(self.tile_size[1], 64)
        p_x = min(1.0, max(0, (pos[0] - palette_rect.w - t_w)) / float(s_width - palette_rect.w - t_w * 2))
        p_y = min(1.0, max(0, (pos[1] - t_h)) / float(s_height - t_h * 2))
        # print p_x, p_y

        s_width -= palette_rect.w
        x, y = max(0, (i_width - s_width)) * p_x * -1, max(0, (i_height - s_height)) * p_y * -1
        # print x, y
        self.tilemap.set_pos(int(x) + palette_rect.w, int(y))

        self.make_tile_current(*pos)

    def __on_mouse_button_released_event(self, context):
        lmb_pressed = context.event.button == 1
        # rmb_pressed = context.event.button == 3

        if lmb_pressed and self.highlighted_tile:
            tile_id = self.tilemap.get_tile_id(self.highlighted_tile)
            # print tile_id
            if tile_id != TileMap.TILE_SPACER_ID:
                self.palette_scene.set_current_tile(tile_id)
                self.palette_scene.add_to_palette(tile_id)

    def show(self):
        super(TilesheetScene, self).show()
        pos = pygame.mouse.get_pos()
        from diamond.array import Array
        context = Array(
            event=Array(
                pos=pos,
            )
        )
        self.__on_mouse_motion_event(context)

        tilemap_scene = self.scene_manager.get_scene('tilemap')
        tilemap_scene.set_cursor_mode(TilemapScene.CURSOR_MODE_PALETTE)


class PaletteScene(Scene):

    def add_to_palette(self, tile_id):
        slots = self.palette_slots
        # 1. Make sure that it's not already in our palette.
        for slot in slots:
            if slot['tile_id'] == tile_id:
                return
        # 2. Move all tiles one slot upwards.
        for pos, slot in enumerate(slots):
            if pos == 0:  # Skip first slot - we already managed it above.
                continue
            prev_slot = slots[pos - 1]
            prev_slot['tile_id'] = slot['tile_id']
            prev_slot['tile'].replace_vault(slot['tile'].vault)
        # 3. Install new tile in last slot.
        last_slot = slots[-1]
        last_slot['tile_id'] = tile_id
        vault = last_slot['tile'].vault.get_vault()
        sprite = vault.get_sprite(str(tile_id))
        last_slot['tile'].replace_vault(sprite)

    def setup(self):
        super(PaletteScene, self).setup()

        self.root_node.set_order_pos(10)

        tilemap_scene = self.scene_manager.get_scene('tilemap')
        tilemap = tilemap_scene.tilemap

        self.transition_manager = TransitionEffects()
        self.bind(self.transition_manager)
        self.palette_node_stack = self.transition_manager.stack()

        self.highlighted_palette_tile = None

        self.palette_node = Node('palette')
        self.palette_node.pos = (10, 10)
        # self.palette_node.add_to(tilemap_scene.hud_node)
        self.palette_node.add_to(self.root_node)
        tool_chain_node = Node('toolchain')
        tool_chain_node.add_to(self.palette_node)
        slots = []
        vault = tilemap.get_vault()
        s_width, s_height = self.scene_manager.display.screen_size
        t_width, t_height = tilemap.get_tile_size()
        h_spacer = max(5, t_width / 5)
        v_spacer = max(5, t_height / 5)
        x, y = 0, 0
        pos = 0
        max_items = 100
        # row_length = None
        tool_chain_height = s_height - (v_spacer + t_height + v_spacer) - 10
        tile_ids = OrderedSet(tilemap.get_tile_ids())

        # Remove all autotiles from the list.
        tilesheet = tilemap.get_sheet()
        if hasattr(tilesheet, 'autotiles'):
            for item in chain(*tilesheet.autotiles.values()):
                tile_ids.remove(item)

        tile_id_iterator = tile_ids.__iter__()
        tile_id = tile_id_iterator.next()
        to_be_added = []
        while pos < max_items:
            # print pos
            tile = Sprite.make(vault, str(tile_id))
            tile.pos = (x, y)
            # tile.add_to(tool_chain_node)
            to_be_added.append(tile)
            slots.append(dict(
                tile_id=str(tile_id),
                pos=(x, y),
                tile=tile,
            ))
            try:
                tile_id = tile_id_iterator.next()
            except StopIteration:
                tile_id_iterator = tile_ids.__iter__()
                tile_id = tile_id_iterator.next()
            # y += t_height + v_spacer
            # if y + t_height + 10 >= tool_chain_height:
            #     if row_length is None:
            #         # print 'break at', pos
            #         row_length = pos + 1
            #         # print max_items, row_length
            #         max_items = max_items  - (max_items - row_length) + row_length
            #         # print max_items
            #     y = 0
            #     x += t_width + h_spacer
            #     if x >= int(s_width * 0.2):
            #         break
            x += t_width + h_spacer
            if x >= int(s_width * 0.15):
                x = 0
                y += t_height + v_spacer
            if y + t_height >= tool_chain_height:
                break
            pos += 1
        tool_chain_node.add_children(to_be_added)
        self.palette_slots = slots

        rect = self.palette_node.get_rect()
        tile = Sprite.make(vault, str(tile_ids[0]))
        tile.pos = ((rect.w - t_width) / 2, tool_chain_height)
        tile.add_to(tool_chain_node)
        self.current_tile = tile
        # self.set_current_tile(str(tile_ids[1]))  # For debugging.

        # Create gray rectangle for surrounding the selected palette tile.
        highlight_node = Node('highlight')
        highlight_node.order_matters = False
        highlight_node.add_to(self.palette_node)
        box = SpritePrimitives.make_rectangle(t_width + 2, t_height + 2, color=(128, 128, 128), hotspot=(1, 1))
        box.add_to(highlight_node)
        box.hide()
        self.highlighted_palette_tile_box = box

        # Create black transparent box behind palette.
        rect = self.palette_node.get_rect()
        width = rect.w + 20
        height = rect.h + 20
        box = SpritePrimitives.make_rectangle(width, height, color=(64, 64, 64, 255), background=(0, 0, 0, 255))
        box.pos = (-10, -10)
        box.set_alpha(70)
        box.add_to(self.palette_node)

        # self.palette_node.order_matters = False

    def set_current_tile(self, tile_id):
        tile = self.current_tile
        vault = tile.vault.get_vault()
        sprite = vault.get_sprite(str(tile_id))
        tile.replace_vault(sprite)

    def highlight_palette_tile(self, tile):
        self.unhighlight_palette_tile()
        tile.set_gamma(130)
        self.highlighted_palette_tile = tile
        box = self.highlighted_palette_tile_box
        box.set_pos(*tile.pos)
        box.show()

    def unhighlight_palette_tile(self):
        if self.highlighted_palette_tile:
            self.highlighted_palette_tile.set_gamma(100)
            self.highlighted_palette_tile = None
            self.highlighted_palette_tile_box.hide()


class TilemapScene(Scene):

    CURSOR_MODE_DRAG = 0
    CURSOR_MODE_DRAW = 1
    CURSOR_MODE_PALETTE = 2
    CURSOR_MODE_HIGHLIGHT_ALL = 3
    CURSOR_MODE_HIGHLIGHT_PATH = 4
    CURSOR_MODE_HIGHLIGHT_COLUMN = 5
    CURSOR_MODE_HIGHLIGHT_ROW = 6

    def __setup_fps(self):
        screen_width = self.scene_manager.display.screen_size[0]
        fps_node = Node('fps node')
        fps_node.order_matters = False
        fps_node.add_to(self.hud_node)
        fps = Fps(ticker=self.ticker, details=True)
        fps.set_alpha(75)
        fps.add_to(fps_node)
        fps.set_align_box(screen_width, 0, 'right')
        self.fps = fps

    def set_cursor_mode(self, mode, amount=None):
        text = ''
        if mode == TilemapScene.CURSOR_MODE_DRAG:
            text = 'drag'
            pygame.mouse.set_cursor(*self.default_pg_cursor)
        elif mode == TilemapScene.CURSOR_MODE_DRAW:
            text = 'draw'
            pygame.mouse.set_cursor(*pygame.cursors.ball)
            # TODO can we show the current tile below the cursor so that the
            #      user can see if it fits?
        elif mode == TilemapScene.CURSOR_MODE_PALETTE:
            text = 'palette'
            pygame.mouse.set_cursor(*self.default_pg_cursor)
        elif mode == TilemapScene.CURSOR_MODE_HIGHLIGHT_ALL:
            text = 'find all'
            pygame.mouse.set_cursor(*pygame.cursors.diamond)
        elif mode == TilemapScene.CURSOR_MODE_HIGHLIGHT_PATH:
            text = 'find path'
            pygame.mouse.set_cursor(*pygame.cursors.diamond)
        elif mode == TilemapScene.CURSOR_MODE_HIGHLIGHT_COLUMN:
            text = 'select column'
            pygame.mouse.set_cursor(*pygame.cursors.diamond)
        elif mode == TilemapScene.CURSOR_MODE_HIGHLIGHT_ROW:
            text = 'select row'
            pygame.mouse.set_cursor(*pygame.cursors.diamond)
        if amount is not None:
            text = '%s (%s)' % (text, amount)
        self.cmd.set_text('cursor mode: %s' % text)
        self.cursor_mode = mode

        palette = self.palette_scene
        rect = palette.palette_node.get_rect()
        alpha_hidden = 20
        alpha_shown = 100
        palette.palette_node_stack.clear()
        if mode == TilemapScene.CURSOR_MODE_PALETTE:
            palette.palette_node_stack.fade_to(palette.palette_node, value=alpha_shown, msecs=300, append=True)
            palette.palette_node_stack.move_to(palette.palette_node, pos=(10, 10), msecs=300, append=True)
        else:
            palette.palette_node_stack.move_to(palette.palette_node, pos=(-rect.w + 20, 10), msecs=300, append=True)
            palette.palette_node_stack.fade_to(palette.palette_node, value=alpha_hidden, msecs=300, append=True)

    def return_to_palette_mode_if_necessary(self):
        # Return to palette mode if cursor within area.
        pos = map(int, self.cpd.get_text().split('x'))
        if not self.switch_to_palette_mode(pos):
            # print 'drag mode'
            self.set_cursor_mode(TilemapScene.CURSOR_MODE_DRAG)
        else:
            TilemapScene.CURSOR_MODE_backup = TilemapScene.CURSOR_MODE_DRAG

    def __on_draw_mode_keydown_event(self, context):
        if self.cursor_mode != TilemapScene.CURSOR_MODE_DRAG:
            return False
        # print 'draw mode'
        self.set_cursor_mode(TilemapScene.CURSOR_MODE_DRAW)

    def __on_draw_mode_keyup_event(self, context):
        if self.cursor_mode != TilemapScene.CURSOR_MODE_DRAW:
            return False
        self.return_to_palette_mode_if_necessary()

    def __on_find_all_mode_keydown_event(self, context):
        if self.cursor_mode != TilemapScene.CURSOR_MODE_DRAG:
            return False
        if self.highlighted_tile:
            tiles = self.tilemap.find_all(self.highlighted_tile)
            [tile.set_gamma(130) for tile in tiles]
            self.selection = tiles
            self.set_cursor_mode(TilemapScene.CURSOR_MODE_HIGHLIGHT_ALL, amount=len(tiles))

    def __on_find_all_mode_keyup_event(self, context):
        if self.cursor_mode != TilemapScene.CURSOR_MODE_HIGHLIGHT_ALL:
            return False
        if self.highlighted_tile:
            tiles = self.selection
            condition = lambda tile: tile is not self.highlighted_tile
            for tile in filter(condition, tiles):
                tile.set_gamma(100)
            self.selection = [self.highlighted_tile]
            self.return_to_palette_mode_if_necessary()

    def __on_find_path_mode_keydown_event(self, context):
        if self.cursor_mode != TilemapScene.CURSOR_MODE_DRAG:
            return False
        if self.highlighted_tile:
            tiles = self.tilemap.find_path(self.highlighted_tile)
            [tile.set_gamma(130) for tile in tiles]
            self.selection = tiles
            self.set_cursor_mode(TilemapScene.CURSOR_MODE_HIGHLIGHT_PATH, amount=len(tiles))

    def __on_find_path_mode_keyup_event(self, context):
        if self.cursor_mode != TilemapScene.CURSOR_MODE_HIGHLIGHT_PATH:
            return False
        if self.highlighted_tile:
            tiles = self.selection
            condition = lambda tile: tile is not self.highlighted_tile
            for tile in filter(condition, tiles):
                tile.set_gamma(100)
            self.selection = [self.highlighted_tile]
            self.return_to_palette_mode_if_necessary()

    def __on_find_column_mode_keydown_event(self, context):
        if self.cursor_mode != TilemapScene.CURSOR_MODE_DRAG:
            return False
        if self.highlighted_tile:
            x, y = self.tilemap.get_tile_pos(self.highlighted_tile)
            tiles = [row[x] for row in self.tilemap.get_map()]
            [tile.set_gamma(130) for tile in tiles]
            self.selection = tiles
            self.set_cursor_mode(TilemapScene.CURSOR_MODE_HIGHLIGHT_COLUMN, amount=len(tiles))

    def __on_find_column_mode_keyup_event(self, context):
        if self.cursor_mode != TilemapScene.CURSOR_MODE_HIGHLIGHT_COLUMN:
            return False
        if self.highlighted_tile:
            tiles = self.selection
            condition = lambda tile: tile is not self.highlighted_tile
            for tile in filter(condition, tiles):
                tile.set_gamma(100)
            self.selection = [self.highlighted_tile]
            self.return_to_palette_mode_if_necessary()

    def __on_find_row_mode_keydown_event(self, context):
        if self.cursor_mode != TilemapScene.CURSOR_MODE_DRAG:
            return False
        if self.highlighted_tile:
            x, y = self.tilemap.get_tile_pos(self.highlighted_tile)
            tiles = self.tilemap.get_map()[y]
            [tile.set_gamma(130) for tile in tiles]
            self.selection = tiles
            self.set_cursor_mode(TilemapScene.CURSOR_MODE_HIGHLIGHT_ROW, amount=len(tiles))

    def __on_find_row_mode_keyup_event(self, context):
        if self.cursor_mode != TilemapScene.CURSOR_MODE_HIGHLIGHT_ROW:
            return False
        if self.highlighted_tile:
            tiles = self.selection
            condition = lambda tile: tile is not self.highlighted_tile
            for tile in filter(condition, tiles):
                tile.set_gamma(100)
            self.selection = [self.highlighted_tile]
            self.return_to_palette_mode_if_necessary()

    def __on_pick_tile_keyup_event(self, context):
        if self.cursor_mode != TilemapScene.CURSOR_MODE_DRAG:
            return False
        if not self.highlighted_tile:
            return

        tile_id = self.tilemap.get_tile_id(self.highlighted_tile)
        # print tile_id
        if tile_id != TileMap.TILE_SPACER_ID:
            palette = self.palette_scene
            palette.set_current_tile(tile_id)
            palette.add_to_palette(tile_id)

    def __on_delete_keyup_event(self, context):
        if self.cursor_mode not in (TilemapScene.CURSOR_MODE_HIGHLIGHT_COLUMN, TilemapScene.CURSOR_MODE_HIGHLIGHT_ROW):
            return False
        if not self.highlighted_tile:
            return

        x, y = self.tilemap.get_tile_pos(self.highlighted_tile)

        if self.cursor_mode == TilemapScene.CURSOR_MODE_HIGHLIGHT_COLUMN:
            self.__on_find_column_mode_keyup_event(context)
            for tilemap, name in self.tilemap_layers:
                tilemap.remove_column(x)
                tilemap.build_map()
            post_func = self.__on_find_column_mode_keydown_event
        elif self.cursor_mode == TilemapScene.CURSOR_MODE_HIGHLIGHT_ROW:
            self.__on_find_row_mode_keyup_event(context)
            for tilemap, name in self.tilemap_layers:
                tilemap.remove_row(y)
                tilemap.build_map()
            post_func = self.__on_find_row_mode_keydown_event

        if self.cursor_mode == TilemapScene.CURSOR_MODE_DRAG:
            # Imitate mouse movement to find new tile to highlight.
            pos = tuple(map(int, self.cpd.get_text().split('x')))
            self.make_tile_current(*pos)
            post_func(context)

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

    def __on_save_map_keyup_event(self, context):
        self.tilemap_layers.save_maps()

    # @time
    def __on_toggle_spacer_keyup_event(self, context):
        # Backup selections.
        get_tile_pos = self.tilemap.get_tile_pos
        highlighted_tile_pos = get_tile_pos(self.highlighted_tile) if self.highlighted_tile else None
        coords = [get_tile_pos(tile) for tile in self.selection]

        self.tilemap.toggle_spacer()

        # Restore selections.
        get_tile_at = self.tilemap.get_tile_at
        self.selection = [get_tile_at(*pos) for pos in coords]
        [tile.set_gamma(130) for tile in self.selection]
        if highlighted_tile_pos:
            self.highlighted_tile = get_tile_at(*highlighted_tile_pos)

    # @time
    def __on_show_tilesheet_keyup_event(self, context):
        self.scene_manager.show_scene('tilesheet')

    def __setup_cursor(self):
        # TODO try switch selection to set. could be faster.
        self.selection = []

        self.default_pg_cursor = pygame.mouse.get_cursor()

        self.cursor_mode = TilemapScene.CURSOR_MODE_DRAG
        TilemapScene.CURSOR_MODE_backup = self.cursor_mode

        self.bind(
            event.add_listener(self.__on_mouse_motion_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.MOUSEMOTION),
            event.add_listener(self.__on_mouse_button_released_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.MOUSEBUTTONUP),
            event.add_listener(self.__on_mouse_button_pressed_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.MOUSEBUTTONDOWN),
            event.add_listener(self.__on_draw_mode_keydown_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYDOWN,
                               context__event__key__eq=pygame.locals.K_LSHIFT),
            event.add_listener(self.__on_draw_mode_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_LSHIFT),
            event.add_listener(self.__on_find_all_mode_keydown_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYDOWN,
                               context__event__key__eq=pygame.locals.K_a),
            event.add_listener(self.__on_find_all_mode_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_a),
            event.add_listener(self.__on_find_path_mode_keydown_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYDOWN,
                               context__event__key__eq=pygame.locals.K_y),
            event.add_listener(self.__on_find_path_mode_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_y),
            event.add_listener(self.__on_find_column_mode_keydown_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYDOWN,
                               context__event__key__eq=pygame.locals.K_c),
            event.add_listener(self.__on_find_column_mode_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_c),
            event.add_listener(self.__on_find_row_mode_keydown_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYDOWN,
                               context__event__key__eq=pygame.locals.K_v),
            event.add_listener(self.__on_find_row_mode_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_v),
            event.add_listener(self.__on_pick_tile_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_p),
            event.add_listener(self.__on_delete_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_BACKSPACE),
            event.add_listener(self.__on_change_bg_color_keyup_event, 'scene.event.system',
                               # context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__in=(pygame.locals.K_1, pygame.locals.K_2, pygame.locals.K_3, pygame.locals.K_4, pygame.locals.K_5, pygame.locals.K_6, pygame.locals.K_7)),
            event.add_listener(self.__on_save_map_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_s),
            event.add_listener(self.__on_toggle_spacer_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_x),
            event.add_listener(self.__on_show_tilesheet_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_SPACE),
            event.add_listener(self.__on_select_previous_tilemap_layer_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_DOWN),
            event.add_listener(self.__on_select_next_tilemap_layer_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_UP),
            event.add_listener(self.__on_show_all_tilemap_layers_keydown_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYDOWN,
                               context__event__key__eq=pygame.locals.K_LEFT),
            event.add_listener(self.__on_show_all_tilemap_layers_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_LEFT),
            event.add_listener(self.__on_reveal_tilemap_layers_keydown_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYDOWN,
                               context__event__key__eq=pygame.locals.K_RIGHT),
            event.add_listener(self.__on_reveal_tilemap_layers_keyup_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYUP,
                               context__event__key__eq=pygame.locals.K_RIGHT),
        )

        screen_width = self.scene_manager.display.screen_size[0]

        # cpd_node = cursor position display node
        cpd_node = Node('cpd node')
        cpd_node.order_matters = False
        cpd_node.add_to(self.hud_node)

        # cpd = cursor position display
        cpd = Font()
        cpd.set_alpha(75)
        cpd.add_to(cpd_node)
        cpd.set_align_box(screen_width, 0, 'top')
        cpd.set_text('0x0')
        self.cpd = cpd

        # cmd = cursor mode display
        cmd = Font()
        cmd.pos = (-150, 0)
        cmd.set_alpha(75)
        cmd.add_to(cpd_node)
        cmd.set_align_box(screen_width, 0, 'top')
        self.cmd = cmd
        self.set_cursor_mode(TilemapScene.CURSOR_MODE_DRAG)

        # ctpd = cursor position display
        ctpd = Font()
        ctpd.pos = (100, 0)
        ctpd.set_alpha(75)
        ctpd.add_to(cpd_node)
        ctpd.set_align_box(screen_width, 0, 'top')
        self.ctpd = ctpd

        # Create gray rectangle for surrounding the selected palette tile.
        highlight_node = Node('highlight')
        highlight_node.order_matters = False
        highlight_node.add_to(self.base_node)
        t_width, t_height = self.tilemap.get_tile_size()
        box = SpritePrimitives.make_rectangle(t_width + 2, t_height + 2, color=(128, 128, 128), hotspot=(1, 1))
        box.add_to(highlight_node)
        box.hide()
        self.highlighted_tile_box = box

        self.highlighted_tile = None
        self.was_drag = False

        # ltf = layer text display
        ltd = Font()
        ltd.pos = (0, 15)
        ltd.set_alpha(75)
        ltd.add_to(self.hud_node)
        ltd.set_align_box(screen_width, 0, 'top')
        self.ltd = ltd

    def switch_to_palette_mode(self, pos):
        palette = self.palette_scene
        palette_rect = palette.palette_node.get_rect()
        # print palette_rect
        if palette_rect.collidepoint(pos):
            # print 'within palette'
            if self.cursor_mode != TilemapScene.CURSOR_MODE_PALETTE:
                if self.highlighted_tile:
                    self.highlighted_tile.set_gamma(100)
                    self.highlighted_tile = None
                TilemapScene.CURSOR_MODE_backup = self.cursor_mode
                self.set_cursor_mode(TilemapScene.CURSOR_MODE_PALETTE)
            return True
        elif self.cursor_mode == TilemapScene.CURSOR_MODE_PALETTE:
            self.set_cursor_mode(TilemapScene.CURSOR_MODE_backup)
            palette.unhighlight_palette_tile()

    def highlight_map_tile(self, tile):
        self.unhighlight_map_tile()
        tile.set_gamma(130)
        self.highlighted_tile = tile
        box = self.highlighted_tile_box
        box.set_pos(*tile.pos)
        box.show()
        self.selection = [tile]

    def unhighlight_map_tile(self):
        if self.highlighted_tile:
            self.highlighted_tile.set_gamma(100)
            self.highlighted_tile = None
            self.highlighted_tile_box.hide()
            self.selection = []

    def make_tile_current(self, x, y):
        width, height = self.tilemap.get_tile_size()
        # Translate pos to possible tile.
        x, y = self.root_node.translate_pos((x, y), self.tilemap)
        pos = x / width, y / height
        # print pos
        tile = self.tilemap.get_tile_at(*pos)
        # Ensure that it's not the same.
        if self.highlighted_tile is None or tile != self.highlighted_tile:
            if tile is not None:
                self.highlight_map_tile(tile)
            else:
                self.unhighlight_map_tile()

    # @time
    def __on_mouse_motion_event(self, context):
        '''
        Tracks mouse movements, drags the map around and highlights the tile
        underneath the mouse cursor.
        '''
        palette = self.palette_scene

        old_pos = tuple(map(int, self.cpd.get_text().split('x')))
        new_pos = context.event.pos
        # print old_pos, '->', new_pos
        # print 'pos =', context.event.pos

        lmb_pressed = context.event.buttons == (1, 0, 0)
        rmb_pressed = context.event.buttons == (0, 0, 1)

        if not lmb_pressed and self.cursor_mode != TilemapScene.CURSOR_MODE_DRAW:
            self.switch_to_palette_mode(context.event.pos)

        if self.cursor_mode == TilemapScene.CURSOR_MODE_PALETTE:
            x, y = context.event.pos
            tile = None
            for child in palette.palette_node.child_nodes[0].child_sprites:
                if child.get_rect().collidepoint(x, y):
                    tile = child
                    break
            # print tile
            if palette.highlighted_palette_tile is None or tile != palette.highlighted_palette_tile:
                if tile is not None:
                    palette.highlight_palette_tile(tile)
                else:
                    palette.unhighlight_palette_tile()
        else:
            is_drag = lmb_pressed or self.was_drag

            if is_drag and self.cursor_mode == TilemapScene.CURSOR_MODE_DRAG:
                # print 'drag!', context.event
                self.base_node_stack.clear()
                self.base_node.set_pos_rel(*context.event.rel)

                x, y = self.base_node.pos
                s_width, s_height = self.scene_manager.display.screen_size
                t_width, t_height = self.tilemap.get_tile_size()
                m_width, m_height = self.tilemap.get_map_size()
                # Keep our drawing area in sight.
                x = min(x, s_width - t_width)
                x = max(x, -(m_width * t_width) + t_width)
                y = min(y, s_height - t_height)
                y = max(y, -(m_height * t_height) + t_height)
                if self.base_node.pos != (x, y):
                    self.base_node.set_pos(x, y)

                if not self.was_drag:
                    pygame.mouse.set_cursor(*pygame.cursors.broken_x)
                self.was_drag = True
            elif self.cursor_mode in (TilemapScene.CURSOR_MODE_DRAG, TilemapScene.CURSOR_MODE_DRAW):
                self.make_tile_current(*context.event.pos)
                if self.highlighted_tile:
                    if lmb_pressed:
                        self.draw_current_tile()
                    elif rmb_pressed:
                        self.remove_current_tile()
            elif self.cursor_mode in (TilemapScene.CURSOR_MODE_HIGHLIGHT_ALL, TilemapScene.CURSOR_MODE_HIGHLIGHT_PATH, TilemapScene.CURSOR_MODE_HIGHLIGHT_COLUMN, TilemapScene.CURSOR_MODE_HIGHLIGHT_ROW):
                pygame.mouse.set_pos(*old_pos)
                new_pos = old_pos
        self.cpd.set_text('%dx%d' % new_pos)

        if self.highlighted_tile:
            tile_pos = self.tilemap.get_tile_pos(self.highlighted_tile)
            self.ctpd.set_text('tile: %dx%d' % tile_pos)
        else:
            self.ctpd.set_text('')

    def realign_tilemap(self):
        t_width, t_height = self.tilemap.get_tile_size()
        x, y = self.base_node.pos
        # print (x, y)
        base = x / t_width * t_width, y / t_height * t_height
        # print 'base =', base
        diff = x - x / t_width * t_width, y - y / t_height * t_height
        # print 'diff =', diff
        half = t_width / 2, t_height / 2
        # print 'half =', half
        if diff[0] < half[0]:
            # print 'pull left'
            x = base[0]
        else:
            # print 'pull right'
            x = base[0] + t_width
        if diff[1] < half[1]:
            # print 'pull top'
            y = base[1]
        else:
            # print 'pull bottom'
            y = base[1] + t_height
        # self.base_node.set_pos(x, y)
        self.base_node_stack.clear()
        self.base_node_stack.move_to(self.base_node, pos=(x, y),
                                     msecs=300, append=True)

    def __on_mouse_button_released_event(self, context):
        palette = self.palette_scene

        lmb_pressed = context.event.button == 1
        rmb_pressed = context.event.button == 3
        if self.cursor_mode in (TilemapScene.CURSOR_MODE_DRAG, TilemapScene.CURSOR_MODE_DRAW):
            if self.was_drag:
                # Realign grid.
                pygame.mouse.set_cursor(*self.default_pg_cursor)
                self.was_drag = False
                self.realign_tilemap()
            elif self.highlighted_tile:
                # print context
                if lmb_pressed:
                    self.draw_current_tile()
                elif rmb_pressed:
                    self.remove_current_tile()
            else:
                # Add additional columns and/or rows *around* the map.
                x, y = context.event.pos
                m_width, m_height = self.tilemap.get_map_size()
                t_width, t_height = self.tilemap.get_tile_size()
                x, y = self.root_node.translate_pos((x, y), self.tilemap)
                m_x, m_y = x / t_width, y / t_height
                # print (m_x, m_y), (m_width, m_height)
                if m_x >= m_width:
                    if lmb_pressed:
                        for tilemap, name in self.tilemap_layers:
                            tilemap.add_column()
                    elif rmb_pressed:
                        self.tilemap.add_column()
                if m_y >= m_height:
                    if lmb_pressed:
                        for tilemap, name in self.tilemap_layers:
                            tilemap.add_row()
                    elif rmb_pressed:
                            self.tilemap.add_row()
                if m_x < 0:
                    if lmb_pressed:
                        for tilemap, name in self.tilemap_layers:
                            tilemap.insert_column(0)
                    elif rmb_pressed:
                            self.tilemap.insert_column(0)
                    self.base_node.set_pos_rel(-t_width, 0)
                if m_y < 0:
                    if lmb_pressed:
                        for tilemap, name in self.tilemap_layers:
                            tilemap.insert_row(0)
                    elif rmb_pressed:
                        self.tilemap.insert_row(0)
                    self.base_node.set_pos_rel(0, -t_height)
                for tilemap, name in self.tilemap_layers:
                    tilemap.build_map()
        elif self.cursor_mode == TilemapScene.CURSOR_MODE_PALETTE:
            if palette.highlighted_palette_tile and lmb_pressed:
                tile_id = self.tilemap.get_tile_id(palette.highlighted_palette_tile)
                # print tile_id
                palette.set_current_tile(tile_id)
        elif self.cursor_mode in (TilemapScene.CURSOR_MODE_HIGHLIGHT_ALL, TilemapScene.CURSOR_MODE_HIGHLIGHT_PATH, TilemapScene.CURSOR_MODE_HIGHLIGHT_COLUMN, TilemapScene.CURSOR_MODE_HIGHLIGHT_ROW):
            # print context
            if self.highlighted_tile and (lmb_pressed or rmb_pressed):
                if self.cursor_mode == TilemapScene.CURSOR_MODE_HIGHLIGHT_ALL:
                    # tiles = self.tilemap.find_all(self.highlighted_tile)
                    tiles = self.selection
                elif self.cursor_mode == TilemapScene.CURSOR_MODE_HIGHLIGHT_PATH:
                    # tiles = self.tilemap.find_path(self.highlighted_tile)
                    tiles = self.selection
                elif self.cursor_mode == TilemapScene.CURSOR_MODE_HIGHLIGHT_COLUMN:
                    # x, y = self.tilemap.get_tile_pos(self.highlighted_tile)
                    # tiles = [row[x] for row in self.tilemap.get_map()]
                    tiles = self.selection
                elif self.cursor_mode == TilemapScene.CURSOR_MODE_HIGHLIGHT_ROW:
                    # x, y = self.tilemap.get_tile_pos(self.highlighted_tile)
                    # tiles = self.tilemap.get_map()[y]
                    tiles = self.selection
                if lmb_pressed:
                    tile_id = self.tilemap.get_tile_id(palette.current_tile)
                elif rmb_pressed:
                    tile_id = TileMap.TILE_SPACER_ID
                self.tilemap.set_tile_ids_of(tiles, tile_id)

    def __on_mouse_button_pressed_event(self, context):
        lmb_pressed = context.event.button == 1
        rmb_pressed = context.event.button == 3

        if self.cursor_mode == TilemapScene.CURSOR_MODE_DRAW and self.highlighted_tile:
            if lmb_pressed:
                self.draw_current_tile()
            elif rmb_pressed:
                self.remove_current_tile()

    AUTOTILE_DIRECTIONS = dict(
        tl=(-1, -1), t=(0, -1), tr=(1, -1),
        l=(-1, 0), r=(1, 0),
        bl=(-1, 1), b=(0, 1), br=(1, 1),
    )

    def __get_openings(self, x, y, autotiles):
        get_tile_id_at = self.tilemap.get_tile_id_at
        openings = []
        for key, pos in TilemapScene.AUTOTILE_DIRECTIONS.iteritems():
            id = get_tile_id_at(x + pos[0], y + pos[1])
            if id in autotiles.values():
                openings.append(key)
        return openings

    AUTOTILE_EDGES = (
        ('t', 'r', 'tr'),
        ('t', 'l', 'tl'),
        ('b', 'r', 'br'),
        ('b', 'l', 'bl'),
    )

    def __resolve_situation(self, openings):
        situation = ','.join(sorted(openings))
        # print 'situation =', situation

        # 1. Try to find exact situation.
        try:
            return AUTOTILE_SITUATIONS[situation]
        except KeyError:
            pass

        # 2. Try to find situation without uninteresting tiles.
        openings = openings[:]
        for vert, horiz, diag in TilemapScene.AUTOTILE_EDGES:
            if vert not in openings and horiz not in openings and diag in openings:
                del openings[openings.index(diag)]
        situation = ','.join(sorted(openings))
        # print 'situation (drop edges fallback) =', situation
        try:
            return AUTOTILE_SITUATIONS[situation]
        except KeyError:
            pass

        # 3. Try to find situation without uninteresting tiles.
        openings = openings[:]
        for vert, horiz, diag in TilemapScene.AUTOTILE_EDGES:
            if (vert not in openings or horiz not in openings) and diag in openings:
                del openings[openings.index(diag)]
        situation = ','.join(sorted(openings))
        # print 'situation (2. drop edges fallback) =', situation
        try:
            return AUTOTILE_SITUATIONS[situation]
        except KeyError:
            pass

        # 4. Try to find general thumb rule.
        situation = re.sub('(tl|tr|bl|br)', '', situation)
        situation = re.sub('[,]+', ',', situation)
        situation = situation.strip(',')
        # print 'situation (drop diagonal fallback) =', situation
        return AUTOTILE_SITUATIONS.get(situation, None)

    def draw_current_tile(self):
        set_tile_at = self.tilemap.set_tile_at

        # print self.highlighted_tile
        # Change highlighted tile to the current one.
        x, y = self.tilemap.get_tile_pos(self.highlighted_tile)
        cur_tile_id = self.tilemap.get_tile_id(self.palette_scene.current_tile)

        # print 'highlighted tile =', self.tilemap.get_tile_id(self.highlighted_tile),
        # print 'cur_tile_id =', cur_tile_id

        try:
            autotile_groups = self.tilemap.get_sheet().autotiles
        except AttributeError:
            set_tile_at(x, y, cur_tile_id)
            return

        if cur_tile_id not in autotile_groups:
            set_tile_at(x, y, cur_tile_id)
            return

        autotiles = autotile_groups[cur_tile_id]
        autotiles = dict([(name[len(':%s:' % cur_tile_id):], name) for name in autotiles.iterkeys()])

        openings = self.__get_openings(x, y, autotiles)
        # print 'openings =', openings

        if 'l' not in openings and 'r' not in openings and 't' not in openings and 'b' not in openings:
            # Looks like we don't have a connection - draw inner tile.
            set_tile_at(x, y, autotiles['inner'])
            return

        resolution = self.__resolve_situation(openings)
        # print 'use tile:', resolution
        if resolution is not None:
            set_tile_at(x, y, autotiles[resolution])
        # print

        for opening in openings:
            rel = TilemapScene.AUTOTILE_DIRECTIONS[opening]
            pos = x + rel[0], y + rel[1]
            openings_ = self.__get_openings(pos[0], pos[1], autotiles)
            # print 'openings_ =', openings_
            resolution = self.__resolve_situation(openings_)
            # print 'use tile:', resolution
            if resolution is not None:
                set_tile_at(pos[0], pos[1], autotiles[resolution])
            # print

    def remove_current_tile(self):
        # print self.highlighted_tile
        # Change highlighted tile to the current one.
        x, y = self.tilemap.get_tile_pos(self.highlighted_tile)
        self.tilemap.set_tile_at(x, y, TileMap.TILE_SPACER_ID)

    def __setup_hud(self):
        # Create black transparent box behind fields.
        width = self.scene_manager.display.screen_size[0]
        box = SpritePrimitives.make_rectangle(width, 10, color=(0, 0, 0), background=(0, 0, 0, 255))
        box.set_alpha(70)
        box.add_to(self.hud_node)

        self.__setup_fps()
        self.palette_scene = self.scene_manager.get_scene('palette', instanciate=True)
        self.__setup_cursor()

    def __on_screen_created_event(self, context):
        '''
        Resizes the align boxes so that the HUD stays glued.
        '''
        # print context.screen_size
        cpd = self.cpd
        box = cpd.get_align_box()
        box[0] = context.screen_size[0]
        cpd.set_align_box(*box)
        # print box
        fps = self.fps
        box = fps.get_align_box()
        box[0] = context.screen_size[0]
        fps.set_align_box(*box)
        # print box

    def select_tilemap_layer(self, zindex):
        tilemap_layers = self.tilemap_layers
        self.tilemap_current_layer = zindex
        self.tilemap = tilemap_layers.get_layer(self.tilemap_current_layer)
        num_layers = self.tilemap_layers.get_num_layers()
        for tilemap, name in self.tilemap_layers:
            if tilemap != self.tilemap:
                tilemap.set_alpha(30)
                tilemap.disable_spacer()
            else:
                tilemap.set_alpha(100)
                tilemap.enable_spacer()
                # print 'Set tilemap layer %d as current.' % zindex
                try:
                    self.ltd.text = 'current layer: %d/%d %s' % (zindex + 1, num_layers, name)
                except AttributeError:
                    pass  # Happens on first call within setup and is ok.
        event.emit('tilemap.switched_layer', dict(tilemap=self.tilemap))

    def __on_select_previous_tilemap_layer_event(self, context):
        zindex = self.tilemap_current_layer
        if zindex > 0:
            zindex -= 1
            self.select_tilemap_layer(zindex)

    def __on_select_next_tilemap_layer_event(self, context):
        num_layers = self.tilemap_layers.get_num_layers()
        zindex = self.tilemap_current_layer
        if zindex < num_layers - 1:
            zindex += 1
            self.select_tilemap_layer(zindex)

    def __on_show_all_tilemap_layers_keydown_event(self, context):
        for tilemap, name in self.tilemap_layers:
            tilemap.set_alpha(100)
            tilemap.disable_spacer()

    def __on_show_all_tilemap_layers_keyup_event(self, context):
        self.select_tilemap_layer(self.tilemap_current_layer)

    def __on_reveal_tilemap_layers_keydown_event(self, context):
        offset_x, offset_y = 0, 0
        for tilemap, name in self.tilemap_layers:
            # tilemap.set_pos_rel(offset_x, offset_y)
            stack = self.tilemap_layer_stacks[id(tilemap)]
            stack.clear()
            stack.move_to(tilemap, pos=(offset_x, offset_y), msecs=300, append=True)
            tile_size = tilemap.get_tile_size()
            offset_x += tile_size[0] / 2
            offset_y += tile_size[1] / 2
            tilemap.set_alpha(100)
            tilemap.enable_spacer()

    def __on_reveal_tilemap_layers_keyup_event(self, context):
        for tilemap, name in self.tilemap_layers:
            # tilemap.set_pos(0, 0)
            stack = self.tilemap_layer_stacks[id(tilemap)]
            stack.clear()
            stack.move_to(tilemap, pos=(0, 0), msecs=300, append=True)
        self.select_tilemap_layer(self.tilemap_current_layer)

    # @time
    def setup(self):
        super(TilemapScene, self).setup()
        self.add_default_listeners()

        self.ticker = Ticker()
        self.transition_manager = TransitionEffects()
        self.bind(self.ticker, self.transition_manager)

        self.base_node = Node('base node')
        self.base_node.order_matters = False
        self.base_node.add_to(self.root_node)
        self.hud_node = Node('hud')
        self.hud_node.add_to(self.root_node)
        self.base_node_stack = self.transition_manager.stack()
        self.bind(event.add_listener(self.__on_screen_created_event, 'display.screen.created'))

        layered_tilemap = LayeredTileMap()
        # layered_tilemap.load_layers(shared_data['layers'], default_size=(10, 10))
        layered_tilemap.load_layers(shared_data['layers'], default_size=(20, 15))  # 640x480 @32x32
        # layered_tilemap.load_layers(shared_data['layers'], default_size=(10, 2))
        # layered_tilemap.load_layers(shared_data['layers'], default_size=(2, 1))
        # layered_tilemap.load_layers(shared_data['layers'], default_size=(32, 63))
        # layered_tilemap.load_layers(shared_data['layers'], default_size=(100, 200))
        # layered_tilemap.load_layers(shared_data['layers'], default_size=(20 * 5, 15 * 5))
        layered_tilemap.maximize_map_sizes()
        layered_tilemap.build_maps()
        # Adding all elements might take a little while because of the vault
        # creating the subsurfaces for all the different tiles.
        layered_tilemap.add_to(self.base_node)
        self.tilemap_layers = layered_tilemap
        self.select_tilemap_layer(0)
        map_rect = layered_tilemap.get_rect()
        screen_rect = self.scene_manager.display.get_rect()
        screen_into_map = screen_rect.clamp(map_rect)
        # map_into_screen = map_rect.clamp(screen_rect)
        # print screen_into_map
        # print map_into_screen
        pos = map(lambda value: value * -1, screen_into_map.topleft)
        # print pos
        self.base_node.set_pos(*pos)
        self.realign_tilemap()

        self.tilemap_layer_stacks = dict()
        for tilemap, name in layered_tilemap:
            self.tilemap_layer_stacks[id(tilemap)] = self.transition_manager.stack()

        self.__setup_hud()
        self.select_tilemap_layer(0)


class RawDescriptionArgumentDefaultsHelpFormatter(argparse.RawDescriptionHelpFormatter):

    def _split_lines(self, text, width):
        return text.splitlines()

    def _get_help_string(self, action):
        help = action.help
        if '%(default)' not in action.help:
            if action.default is not argparse.SUPPRESS:
                defaulting_nargs = [argparse.OPTIONAL, argparse.ZERO_OR_MORE]
                if action.option_strings or action.nargs in defaulting_nargs:
                    help += ' (default: %(default)s)'
        return help


def main():
    parser = argparse.ArgumentParser(
        description=textwrap.dedent('''
        %s (%s)

        Loads a previously created tilesheet and shows an editor which enables you
        to create, edit and save a map.
        ''') % (APP_NAME, APP_VERSION),
        prog='tilemap_editor.py',
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('-l', '--layer-file', action='store',
                        metavar='LAYERS',
                        help='Provide filepath to the layers spec to work with.',
    )
    parser.add_argument('-s', '--sheet-file', action='store',
                        metavar='SHEET',
                        help='Provide filepath to the tilesheet vault to work with.',
    )
    parser.add_argument('-m', '--map-file', action='store',
                        metavar='MAP',
                        help='Provide filepath to the map CSV file.',
    )
    parser.add_argument('--screen-size', dest='screen_size', action='store',
                        default='800x600', metavar='WIDTHxHEIGHT',
                        help='Provide screen size (width and height) for the display.',
    )
    parser.add_argument('--fullscreen', dest='fullscreen', action='store_true',
                        help='Enable fullscreen mode.',
    )
    parser.add_argument('--debug', dest='debug', action='store_true',
                        help='Enable debugging output.',
    )
    parser.add_argument('--version', action='version',
                        version='%(prog)s ' + APP_VERSION,
                        help='Show program\'s version number and exit.')
    args = parser.parse_args()

    if args.debug:
        from diamond.helper import logging
        logging.LOG_LEVEL_THRESHOLD = logging.LOG_LEVEL_DEBUG

    if not args.layer_file:
        if not args.sheet_file and not args.map_file:
            parser.error('If you don\'t provide a layer file you have to provice a sheet and a map file!')
    if args.sheet_file and not args.map_file or not args.sheet_file and args.map_file:
        parser.error('If you specify a sheet file you also have to provide a map file and via versa.')

    # Display options
    DISPLAY_LAYOUT = {
        'screen_size': map(int, args.screen_size.split('x')),
        'fullscreen': args.fullscreen,
        'show_mouse_in_windowed_mode': True,
        'show_mouse_in_fullscreen_mode': True,
        # 'expand_in_fullscreen': True,
        # 'maximize_fullscreen': True,
    }

    # Setup data to work with.
    if args.layer_file:
        layer_path = os.path.dirname(args.layer_file)
        layer_file = os.path.basename(args.layer_file)
        # print layer_path, layer_file

        if layer_path:
            sys.path.insert(0, os.path.abspath(layer_path))
        layer_module = __import__(os.path.splitext(layer_file)[0], globals(), locals(), [], -1)

        shared_data['layers'] = layer_module.layers
    else:
        sheet_path = os.path.dirname(args.sheet_file)
        sheet_file = os.path.basename(args.sheet_file)
        # print sheet_path, sheet_file

        if sheet_path:
            sys.path.insert(0, os.path.abspath(sheet_path))
        sheet_module = __import__(os.path.splitext(sheet_file)[0], globals(), locals(), [], -1)

        shared_data['layers'] = [
            dict(sheet_vault=sheet_module, map_filename=args.map_file),
        ]

    # Setup our editor.
    manager = SceneManager()
    display = manager.setup_display(**DISPLAY_LAYOUT)
    display.set_caption('%s (%s)' % (APP_NAME, APP_VERSION))
    manager.add_scene(TilesheetScene, scene_id='tilesheet')
    manager.add_scene(TilemapScene, scene_id='tilemap')
    manager.add_scene(PaletteScene, scene_id='palette')

    # Run it!
    manager.run('tilemap')


if __name__ == '__main__':
    main()
