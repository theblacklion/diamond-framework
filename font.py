# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

import pygame
from pygame.locals import SRCALPHA, RLEACCEL

from diamond.fonts import internal as DEFAULT_FONT
from diamond.sprite import Sprite
from diamond.vault import GeneratedVault
import diamond.helper.image as image_helper


class TTFFont(object):
    """Creates a renderable font from an true-type-font"""

    def __init__(self, vault):
        super(TTFFont, self).__init__()

        # gather data from vault
        self.name = vault.name
        self.size = vault.size
        self.color = vault.color

        # setup font
        self.font = pygame.font.SysFont(self.name, self.size)

    def render(self, string):
        return self.font.render(string, True, self.color).convert_alpha()


SFONT_HINT = '''
    ! " # $ % & ' ( ) * + , - . / 0 1 2 3 4 5 6 7 8 9 : ; < = > ? @
    A B C D E F G H I J K L M N O P Q R S T U V W X Y Z [ \ ] ^ _ `
    a b c d e f g h i j k l m n o p q r s t u v w x y z { | } ~
'''


class SFont(object):
    """Creates a renderable font from an sfont (http://nostatic.org/sfont/)"""

    def __init__(self, vault):
        """Gathers data from vault"""
        super(SFont, self).__init__()

        self.hint = getattr(vault, 'hint', SFONT_HINT).replace("\n", '').replace(' ', '')
        self.name = str(vault) if not hasattr(vault, 'start') else vault.name
        self.start = getattr(vault, 'start', ord(self.hint[0]))
        self.space = getattr(vault, 'space', None)
        self.transparent = getattr(vault, 'transparent', None)

        self.load_image(vault)
        self.prepare()

    def load_image(self, vault):
        if not hasattr(vault, 'image_data'):
            vault.image_data = image_helper.load(vault.filename)

        self.sheet = vault.image_data
        self.rect = self.sheet.get_rect()

        if self.transparent is not None:
            (x, y) = self.transparent

            if x < 0: x = self.rect.w - 2 - x
            if y < 0: y = self.rect.h - 2 - y

            colorkey = self.sheet.get_at((x, y))
            self.sheet.set_colorkey(colorkey, RLEACCEL)

    def prepare(self):
        """Scans surface for holes in the pink top line and finds letters"""
        x = 0
        w = self.rect.w
        h = self.rect.h
        transparent = 0
        letters = {}
        hint = self.hint
        hint_length = len(hint)
        cur_char = 0 if hint else self.start
        self.sheet.lock() # lock surface for faster pixel access
        space = 0; i = 1 # auto-space
        while x < w:
            # skip non transparent part
            x += image_helper.calc_solid_hline_length(self.sheet, x, w - 1, 0)

            # get hole for letter
            if x < w:
                transparent = image_helper.calc_transparent_hline_length(self.sheet, x, w - 1, 0)
            else:
                transparent = 0

            # associate hole with letter
            if x < w and transparent > 1:  # Some fonts finish with a 1px hole. We skip this.
                if hint:
                    if cur_char < hint_length:
                        char = hint[cur_char]
                    else:
                        print '%s: unknown char "%s" (%d) in font template.' % (self.name, chr(cur_char), cur_char)
                else:
                    char = chr(cur_char)

                letters[char] = pygame.Rect(x, 1, transparent, h - 1)
                cur_char += 1

                space += transparent; i += 1 # auto-space

            x += transparent
        self.sheet.unlock()

        if self.space is None: # auto-space
            self.space = space / i

        self.letters = letters

    def render(self, string):
        """Renders font on a new surface"""
        sheet = self.sheet
        letters = self.letters
        space = self.space
        rects = []
        w = 0

        # gather rects for string and summize width
        for c in string:
            if c != ' ' and not letters.has_key(c):
                print 'invalid letter "%s" for sfont "%s" in string "%s"' % \
                      (c, self.name, string)
                c = ' '

            if c == ' ':
                rect = space
                w += space
            else:
                rect = letters[c]
                w += letters[c].w

            rects.append(rect)

        # build proper surface
        surface = pygame.Surface((w, self.rect.h), SRCALPHA).convert_alpha()
        surface.fill((0, 0, 0, 0))

        # draw letters on surface
        x = 0
        for rect in rects:
            if type(rect) is not pygame.Rect:
                x += rect # should be a space
                continue

            surface.blit(sheet, (x, 0), rect)
            x += rect.w

        return surface


class FixedSFont(SFont):

    def __init__(self, vault):
        if not hasattr(vault, 'length'):
            raise Exception('cannot init FixedSFont without length attribute.')
        else:
            self.length = vault.length

        super(FixedSFont, self).__init__(vault)

    def prepare(self):
        """Scans surface and finds letters"""
        x = 0
        w = self.rect.w
        h = self.rect.h
        length = self.length
        char_width = w / length
        letters = {}
        hint = self.hint
        hint_length = len(hint)
        cur_char = 0 if hint else self.start
        space = 0; i = 1 # auto-space
        while x < w:
            # associate with letter
            if x < w:
                if hint:
                    if cur_char < hint_length:
                        char = hint[cur_char]
                    else:
                        print '%s: unknown char "%s" (%d) in font template.' % (self.name, chr(cur_char), cur_char)
                else:
                    char = chr(cur_char)

                letters[char] = pygame.Rect(x, 1, char_width, h - 1)
                cur_char += 1

                space += char_width; i += 1 # auto-space

            x += char_width

        if self.space is None: # auto-space
            self.space = space / i

        self.letters = letters


class Font(Sprite):
    """Base font class wrapper based on a sprite."""

    def __init__(self, vault=None):
        if vault is None:
            vault = DEFAULT_FONT
        if vault.type == 'sfont':
            self.font = SFont(vault)
        elif vault.type == 'fixedsfont':
            self.font = FixedSFont(vault)
        elif vault.type == 'ttf':
            self.font = TTFFont(vault)
        else:
            raise Exception('unknown font type specified in: %s' % vault)
        self._text = ''

        vault_ = GeneratedVault()
        sprite = vault_.add_sprite(self.font.name)
        super(Font, self).__init__(vault=sprite)
        self.text_is_dirty = False
        self.__update_text()

    def __repr__(self):
        pos = '%s,%s' % self.pos
        name = 'Font.Sprite(%s@%s)' % (self.font.name, pos)
        if self.parent_node:
            return '<%s -> %s>' % (self.parent_node, name)
        else:
            return '<%s>' % name

    def __update_text(self):
        vault = self.vault
        surface = self.font.render(self._text)
        size = surface.get_size()
        rect = (0, 0, size[0], size[1])
        hotspot = (0, 0)
        delta = (0, 0)
        msecs = 0
        vault.get_vault().set_surface(surface)
        vault.clear_actions()
        action = vault.add_action('none')
        frame_vault = action.add_frame(rect, hotspot, delta, msecs)
        if self.display:
            # And now update our texture.
            frame = self.frame
            # print frame
            texture = self.display.get_texture_instance(surface)
            rgba = self.rgba_inherited
            rotation = self.rotation  # TODO should use rotation_inherited
            texture_dl = self.display.get_texture_dl_instance(texture, rgba, rotation)
            frame.update(dict(
                texture=texture,
                texture_dl=texture_dl,
                frame_vault=frame_vault,
            ))
            self.size = frame_vault.rect[2:]
            if self.align_box:
                self.recalc_real_pos()
            self.is_dirty = True

    def update(self):
        if self.text_is_dirty:
            if self.frame is not None:
                self.__update_text()
                self.text_is_dirty = False
            else:
                self._add_to_update_list()
        super(Font, self).update()

    def set_text(self, text):
        text = str(text)
        if self._text != text:
            self._text = text
            self.text_is_dirty = True
            self._add_to_update_list()

    def set(self, data):
        self.set_text(str(data))

    def get_text(self):
        return self._text

    def get(self):
        return self._text

    def get_int(self):
        return int(self._text)

    def get_float(self):
        return float(self._text)

    def __add__(self, value):
        type_ = type(value)
        # print '__add__', self._text, type_, value
        self.set_text(type_(self._text) + value)
        return self

    def __sub__(self, value):
        type_ = type(value)
        self.set_text(type_(self._text) - value)
        return self

    def __mul__(self, value):
        type_ = type(value)
        self.set_text(type_(self._text) * value)
        return self

    def __div__(self, value):
        type_ = type(value)
        self.set_text(type_(self._text) / value)
        return self

    text = property(get_text, set_text)
