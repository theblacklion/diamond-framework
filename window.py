# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

from diamond import pyglet
from diamond.node import Node
from diamond import event
from diamond.array import Array
from diamond.fbo import FBO

# Load this into our namespace for easier reference.
from pyglet.window import key


class Window(pyglet.window.Window):

    # When resizing the viewport and its nearly the window size use it instead.
    viewport_resize_correction_threshold = 50

    def __init__(self, width=640, height=480, adapt_width=False, adapt_height=False, **kwargs):
        if 'config' not in kwargs:
            kwargs['config'] = pyglet.gl.Config(
                # major_version=3, minor_version=0,  # TODO Do we really need OpenGL 3?
                sample_buffers=1, samples=4,
                double_buffer=True,
            )

        screen = pyglet.window.get_platform().get_default_display().get_default_screen()
        view_size = screen.width, screen.height

        screen_size = width, height
        if adapt_width:
            height_factor = view_size[1] / float(screen_size[1])
            # print 1, height_factor
            width = height_factor * screen_size[0]
            # print 2, width
            x = view_size[0] - width
            # print x
            screen_size = screen_size[0] + int(x / height_factor), screen_size[1]
        elif adapt_height:
            width_factor = view_size[0] / float(screen_size[0])
            height = width_factor * screen_size[1]
            y = view_size[1] - height
            screen_size = screen_size[0], screen_size[1] + int(y / width_factor)
        elif adapt_width and adapt_height:
            raise Exception('Only width *or* height of screen_size can be auto-adapted. Got both at once. Please decide.')

        # print screen_size
        kwargs['width'], kwargs['height'] = screen_size
        self._screen_size = screen_size
        self._view_size = view_size

        if 'fullscreen' in kwargs:
            fullscreen = kwargs.pop('fullscreen')
        else:
            fullscreen = False

        super(Window, self).__init__(**kwargs)
        self._batch = pyglet.graphics.Batch()
        self.root_node = Node()
        self.root_node.window = self

        self.fps_display = pyglet.window.FPSDisplay(self)

        self.fbo = FBO(*screen_size)
        self._setup_fbo_dl()
        # self._setup_fbo_batch()

        if fullscreen:
            self.toggle_fullscreen()

    def __del__(self):
        pyglet.gl.glDeleteLists(self._fbo_dl, 1)
        super(Window, self).__del_()

    # def _setup_fbo_batch(self):
    #     self._fbo_batch = pyglet.graphics.Batch()
    #     blend_src = pyglet.gl.GL_SRC_ALPHA
    #     blend_dest = pyglet.gl.GL_ONE_MINUS_SRC_ALPHA
    #     group = pyglet.sprite.SpriteGroup(self.fbo.pyglet_texture, blend_src, blend_dest)
    #     x, y = 0, 0
    #     w, h = self._screen_size
    #     tex_coords = (
    #         x, y + h, 0,  # bottom left
    #         x + w, y + h, 0,  # bottom right
    #         x + w, y, 0,  # top right
    #         x, y, 0,  # top left
    #     )
    #     self._vertex_list = self._fbo_batch.add(4, pyglet.gl.GL_QUADS, group,
    #         'v2i/dynamic',
    #         'c4B', ('t3i', tex_coords))
    #     # Update color.
    #     self._vertex_list.colors[:] = [255, 255, 255, 255] * 4
    #     # Update vertices.
    #     x1 = x
    #     y1 = y
    #     x2 = w
    #     y2 = h
    #     vertices = [x1, y1, x2, y1, x2, y2, x1, y2]
    #     self._vertex_list.vertices[:] = vertices

    # def __del__(self):
    #     try:
    #         if self._vertex_list is not None:
    #             self._vertex_list.delete()
    #     except:
    #         pass

    def _setup_fbo_dl(self):
        import ctypes
        self._fbo_dl = ctypes.c_uint(0)
        gl = pyglet.gl
        self._fbo_dl = gl.glGenLists(1)
        gl.glNewList(self._fbo_dl, gl.GL_COMPILE)
        gl.glEnable(gl.GL_TEXTURE_2D)
        gl.glColor3f(1,1,1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.fbo.img)
        x1, y1, x2, y2 = (0.0, 1.0, 1.0, 0.0)  # Render texture flipped.
        gl.glBegin(gl.GL_TRIANGLE_STRIP)
        for t, v in (
                ((x1, y1), (0, 0)),
                ((x1, y2), (0, self._screen_size[1])),
                ((x2, y1), (self._screen_size[0], 0)),
            ):
            gl.glTexCoord2f(*t)
            gl.glVertex2f(*v)
        gl.glTexCoord2f(x2, y2)
        gl.glVertex2f(*self._screen_size)
        gl.glEnd()
        gl.glEndList()

    def on_resize(self, width, height):
        gl = pyglet.gl
        w, h = self._screen_size
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glLoadIdentity()

        # 768 / 480.0 = 1.6
        # 640 * 1.6 = 1024
        # 1366 - 1024 = 342
        # 342 / 2 = 171
        height_factor = height / float(h)
        # print 1, height_factor
        v_width = height_factor * w
        # print 2, v_width
        x = int((width - v_width) / 2)
        # print 3, x
        if x < 0:
            v_width += x * 2
            x = 0
        # print 'x =', x

        width_factor = width / float(w)
        # print 1, width_factor
        v_height = width_factor * h
        # print 2, v_height
        y = int((height - v_height) / 2)
        # print 3, y
        if y < 0:
            v_height += y * 2
            y = 0
        # print 'y =', y

        threshold = self.viewport_resize_correction_threshold
        if v_width > width - threshold and v_width < width + threshold:
            x = 0
            v_width = width
        if v_height > height - threshold and v_height < height + threshold:
            y = 0
            v_height = height

        # print 'viewport =', (x, y, int(v_width), int(v_height))
        gl.glViewport(x, y, int(v_width), int(v_height))

        gl.glOrtho(0, w, h, 0, -1, 1)
        gl.glMatrixMode(gl.GL_MODELVIEW)

    def on_draw(self):
        self.fbo.attach()
        self.clear()
        self._batch.draw()
        self.fps_display.draw()
        self.fbo.detach()

        pyglet.gl.glCallList(self._fbo_dl)
        # self._fbo_batch.draw()

    # TODO Decission required: Do we want to overwrite the close handler?

    def on_key_press(self, symbol, modifiers):
        event.emit('window.key.down', Array(
            window=self,
            key=key.symbol_string(symbol),
            modifiers=key.modifiers_string(modifiers),
        ))

    def on_key_release(self, symbol, modifiers):
        event.emit('window.key.up', Array(
            window=self,
            key=key.symbol_string(symbol),
            modifiers=key.modifiers_string(modifiers),
        ))

    # TODO implement mouse events.
    # def on_mouse_motion(self, x, y, dx, dy):
    #     print 'mouse motion:', x, y, dx, dy

    # def on_mouse_press(self, x, y, button, modifiers):
    #     print 'mouse button down:', x, y, button, modifiers

    # def on_mouse_release(self, x, y, button, modifiers):
    #     print 'mouse button up:', x, y, button, modifiers

    # def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
    #     print 'mouse drag:', x, y, dx, dy, buttons, modifiers

    # def on_mouse_enter(self, x, y):
    #     print 'mouse enter:', x, y

    # def on_mouse_leave(self, x, y):
    #     print 'mouse leave:', x, y

    # def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
    #     print 'mouse scroll:', x, y, scroll_x, scroll_y

    def toggle_fullscreen(self):
        self.set_fullscreen(fullscreen=not self._fullscreen)
