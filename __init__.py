import sys
from os.path import abspath, join, dirname
from time import time

_startup_time = time() * 1000

# Make sure that pyglet can be found.
sys.path.insert(0, abspath(join(dirname(__file__), 'thirdparty', 'pyglet')))

import pyglet


# if True:
#     array = pyglet._ModuleProxy('array')
#     collision = pyglet._ModuleProxy('collision')
#     decorators = pyglet._ModuleProxy('decorators')
#     app = pyglet._ModuleProxy('app')
#     app = pyglet._ModuleProxy('app')
#     app = pyglet._ModuleProxy('app')
#     app = pyglet._ModuleProxy('app')
#     app = pyglet._ModuleProxy('app')
#     app = pyglet._ModuleProxy('app')
#     app = pyglet._ModuleProxy('app')
#     app = pyglet._ModuleProxy('app')
#     app = pyglet._ModuleProxy('app')
#     app = pyglet._ModuleProxy('app')
#     app = pyglet._ModuleProxy('app')
#     app = pyglet._ModuleProxy('app')
#     app = pyglet._ModuleProxy('app')
#     app = pyglet._ModuleProxy('app')
#     app = pyglet._ModuleProxy('app')

# # Fool py2exe, py2app into including all top-level modules (doesn't understand
# # lazy loading)
# if False:
#     import app
