# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

import os
import random
import collections
from threading import Thread

from diamond.array import Array
from diamond.window import Window
from diamond import event
from diamond.node import Node
from diamond.helper.logging import log_debug, log_info, log_warning
from diamond.helper.weak_ref import Wrapper
from diamond import clock
from diamond import pyglet


class Scene(object):

    def __init__(self, scene_id, manager):
        super(Scene, self).__init__()
        self.scene_id = scene_id
        self.scene_manager = manager
        self.root_node = None
        self.__bound_listeners = set()
        self.__bound_tickers = set()
        self.__bound_threads = set()
        self.__managed_objects = set()
        self.keys_pressed = set()
        self.is_paused = False

    def setup(self):
        '''
        This method is being called before the loop is being run.
        Add your own setup code at the end of this method.
        '''
        root_node = Node('Scene %s' % self.scene_id)
        root_node.add_to(self.scene_manager.window.root_node)
        self.root_node = root_node

    def bind(self, *candidates):
        has_method = lambda obj, method: hasattr(obj, method) and \
            isinstance(getattr(obj, method), collections.Callable)
        for candidate in candidates:
            obj = candidate
            if type(obj) is Wrapper:
                obj = obj.resolve()
            if type(obj) is event.Listener:
                self.__bound_listeners.add(candidate)
            elif isinstance(obj, Thread):
                if not hasattr(candidate, 'is_threaded') or candidate.is_threaded:
                    self.__bound_threads.add(candidate)
                    candidate.start()
                    # print 1, candidate
                else:
                    # print 2, candidate
                    self.__bound_tickers.add(candidate)
            elif has_method(obj, 'tick'):
                self.__bound_tickers.add(candidate)
            else:
                raise Exception('Only Listener and Ticker objects can be bond to the scene.')

    def remove_bonds(self, *candidates):
        has_method = lambda obj, method: hasattr(obj, method) and \
            isinstance(getattr(obj, method), collections.Callable)
        listeners = []
        for candidate in candidates:
            obj = candidate
            if type(obj) is Wrapper:
                obj = obj.resolve()
            if type(obj) is event.Listener:
                listeners.append(candidate)
                self.__bound_listeners.remove(candidate)
            elif isinstance(obj, Thread):
                candidate.join()
                self.__bound_threads.remove(candidate)
            elif has_method(obj, 'tick'):
                candidate.clear()
                self.__bound_tickers.remove(candidate)
            else:
                raise Exception('Only Listener and Ticker objects can be unbonded from the scene.')
        if listeners:
            event.remove_listeners(listeners)

    def remove_all_bonds(self):
        log_debug('clear tickers')
        for ticker in self.__bound_tickers:
            ticker.clear()
        log_debug('join threads')
        for thread in self.__bound_threads:
            thread.join()
        log_debug('remove listeners')
        event.remove_listeners(self.__bound_listeners)
        log_debug('clear listener list')
        self.__bound_listeners.clear()
        log_debug('clear ticker list')
        self.__bound_tickers.clear()
        log_debug('clear thread list')
        self.__bound_threads.clear()

    def add_default_listeners(self):
        window = self.scene_manager.window
        self.bind(
            event.add_listener(self.on_quit_event, 'scene.key.down',
                               context__scene__is=self,
                               context__event__key__eq='ESCAPE'),
            event.add_listener(window.toggle_fullscreen, 'scene.key.down',
                               context__scene__is=self,
                               context__event__key__eq='F11'),
        )
        # TODO only add this if platform is windows.
        self.bind(
            event.add_listener(window.toggle_fullscreen, 'scene.key.down',
                               context__scene__is=self,
                               context__event__key__eq='RETURN',
                               context__event__modifiers__contains='MOD_ALT'),
        )

    def manage(self, *candidates):
        for candidate in candidates:
            self.__managed_objects.add(candidate)

    def unmanage(self, *candidates):
        for candidate in candidates:
            self.__managed_objects.remove(candidate)

    # def setup_managed_objects(self):
    #     has_method = lambda obj, method: hasattr(obj, method) and \
    #         isinstance(getattr(obj, method), collections.Callable)
    #     for candidate in self.__managed_objects:
    #         if has_method(candidate, 'setup'):
    #             candidate.setup()

    def teardown_managed_objects(self):
        has_method = lambda obj, method: hasattr(obj, method) and \
            isinstance(getattr(obj, method), collections.Callable)
        for candidate in self.__managed_objects:
            if has_method(candidate, 'teardown'):
                candidate.teardown()

    def teardown(self):
        '''
        This method is being called before the scene object is being killed.
        It clears all listeners and should clean up everything you've set up
        within your setup method above.
        Add your own teardown code before this method.
        '''
        # print('Scene.teardown')
        log_debug('\n1. unmanage all objects')
        self.teardown_managed_objects()
        self.unmanage(*self.__managed_objects)
        log_debug('\n2. remove_all_bonds')
        self.remove_all_bonds()
        log_debug('\n3. remove_all')
        self.root_node.remove_all()
        log_debug('\n4. remove_from_parent')
        self.root_node.remove_from_parent()
        log_debug('\n5. del self.root_node')
        del self.root_node
        log_debug('\n6. done')

    def tick(self, dt):
        # TODO also support Wrapper?
        [ticker.tick() for ticker in self.__bound_tickers]

    def pause(self):
        if not self.is_paused:
            [ticker.pause() for ticker in self.__bound_tickers]
            [thread.pause() for thread in self.__bound_threads]
            self.is_paused = True

    def unpause(self):
        if self.is_paused:
            [ticker.unpause() for ticker in self.__bound_tickers]
            [thread.unpause() for thread in self.__bound_threads]
            self.is_paused = False

    def show(self):
        '''Transition for showing a scene.'''
        # if self.root_node.is_hidden:
        #     self.root_node.show()
        pass

    def hide(self):
        '''Transition for hiding a scene.'''
        # if not self.root_node.is_hidden:
        #     self.root_node.hide()
        pass

    def on_quit_event(self, context):
        event.emit('scene.quit', self)

    def __del__(self):
        log_debug('Scene.__del__(%s)' % self)


class SceneManager(object):

    def __init__(self):
        super(SceneManager, self).__init__()
        self.window = None
        self.scenes = {}
        self.scene_tickers = []
        self.active_scene_id = None
        self._listeners = [
            event.add_listener(self._on_window_key_down_event, 'window.key.down'),
            event.add_listener(self._on_window_key_up_event, 'window.key.up'),
            event.add_listener(self._on_scene_quit_event, 'scene.quit'),
        ]
        log_info('Initialized.')

    def setup_window(self, **kwargs):
        self.window = Window(**kwargs)
        return self.window

    def add_scene(self, Scene, scene_id=None, **setup_kwargs):
        if scene_id is None:
            scene_id = ('<%s>' % random.random()).replace('.', '')
        log_info('Adding scene %s with ID "%s".' % (Scene, scene_id))
        self.scenes[scene_id] = dict(
            cls=Scene,
            setup_kwargs=setup_kwargs,
            instance=None,
            scene_id=scene_id,  # Backref for faster looping.
        )

    def create_scene(self, scene_id):
        time = clock.get_ticks()
        try:
            scene_frame = self.scenes[scene_id]
        except KeyError:
            raise Exception('Unknown scene ID: %s' % scene_id)
        if scene_frame['instance'] is not None:
            return scene_frame['instance']
        log_info('Creating scene with ID "%s".' % scene_id)
        scene = scene_frame['cls'](scene_id, self)
        scene_frame['instance'] = scene
        self.scene_tickers.append(scene.tick)
        clock.shift(clock.get_ticks() - time)
        return scene_frame['instance']

    def setup_scene(self, scene_id):
        time = clock.get_ticks()
        try:
            scene_frame = self.scenes[scene_id]
        except KeyError:
            raise Exception('Unknown scene ID: %s' % scene_id)
        scene = scene_frame['instance']
        log_info('Setting up scene %s with ID: %s' % (scene, scene_id))
        scene.setup(**scene_frame['setup_kwargs'])
        clock.shift(clock.get_ticks() - time)

    def teardown_scene(self, scene_id):
        time = clock.get_ticks()
        try:
            scene_frame = self.scenes[scene_id]
        except KeyError:
            raise Exception('Unknown scene ID: %s' % scene_id)
        scene = scene_frame['instance']
        log_info('Tearing down scene %s with ID "%s".' % (scene, scene_id))
        scene.teardown()
        self.scene_tickers.remove(scene.tick)
        scene_frame['instance'] = None
        log_info('Deleted scene instance with ID: %s' % scene_id)
        clock.shift(clock.get_ticks() - time)

    def show_scene(self, scene_id):
        try:
            scene_frame = self.scenes[scene_id]
        except KeyError:
            raise Exception('Unknown scene ID: %s' % scene_id)
        if scene_frame['instance'] is None:
            self.create_scene(scene_id)
            self.setup_scene(scene_id)
        self.active_scene_id = scene_id
        scene_frame['instance'].keys_pressed.clear()
        scene_frame['instance'].show()

    def hide_scene(self, scene_id):
        try:
            scene_frame = self.scenes[scene_id]
        except KeyError:
            raise Exception('Unknown scene ID: %s' % scene_id)
        if scene_frame['instance'] is None:
            raise Exception('Error hiding scene. Scene not instanciated: %s' % scene_id)
        scene_frame['instance'].keys_pressed.clear()
        scene_frame['instance'].hide()
        self.active_scene_id = None

    def get_scene(self, scene_id, instanciate=False):
        try:
            scene_frame = self.scenes[scene_id]
        except KeyError:
            raise Exception('Unknown scene ID: %s' % scene_id)
        if scene_frame['instance'] is None:
            if not instanciate:
                raise Exception('Error getting scene. Scene not instanciated: %s' % scene_id)
            else:
                self.create_scene(scene_id)
                self.setup_scene(scene_id)
        return scene_frame['instance']

    # TODO
    def _on_window_mouse_motion_event(self, context):
        # translate_view_to_screen_coord = self.window.translate_view_to_screen_coord
        # old_pos = translate_view_to_screen_coord(*pygame.mouse.get_pos())
        scene_id = self.active_scene_id
        if scene_id is not None:
            #     if pg_event.type == pygame.locals.MOUSEMOTION:
            #         pos = translate_view_to_screen_coord(*pg_event.pos)
            #         rel = pos[0] - old_pos[0], pos[1] - old_pos[1]
            #         old_pos = pos
            #         pg_event = pygame.event.Event(pg_event.type, dict(
            #             buttons=pg_event.buttons,
            #             pos=pos,
            #             rel=rel,
            #         ))
            event.emit('scene.mouse.motion', Array(
                scene=self.scenes[scene_id]['instance'],
                event=context,
            ))

    # TODO
    def _on_window_mouse_button_down_event(self, context):
        scene_id = self.active_scene_id
        if scene_id is not None:
            #     elif pg_event.type in (pygame.locals.MOUSEBUTTONDOWN, pygame.locals.MOUSEBUTTONUP):
            #         pos = translate_view_to_screen_coord(*pg_event.pos)
            #         old_pos = pos
            #         pg_event = pygame.event.Event(pg_event.type, dict(
            #             button=pg_event.button,
            #             pos=pos,
            #         ))
            #     event.emit('scene', Array(
            #         scene=scene_instance, event=pg_event))
            event.emit('scene.mouse.button.down', Array(
                scene=self.scenes[scene_id]['instance'],
                event=context,
            ))

    # TODO
    def _on_window_mouse_button_up_event(self, context):
        scene_id = self.active_scene_id
        if scene_id is not None:
            #     elif pg_event.type in (pygame.locals.MOUSEBUTTONUP, pygame.locals.MOUSEBUTTONUP):
            #         pos = translate_view_to_screen_coord(*pg_event.pos)
            #         old_pos = pos
            #         pg_event = pygame.event.Event(pg_event.type, dict(
            #             button=pg_event.button,
            #             pos=pos,
            #         ))
            #     event.emit('scene', Array(
            #         scene=scene_instance, event=pg_event))
            event.emit('scene.mouse.button.up', Array(
                scene=self.scenes[scene_id]['instance'],
                event=context,
            ))

    def _on_window_key_down_event(self, context):
        scene_id = self.active_scene_id
        if scene_id is not None:
            self.scenes[scene_id]['instance'].keys_pressed.add(context.key)
            event.emit('scene.key.down', Array(
                scene=self.scenes[scene_id]['instance'],
                event=context,
            ))

    def _on_window_key_up_event(self, context):
        scene_id = self.active_scene_id
        if scene_id is not None:
            self.scenes[scene_id]['instance'].keys_pressed.discard(context.key)
            event.emit('scene.key.up', Array(
                scene=self.scenes[scene_id]['instance'],
                event=context,
            ))

    def _on_scene_quit_event(self, context):
        scene = context
        scene_id = scene.scene_id
        self.teardown_scene(scene_id)
        if self.active_scene_id == scene_id:
            self.active_scene_id = None
            self.window.dispatch_event('on_close')

    def _loop_scenes(self):
        scenes = self.scenes.values()
        for scene in scenes:
            if scene['instance'] is not None:
                event.emit('scene.ready', scene['instance'])
                scene['instance'].show()

        # Changing the time offset is necessary to compensate the startup time.
        # This also ensures that tickers won't skip ahead on startup.
        clock.reset()

        tickers = self.scene_tickers
        pyglet.clock.schedule(lambda dt: [ticker(dt) for ticker in tickers])
        pyglet.app.run()

        for scene in scenes:
            if scene['instance'] is not None:
                self.teardown_scene(scene['scene_id'])

    def run(self, scene_id=None):
        event.emit('scenemanager.ready', self)

        if scene_id is not None:
            self.active_scene_id = scene_id
        else:
            scene_id = self.active_scene_id

        # Instanciate active scene if not already done.
        if scene_id is None:
            # If we have only one scene, try to use it anyway.
            if len(self.scenes) == 1:
                scene_id = self.scenes.keys()[0]
                self.active_scene_id = scene_id
            else:
                raise Exception('SceneManager has no active scene to work with!')
        self.create_scene(scene_id)
        self.setup_scene(scene_id)

        # We enclose our loop in order to have it easier with our GC.
        self._loop_scenes()

        event.remove_listeners(self._listeners)

        del self.window  # Tell window to clean it up.

        # Catch statistics and if some found output things.
        log_info('Checking for stuff that should be cleaned up already.')
        listeners = event.get_listeners()
        tickers = event.emit('ticker.dump')
        if listeners or tickers:
            log_warning('Found stuff that should be cleaned up earlier!')
            if listeners:
                log_warning('Events:')
                for key, val in listeners.iteritems():
                    log_warning({key: val})
            if tickers:
                log_warning('Tickers:')
                for func, items in tickers:
                    log_warning((func, items))

        log_info('Done.')
