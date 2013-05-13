# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

# TODO Try to split display list into chunks so that we have drawable groups.
#      Next try to find out which list and group has changed and rebuilt it.
#      This should give us some reduced overhead talking with opengl.

import os
from math import sin, cos, radians
from itertools import chain
from weakref import WeakValueDictionary, ref
from Queue import Queue, Empty as Queue_Empty

import pygame
from pygame import locals as locals_

try:
    # Squeeze out some speed improvements.
    import OpenGL
    OpenGL.ERROR_CHECKING = False
    OpenGL.ERROR_LOGGING = False
    # OpenGL.FULL_LOGGING = True

    from OpenGL.GL import (
        GL_COLOR_BUFFER_BIT, GL_PROJECTION, GL_MODELVIEW, GL_TEXTURE_2D,
        GL_BLEND, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA,
        # GL_GREATER, GL_ALPHA_TEST,
        GL_TEXTURE_MAG_FILTER, GL_TEXTURE_MIN_FILTER,
        GL_NEAREST, GL_RGBA, GL_UNSIGNED_BYTE, GL_COMPILE,
        # GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_TEXTURE_WRAP_R, GL_CLAMP_TO_EDGE,
        # GL_QUADS,
        GL_TRIANGLE_STRIP,
        glEnable, glClearColor, glClear, glBlendFunc, glMatrixMode,
        glLoadIdentity,
        # glAlphaFunc,
        glTranslate, glCallList, glGenTextures,
        glBindTexture, glTexParameter, glTexImage2D, glDeleteTextures,
        glGenLists, glNewList, glColor4f, glBegin, glTexCoord2f, glVertex2f,
        glEnd, glEndList, glDeleteLists, #glPushMatrix, glPopMatrix,
        # glRotatef,
        glTexEnvf, GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE,
        GL_SCISSOR_TEST, glScissor, glDisable,  # For clipping regions of update method.
        GL_CULL_FACE, glCullFace, GL_BACK,  # For disable rendering back of quads.
    )
    from OpenGL.GLU import gluOrtho2D

    # BEGIN: Framebuffer (fbo) stuff.
    from OpenGL.GL import (
        GL_DEPTH_COMPONENT24,
        glTexParameteri,
        GL_RGB8,
        GL_RGB,
        GL_INT,
        glPushAttrib, glPopAttrib, GL_VIEWPORT_BIT, glViewport,
        # glColor3f, glNormal3f, GL_QUADS, glColor3fv, glVertex3dv,
        GL_LIGHTING,
        # glTexCoord2fv,
        GL_DEPTH_BUFFER_BIT,
        GL_LINEAR,
        glFlush,
    )
    from OpenGL.GL.EXT.framebuffer_object import (
        glGenFramebuffersEXT, glBindFramebufferEXT, GL_FRAMEBUFFER_EXT,
        glGenRenderbuffersEXT, glBindRenderbufferEXT, GL_RENDERBUFFER_EXT,
        glRenderbufferStorageEXT,
        glFramebufferRenderbufferEXT, GL_DEPTH_ATTACHMENT_EXT,
        glFramebufferTexture2DEXT, GL_COLOR_ATTACHMENT0_EXT,
        glCheckFramebufferStatusEXT, GL_FRAMEBUFFER_COMPLETE_EXT,
        glDeleteFramebuffersEXT, glDeleteRenderbuffersEXT
    )
    # END: Framebuffer (fbo) stuff.

except:
    print ('Diamond Engine requires PyOpenGL.')
    raise SystemExit

from diamond.node import Node
from diamond.helper import image
from diamond.helper.ordered_set import OrderedSet
from diamond import event
from diamond.ticker import Ticker
from threading import Lock
from diamond.decorators import time


class Texture(object):

    __instances = WeakValueDictionary()
    __textures = dict()

    def __init__(self, surface, rect):
        super(Texture, self).__init__()
        # print 'Texture.__init__(%s, %s, %s)' % (id(self), surface, rect)
        cache_id = id(surface)
        try:
            texture = Texture.__textures[cache_id][0]
            Texture.__textures[cache_id][1] += 1
        except KeyError:
            data = pygame.image.tostring(surface, 'RGBA', 0)  # 0 means not flipped
            width, height = surface.get_size()
            texture = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, texture)
            glTexParameter(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            glTexParameter(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            # glTexParameter(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            # glTexParameter(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            # glTexParameter(GL_TEXTURE_2D, GL_TEXTURE_WRAP_R, GL_CLAMP_TO_EDGE)
            glTexEnvf(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
            Texture.__textures[cache_id] = [texture, 1]
        self.texture = texture
        self.atlas_rect = surface.get_rect()
        self.tile_rect = rect
        self.surface = surface

    def __repr__(self):
        return '<Texture %s(%s, %s, %s)>' % (self.texture, self.surface, self.atlas_rect, self.tile_rect)

    def __del__(self):
        # print 'Texture.__del__(%s)' % self
        cache_id = id(self.surface)
        Texture.__textures[cache_id][1] -= 1
        if Texture.__textures[cache_id][1] <= 0:
            glDeleteTextures(self.texture)
            del Texture.__textures[cache_id]

    @classmethod
    def get_instance(cls, surface):
        # print 'Texture.get_instance(%s, %s)' % (cls, surface)
        cache_id = id(surface)
        try:
            cls.__instances[cache_id]
            return cls.__instances[cache_id]
        except KeyError:
            pass
        rect = pygame.Rect(surface.get_abs_offset(), surface.get_size())
        surface = surface.get_abs_parent()
        instance = cls(surface, rect)
        cls.__instances[cache_id] = instance
        return instance

    @classmethod
    def get_instance_cache(cls):
        return cls.__instances


class TextureDl(object):

    __instances = WeakValueDictionary()

    def rotate_point(self, angle, point, origin):
        sinT = sin(radians(angle))
        cosT = cos(radians(angle))
        return (
            origin[0] + (cosT * (point[0] - origin[0]) - sinT * (point[1] - origin[1])),
            origin[1] + (sinT * (point[0] - origin[0]) + cosT * (point[1] - origin[1])),
        )

    def __init__(self, tex, rgba, rotation):
        super(TextureDl, self).__init__()
        self.dl = glGenLists(1)
        glNewList(self.dl, GL_COMPILE)

        # print 'texture object =', tex

        texture = tex.texture
        width, height = tex.tile_rect.size

        atlas_rect = tex.atlas_rect
        tile_rect = tex.tile_rect

        # print tex
        # print 'atlas_rect =', atlas_rect
        # print 'tile_rect =', tile_rect

        try:
            p_w = 100.0 / atlas_rect.w
        except ZeroDivisionError:
            p_w = 0.0
        try:
            p_h = 100.0 / atlas_rect.h
        except ZeroDivisionError:
            p_h = 0.0
        x1 = tile_rect.x * p_w
        x2 = x1 + tile_rect.w * p_w
        y1 = tile_rect.y * p_h
        y2 = y1 + tile_rect.h * p_h

        x1 = x1 / 100.0
        x2 = x2 / 100.0
        y1 = y1 / 100.0
        y2 = y2 / 100.0

        # print 'point size =', (p_w, p_h)
        # print 'rect =', (x1, y1, x2, y2)
        # exit()

        # if rotation != 0.0:
        #     # print rotation
        #     Rect = pygame.rect.Rect

        #     org_rect = Rect(0, 0, width, height)
        #     center = org_rect.centerx, org_rect.centery

        #     rotation *= -1

        #     # tl = self.rotate_point(rotation, org_rect.topleft, center)
        #     tr = self.rotate_point(rotation, org_rect.topright, center)
        #     bl = self.rotate_point(rotation, org_rect.bottomleft, center)
        #     # br = self.rotate_point(rotation, org_rect.bottomright, center)

        #     # print 'TL =', tl
        #     # print 'TR =', tr
        #     # print 'BL =', bl
        #     # print 'BR =', br

        #     # new_rect = Rect(0, 0, 0, 0)

        #     # new_rect.unionall_ip([
        #     #     Rect((tl[0], tl[1]), (0, 0)),
        #     #     Rect((0, tr[1]), (tr[0], 0)),
        #     #     Rect((bl[0], 0), (0, bl[1])),
        #     #     Rect((0, 0), (br[0], br[1])),
        #     # ])

        #     # print org_rect
        #     # print new_rect

        #     # glTranslate(-114, 142, 0)       # 45  BL TR
        #     # glTranslate(-95, 325, 0)        # 90  BL TR
        #     # glTranslate(47, 439, 0)         # 135  BL TR
        #     # glTranslate(229, 420, 0)        # 180  BL TR
        #     # glTranslate(344, 277, 0)        # 225  BL TR
        #     # glTranslate(325, 95, 0)        # 270  BL TR
        #     # glTranslate(182, -19, 0)        # 315  BL TR
        #     # glTranslate(3.6, -1.9, 0)        # 359  BL TR
        #     glTranslate(bl[0], tr[1], 0)
        #     glRotatef(rotation, 0, 0, -1)
        #     # TODO when not using push and pop matrix we have to reverse the two above later on.

        # FIXME why is it that the fps alpha affects all other drawables?
        glColor4f(*rgba)
        # glColor4f(1.0, 1.0, 1.0, 1.0)
        # print tex, rgba
        glBindTexture(GL_TEXTURE_2D, texture)
        # glBegin(GL_QUADS)
        # glTexCoord2f(x1, y1); glVertex2f(    0,      0)  # Bottom left of the texture and quad.
        # glTexCoord2f(x1, y2); glVertex2f(    0, height)  # Top left of the texture and quad.
        # glTexCoord2f(x2, y2); glVertex2f(width, height)  # Top right of the texture and quad.
        # glTexCoord2f(x2, y1); glVertex2f(width,      0)  # Bottom right of the texture and quad.
        # glEnd()
        glBegin(GL_TRIANGLE_STRIP)
        glTexCoord2f(x1, y1); glVertex2f(0, 0)
        glTexCoord2f(x1, y2); glVertex2f(0, height)
        glTexCoord2f(x2, y1); glVertex2f(width, 0)
        glTexCoord2f(x2, y2); glVertex2f(width, height)
        glEnd()

        # # TODO create blending masks?
        # # glColor4f(0.0, 0.0, 0.0, 1.0)
        # # glColor4f(0.5, 0.5, 0.5, 1.0)
        # glColor4f(1.0, 1.0, 1.0, 1.0)
        # # brightness = 2
        # from OpenGL.GL import (GL_DST_COLOR, GL_ONE, glColor3f, GL_ZERO, GL_SRC_COLOR, GL_ADD)
        # # if brightness >= 1.0:
        #     # glBlendFunc(GL_DST_COLOR, GL_ONE);
        #     # glBlendFunc(GL_SRC_ALPHA, GL_ONE);
        #     # glColor3f(brightness-1, brightness-1, brightness-1);
        #     # glColor4f(1, 1, 1, brightness-1.0);
        # # else:
        #     # glBlendFunc(GL_ZERO, GL_SRC_COLOR);
        #     # glBlendFunc(GL_DST_COLOR, GL_ONE_MINUS_SRC_ALPHA);
        #     # glColor4f(0, 0, 0, brightness);
        #     # glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
        #     # glColor4f(0, 0, 0, 1.0);
        # # glBlendFunc(GL_DST_COLOR, GL_ONE_MINUS_SRC_ALPHA)
        # # glBlendFunc(GL_DST_COLOR, GL_ONE)
        # glTexEnvf(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_ADD)
        # a = 1.0
        # glColor4f(a, a, a, a);
        # glBegin(GL_QUADS)
        # glTexCoord2f(0, 0); glVertex2f(    0,      0)  # Bottom left of the texture and quad.
        # glTexCoord2f(0, 1); glVertex2f(    0, height)  # Top left of the texture and quad.
        # glTexCoord2f(1, 1); glVertex2f(width, height)  # Top right of the texture and quad.
        # glTexCoord2f(1, 0); glVertex2f(width,      0)  # Bottom right of the texture and quad.
        # glEnd()
        # glTexEnvf(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE)
        # glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # TODO implement rotation and scaling
        # see: http://disruption.ca/gutil/example2/example2b.html
        # if rotation != 0:
                # if rotationCenter == None:
                    # rotationCenter = (self.width / 2, self.height / 2)
                # (w,h) = rotationCenter
                # glTranslate(rotationCenter[0],rotationCenter[1],0)
                # glRotate(rotation,0,0,-1)
                # glTranslate(-rotationCenter[0],-rotationCenter[1],0)
        # if width or height:
            # if not width:
                # width = self.width
            # elif not height:
                # height = self.height
            # glScalef(width/(self.width*1.0), height/(self.height*1.0), 1.0)

        glColor4f(1.0, 1.0, 1.0, 1.0)
        glEndList()

    def __del__(self):
        # print 'TextureDl.__del__(%s)' % self
        glDeleteLists(self.dl, 1)

    @classmethod
    def get_instance(cls, tex, rgba, rotation):
        # print 'TextureDl.get_instance(%s, %s, %s, %s)' % (cls, tex, rgba, rotation)
        cache_id = hash((tex, rgba, rotation))
        try:
            return cls.__instances[cache_id]
        except KeyError:
            pass
        instance = cls(tex, rgba, rotation)
        cls.__instances[cache_id] = instance
        return instance

    @classmethod
    def get_instance_cache(cls):
        return cls.__instances


class Display(object):

    def __init__(self, screen_size=(640, 480), fullscreen=False,
                      color_depth=0, framerate=60, use_hw_accel=True,
                      scaling=1.0,
                      show_mouse_in_windowed_mode=True,
                      show_mouse_in_fullscreen_mode=False,
                      expand_in_fullscreen=False,
                      maximize_fullscreen=False,
                      vsync=True):
        super(Display, self).__init__()
        hwinfo = pygame.display.Info()
        # print hwinfo
        self.view_size = hwinfo.current_w, hwinfo.current_h
        self.screen_size = screen_size
        self.screen_size_org = screen_size  # Backup of original screen size.
        flags = locals_.OPENGL | locals_.DOUBLEBUF
        if use_hw_accel:  # TODO is this necessary with OpenGL anymore?
            flags |= locals_.HWSURFACE
        self.scaling = scaling
        self.show_mouse_in_windowed_mode = show_mouse_in_windowed_mode
        self.show_mouse_in_fullscreen_mode = show_mouse_in_fullscreen_mode
        self.expand_in_fullscreen = expand_in_fullscreen
        self.maximize_fullscreen = maximize_fullscreen
        self.fullscreen_enabled = False
        self.fullscreen_pseudo = False
        self.update_list = set()
        self.node_update_list = set()
        self.display_list = []
        self.display_list_dirty = True
        self._drawables = []
        self.drawables_dirty = False
        self._drawables_dl = None
        self.drawables_dl_dirty = True
        self.lock = Lock()
        self.ticker = Ticker(limit=10000)
        self.ticker.start()
        self.__child_to_be_removed = None
        self.__children_to_be_removed = None
        self.last_clipping_region = None
        self.clipping_enabled = False
        self.gl_clear_color = (0.0, 0.0, 0.0, 1.0)
        self.framerate = framerate
        self.vsync = vsync
        self.requested_color_depth = color_depth
        self.requested_flags = flags
        width, height = self.screen_size
        view_size = int(width * self.scaling), int(height * self.scaling)
        self.screen = None
        self.setup_screen(view_size, screen_size, flags, color_depth)
        self.clock = pygame.time.Clock()
        pygame.mouse.set_visible(self.show_mouse_in_windowed_mode)
        self.set_fullscreen(fullscreen)
        self.is_dirty = True
        self.root_node = Node('root')
        self.root_node.on_node_added(self)
        self.update()

    def __del__(self):
        # print 'Display.__del__(%s)' % self
        self.ticker.join()

    def enable_clipping(self):
        if self.last_clipping_region is None:
            glEnable(GL_SCISSOR_TEST)
            self.clipping_enabled = True

    def disable_clipping(self):
        glDisable(GL_SCISSOR_TEST)
        self.clipping_enabled = False

    def setup_screen(self, window_size, screen_size, flags, color_depth):
        self.ticker.pause()
        event.emit('display.screen.dropped', self)

        if self.screen is not None:
            glFlush()
            glDeleteFramebuffersEXT(1, [self.fbo])
            glDeleteRenderbuffersEXT(1, [self.fbo_depthbuffer])
            glDeleteTextures(self.fbo_tex)
            glDeleteLists(self._drawables_dl, 1)
            del self._drawables_dl, self.fbo, self.fbo_tex, self.screen

        # pygame.display.gl_set_attribute(pygame.locals.GL_MULTISAMPLEBUFFERS, 1)
        pygame.display.gl_set_attribute(pygame.locals.GL_SWAP_CONTROL, 1 if self.vsync else 0)

        mode = (window_size, flags, color_depth)
        # print mode
        self.screen = pygame.display.set_mode(*mode)

        # Clear the screen.
        glClearColor(*self.gl_clear_color)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # Setup the view.
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()

        # if self.fullscreen_enabled and self.fullscreen_pseudo:
        if window_size != screen_size:
            view_min = min(*window_size)
            view_max = max(*window_size)
            screen_min = min(*self.screen_size)
            screen_max = max(*self.screen_size)
            # print 'view min =', view_min, '; view_max =', view_max
            # print 'screen min =', screen_min, '; screen_max =', screen_max
            view_factor = float(view_min) / float(view_max)
            screen_factor = float(screen_min) / float(screen_max)
            # print 'view_factor =', view_factor
            # print 'screen_factor =', screen_factor
            # view_width = (view_min / max(view_factor, screen_factor))
            # print 'view_width =', view_width
            diff = int(screen_min / min(view_factor, screen_factor)) - screen_max
            # print 'diff =', diff
            new_ortho = -diff/2, screen_size[0] + diff/2, screen_size[1], 0
        else:
            new_ortho = 0, screen_size[0], screen_size[1], 0
        # print 'ortho =', new_ortho
        # TODO Can we use our z-buffer for ordering of sprites instead of doing that manually?
        #      http://wiki.delphigl.com/index.php/Tutorial_2D
        gluOrtho2D(*new_ortho)
        glMatrixMode(GL_MODELVIEW)

        # Setup texturing.
        glEnable(GL_TEXTURE_2D)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_BLEND)
        glDisable(GL_LIGHTING)

        # glAlphaFunc(GL_GREATER, 0.2)
        # glEnable(GL_ALPHA_TEST)

        glEnable(GL_CULL_FACE)
        glCullFace(GL_BACK)

        # TODO how does multisampling work??
        # from OpenGL.GL.ARB.multisample import glInitMultisampleARB
        # print glInitMultisampleARB()
        # from OpenGL.GL import GL_MULTISAMPLE_ARB
        # glEnable(GL_MULTISAMPLE_ARB)

        self.is_dirty = True
        self.display_list_dirty = True
        self._drawables_dl = glGenLists(1)
        self.last_clipping_region = None
        if self.clipping_enabled:
            self.enable_clipping()

        # BEGIN: Setup framebuffer.
        fbo = glGenFramebuffersEXT(1)
        glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, fbo)
        depthbuffer = glGenRenderbuffersEXT(1)
        glBindRenderbufferEXT(GL_RENDERBUFFER_EXT, depthbuffer)
        glRenderbufferStorageEXT(GL_RENDERBUFFER_EXT, GL_DEPTH_COMPONENT24, screen_size[0], screen_size[1])
        glFramebufferRenderbufferEXT(
            GL_FRAMEBUFFER_EXT, GL_DEPTH_ATTACHMENT_EXT, GL_RENDERBUFFER_EXT,
            depthbuffer
        )
        fbo_tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, fbo_tex)
        # NOTE: These lines are *key*, without them you'll likely get an unsupported format error,
        # ie. GL_FRAMEBUFFER_UNSUPPORTED_EXT
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexImage2D(
            GL_TEXTURE_2D, 0, GL_RGB8,
            screen_size[0], screen_size[1], 0, GL_RGB,
            GL_INT,
            None  # No data transferred.
        )
        glFramebufferTexture2DEXT(
            GL_FRAMEBUFFER_EXT, GL_COLOR_ATTACHMENT0_EXT, GL_TEXTURE_2D,
            fbo_tex,
            0  # Mipmap level, normally 0
        )
        status = glCheckFramebufferStatusEXT(GL_FRAMEBUFFER_EXT)
        assert status == GL_FRAMEBUFFER_COMPLETE_EXT, status
        self.fbo = fbo
        self.fbo_tex = fbo_tex
        self.fbo_depthbuffer = depthbuffer
        glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, 0)
        # END: Setup framebuffer.

        glNewList(self._drawables_dl, GL_COMPILE)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        # BEGIN: draw our buffer to the display list
        glBindTexture(GL_TEXTURE_2D, fbo_tex)
        x1, y1, x2, y2 = (0.0, 1.0, 1.0, 0.0)  # Render texture flipped.
        glBegin(GL_TRIANGLE_STRIP)
        glTexCoord2f(x1, y1); glVertex2f(0, 0)
        glTexCoord2f(x1, y2); glVertex2f(0, screen_size[1])
        glTexCoord2f(x2, y1); glVertex2f(screen_size[0], 0)
        glTexCoord2f(x2, y2); glVertex2f(screen_size[0], screen_size[1])
        glEnd()
        # END: draw our buffer to the display list
        glEndList()

        event.emit('display.screen.created', self)
        self.ticker.unpause()

    def set_caption(self, string):
        pygame.display.set_caption(string)

    def set_icon(self, icon):
        if type(icon) is str:
            icon = image.load(icon)
        pygame.display.set_icon(icon)

    def set_gl_clear_color(self, r, g, b, a):
        self.gl_clear_color = (r, g, b, a)
        glClearColor(*self.gl_clear_color)
        self.drawables_dl_dirty = True

    def get_root_node(self):
        return self.root_node

    def on_node_child_added(self, child):
        self.is_dirty = True
        self.display_list_dirty = True
        self.add_to_update_list(child)

    def on_node_children_added(self, children):
        self.is_dirty = True
        self.display_list_dirty = True
        [self.add_to_update_list(child) for child in children]

    def __remove_child_from_lists(self):
        if self.__child_to_be_removed is not None:
            child = self.__child_to_be_removed
            child = child()
            # try:
            #     self.update_list.remove(child)
            # except ValueError:
            #     pass
            try:
                self.display_list.remove(child)
            except ValueError:
                pass
            for index, item in enumerate(self._drawables):
                if item[2] is child:
                    del self._drawables[index]
                    break
            self.drawables_dl_dirty = True
            self.__child_to_be_removed = None

    def __remove_children_from_lists(self):
        if self.__children_to_be_removed is not None:
            children = self.__children_to_be_removed.values()
            for child in children:
                # try:
                #     self.update_list.remove(child)
                # except ValueError:
                #     pass
                try:
                    self.display_list.remove(child)
                except ValueError:
                    pass
            to_be_removed = []
            for index, item in enumerate(self._drawables):
                if item[2] in children:
                    to_be_removed.append(index)
            [self._drawables.__delitem__(index) for index in to_be_removed.__reversed__()]
            self.drawables_dl_dirty = True
            self.__children_to_be_removed = None

    def on_node_child_removed(self, child):
        if self.__child_to_be_removed is not None:
            # print 3, child, self.__child_to_be_removed
            self.on_node_children_removed([child])
            # self.__child_to_be_removed = None
        else:
            # print 4, child
            self.__child_to_be_removed = ref(child)

    # @time
    def on_node_children_removed(self, children):
        if self.__children_to_be_removed is not None:
            # print 2, children
            children = dict((id(child), child) for child in children)
            self.__children_to_be_removed.update(children)
        else:
            # print 5, children
            children = WeakValueDictionary((id(child), child) for child in children)
            self.__children_to_be_removed = children

    def on_node_child_shown(self, child):
        self.is_dirty = True
        self.display_list_dirty = True
        self.add_to_update_list(child)

    def on_node_children_shown(self, children):
        self.is_dirty = True
        self.display_list_dirty = True
        [self.add_to_update_list(child) for child in children]

    on_node_child_hidden = on_node_child_removed
    on_node_children_hidden = on_node_children_removed

    def _add_to_update_list(self, obj):
        # print self, obj
        with self.lock:
            try:
                if isinstance(obj, Node):
                    self.node_update_list.add(obj)
                else:
                    self.update_list.add(obj)
            except ReferenceError:
                pass

    # @time
    def add_to_update_list(self, obj, timestamp=0, rel_timestamp=None):
        # print obj, timestamp, rel_timestamp
        # return
        if timestamp == 0 and rel_timestamp is None:
            with self.lock:
                if isinstance(obj, Node):
                    self.node_update_list.add(obj)
                else:
                    self.update_list.add(obj)
        else:
            if rel_timestamp is not None:
                timestamp = self.ticker.get_ticks() + rel_timestamp
            else:
                timestamp = timestamp - self.ticker.get_ticks()
            self.ticker.add(self._add_to_update_list, timestamp, args=[ref(obj)], onetime=True)

    # @time
    def remove_from_update_list(self, obj):
        self.update_list.discard(obj)
        self.node_update_list.discard(obj)

    # @time
    def rebuild_display_list(self):
        items = self.root_node.get_tree_as_list()
        self.display_list = list(chain.from_iterable(items))
        self.display_list_dirty = False
        self.drawables_dirty = True
        # self.update_list = list(self.root_node.get_node_tree_as_list()) + self.display_list
        # self.node_update_list = self.root_node.get_node_tree_as_list()

    # @time
    def rebuild_drawables(self):
        width, height = self.screen_size
        drawables = self._drawables = []
        drawables_append = drawables.append
        for item in self.display_list:
            # if isinstance(item, Node):
            #     continue
            if not item.is_drawable:
                print item.parent_node, item
                continue
            if item.pos_real is None or item.rgba_inherited[3] == 0.0:
                # print 'rebuild_drawables', item, item.rgba_inherited
                continue
            x, y = item.pos_real_in_tree
            # Skip if item is out of screen.
            if x >= width or y >= height or x + item.size[0] < 0 or y + item.size[1] < 0:
                continue
            drawables_append((x, y, item))
        self.drawables_dirty = False
        self.drawables_dl_dirty = True

    # @time
    def rebuild_drawables_dl(self):
        # BEGIN: Fill framebuffer.
        width, height = self.screen_size
        fbo = self.fbo

        glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, fbo)
        glPushAttrib(GL_VIEWPORT_BIT)  # viewport is shared with the main context
        glViewport(0, 0, width, height)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        # BEGIN: rendering to the texture
        # print len(self._drawables), len(self.display_list)
        if not self.clipping_enabled:
            c_x, c_y = 0, 0
            for x, y, item in self._drawables:
                # glPushMatrix()
                # glTranslate(x, y, 0)
                glTranslate(x - c_x, y - c_y, 0)
                # if item.frame is None:
                #     print 'item without frame =', item
                glCallList(item.frame['texture_dl'].dl)
                # glPopMatrix()
                c_x, c_y = x, y
            glTranslate(-c_x, -c_y, 0)
        else:
            # Copy from above if-clause plus some region code.
            last_region = self.last_clipping_region
            c_x, c_y = 0, 0
            for x, y, item in self._drawables:
                current_region = item.parent_node.clipping_region_inherited
                if current_region != last_region:
                    # print current_region
                    glScissor(
                        current_region.x, self.screen_size[1] - current_region.y - current_region.h,
                        current_region.w, current_region.h,
                    )
                    last_region = current_region
                # glPushMatrix()
                # glTranslate(x, y, 0)
                glTranslate(x - c_x, y - c_y, 0)
                glCallList(item.frame['texture_dl'].dl)
                # glPopMatrix()
                c_x, c_y = x, y
            glTranslate(-c_x, -c_y, 0)
            self.last_clipping_region = last_region
        # END: rendering to the texture
        glPopAttrib()  # restore viewport
        glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, 0)  # unbind
        # END: Fill framebuffer.
        self.drawables_dl_dirty = False
        self.is_dirty = True

    # @time
    def update(self):
        if self.lock.acquire(False):
            update_list = chain(self.node_update_list.copy(), self.update_list.copy())
            self.node_update_list.clear()
            self.update_list.clear()
            self.lock.release()
            # [item.update() for item in update_list]
            for item in update_list:
                try:
                    item.update()
                except AttributeError:
                    # print item
                    # raise
                    pass
            # print('updated %d items.' % len(update_list))
        if self.__child_to_be_removed:
            # print 'removed child =', self.__child_to_be_removed
            self.__remove_child_from_lists()
        if self.__children_to_be_removed:
            # print 'removed children =', list(self.__children_to_be_removed)
            self.__remove_children_from_lists()
        if self.display_list_dirty:
            self.rebuild_display_list()
        if self.drawables_dirty:
            self.rebuild_drawables()
        if self.drawables_dl_dirty:
            self.rebuild_drawables_dl()
        # self.is_dirty = True  # NOTE for debugging only!
        if self.is_dirty:
            self.is_dirty = False
            glCallList(self._drawables_dl)
            # flip() may reduce FPS to e.g. 60 if vsync is enabled.
            pygame.display.flip()
        is_idle = self.clock.get_time() <= int(round(1000.0 / self.framerate))
        if is_idle:
            # print 'do some idle tasks'
            event.emit('display.update.cpu_is_idle', self)
        self.clock.tick(self.framerate)

    def is_fullscreen(self):
        return self.fullscreen_enabled

    def set_fullscreen(self, choice=True):
        # TODO throw event to pause all tickers/threads while switching!
        # surface = pygame.display.get_surface()
        # hwinfo = pygame.display.Info()
        # print hwinfo
        flags = self.requested_flags
        color_depth = self.requested_color_depth
        # print 'view_size =', self.view_size
        # print 'screen_size =', self.screen_size
        if choice is True and not self.is_fullscreen():
            pygame.mouse.set_visible(self.show_mouse_in_fullscreen_mode)
            if self.maximize_fullscreen:
                self.screen_size = self.view_size
            elif self.expand_in_fullscreen:
                # 1440/900*600
                self.screen_size = int(float(self.view_size[0]) / float(self.view_size[1]) * float(self.screen_size[1])), self.screen_size[1]
            if self.fullscreen_pseudo:
                # print 'enable pseudo fullscreen'
                flags |= locals_.NOFRAME
                self.fullscreen_enabled = True
                self.setup_screen(self.view_size, self.screen_size, flags, color_depth)
            else:
                # print 'enable fullscreen'
                flags |= locals_.FULLSCREEN
                self.fullscreen_enabled = True
                self.setup_screen(self.screen_size, self.screen_size, flags, color_depth)
        elif choice is False and self.is_fullscreen():
            # print 'disable fullscreen'
            if self.expand_in_fullscreen:
                self.screen_size = self.screen_size_org
            self.fullscreen_enabled = False
            width, height = self.screen_size
            view_size = int(width * self.scaling), int(height * self.scaling)
            self.setup_screen(view_size, self.screen_size, flags, color_depth)
            pygame.mouse.set_visible(self.show_mouse_in_windowed_mode)

    def toggle_fullscreen(self, context=None):
        if self.is_fullscreen():
            self.set_fullscreen(False)
        else:
            self.set_fullscreen(True)

    def save_screenshot(self, filename='shot_%d.png'):
        num = 0
        while os.path.exists(filename % num):
            num += 1
        pygame.image.save(self.screen, filename % num)
        return filename % num

    def get_texture_instance(self, surface):
        """Wrapper around Texture class"""
        return Texture.get_instance(surface)

    def get_texture_dl_instance(self, tex, rgba, rotation):
        """Wrapper around TextureDl class"""
        return TextureDl.get_instance(tex, rgba, rotation)

    def get_rect(self):
        return pygame.Rect(0, 0, self.screen_size[0], self.screen_size[1])
