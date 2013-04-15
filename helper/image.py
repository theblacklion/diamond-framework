import os

import pygame
import pygame.locals as locals_


TRANSPARENCY_THRESHOLD = 230


def load(filename, colorkey=None):
    """Loads an image and optionally applies a colorkey"""
    try:
        image = pygame.image.load(filename)
    except pygame.error, message:
        print 'Cannot load image:', filename
        raise SystemExit(message)

    (root, ext) = os.path.splitext(filename)

    if ext == '.png': # are there more image types with alpha channels?
        image = image.convert_alpha()
    else:
        image = image.convert()

    if colorkey is not None:
        if colorkey is -1:
            colorkey = image.get_at((0, 0))
        image.set_colorkey(colorkey, locals_.RLEACCEL)

    return image


def blend(surface, rgba):
    """Returns a copy of a surface object with modified channels"""
    # tmp = pygame.Surface(surface.get_size(), locals_.SRCALPHA).convert_alpha()
    tmp = pygame.Surface(surface.get_size(), locals_.SRCALPHA, 32)
    tmp.fill(rgba)
    tmp.blit(surface, (0, 0), surface.get_rect(), locals_.BLEND_RGBA_MULT)
    return tmp


def darken(surface, value):
    """Returns a copy of a surface object with darkened channels"""
    # print 'darken(%s, %s)' % (surface, value)
    tmp = pygame.Surface(surface.get_size())
    value = 255 - value
    tmp.fill((value, value, value))
    surface = surface.copy()
    surface.blit(tmp, (0, 0), surface.get_rect(), locals_.BLEND_RGB_MULT)
    return surface


def brighten(surface, value):
    """Returns a copy of a surface object with brightened channels"""
    # print 'brighten(%s, %s)' % (surface, value)
    tmp = pygame.Surface(surface.get_size())
    tmp.fill((value, value, value))
    surface = surface.copy()
    surface.blit(tmp, (0, 0), surface.get_rect(), locals_.BLEND_RGB_ADD)
    return surface


def change_gamma(surface, gamma):
    """Returns a copy of a surface object with gamma changed as requested."""
    gamma = min(2.0, max(0.0, gamma))  # Clamp within 0.0 and 2.0.
    if gamma < 1.0:
        a = int(255 * (1.0 - gamma))
        surface = darken(surface, a)
        # print 'darken'
    elif gamma > 1.0:
        a = int(255 * (gamma - 1.0))
        surface = brighten(surface, a)
        # print 'brighten'
    else:
        result = surface.copy()
        result.set_alpha(surface.get_alpha())
        return result
    # print 'a =', a
    return surface


def calc_transparent_hline_length(surface, x, max_x, y):
    """Walks given horizontal line and counts transparent pixels in a row"""
    length = 0
    surface.lock()
    (r, g, b, a) = surface.get_at((x, y))
    while a < TRANSPARENCY_THRESHOLD:
        length += 1
        x += 1
        if x > max_x:
            break
        (r, g, b, a) = surface.get_at((x, y))
    surface.unlock()
    return length


def calc_solid_hline_length(surface, x, max_x, y):
    """Walks given horizontal line and counts solid pixels in a row"""
    length = 0
    surface.lock()
    (r, g, b, a) = surface.get_at((x, y))
    while a >= TRANSPARENCY_THRESHOLD:
        length += 1
        x += 1
        if x > max_x:
            break
        (r, g, b, a) = surface.get_at((x, y))
    surface.unlock()
    return length
