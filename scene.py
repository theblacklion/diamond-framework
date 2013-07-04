# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

import os
import random
import collections
from threading import Thread

import pygame
from pygame.time import get_ticks, wait

from diamond.array import Array
from diamond.display import Display
from diamond import event
from diamond.node import Node
from diamond.helper.logging import log_debug, log_info, log_warning
from diamond.helper.weak_ref import Wrapper
# from diamond.ticker import Ticker


class QuitSceneEvent(Exception):
    pass


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
        self.is_paused = False

    def setup(self):
        '''
        This method is being called before the loop is being run.
        Add your own setup code at the end of this method.
        '''
        root_node = Node('Scene %s' % self.scene_id)
        root_node.add_to(self.scene_manager.display.get_root_node())
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
        display = self.scene_manager.display
        self.bind(
            event.add_listener(self.on_quit_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.QUIT),
            event.add_listener(self.on_quit_event, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYDOWN,
                               context__event__key__eq=pygame.locals.K_ESCAPE),
            event.add_listener(display.toggle_fullscreen, 'scene.event.system',
                               context__scene__is=self,
                               context__event__type__eq=pygame.locals.KEYDOWN,
                               context__event__key__eq=pygame.locals.K_F1),
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
        log_debug('\n0. unmanage all objects')
        self.teardown_managed_objects()
        self.unmanage(*self.__managed_objects)
        log_debug('\n5. remove_all_bonds')
        self.remove_all_bonds()
        log_debug('1. detach_from_display')
        self.root_node.detach_from_display()
        log_debug('\n2. remove_all')
        self.root_node.remove_all()
        log_debug('\n3. remove_from_parent')
        self.root_node.remove_from_parent(cascade=True)
        log_debug('\n4. del self.root_node')
        del self.root_node
        log_debug('\n6. done')

    def loop_iteration(self):
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
        if self.root_node.is_hidden:
            self.root_node.show()

    def hide(self):
        '''Transition for hiding a scene.'''
        if not self.root_node.is_hidden:
            self.root_node.hide()

    def on_quit_event(self, context):
        raise QuitSceneEvent()

    def __del__(self):
        log_debug('Scene.__del__(%s)' % self)


class SceneManager(object):

    def __init__(self):
        super(SceneManager, self).__init__()
        self.display = None
        # os.environ['SDL_VIDEO_CENTERED'] = '1'
        pygame.mixer.pre_init(44100, -16, 2, 1024)
        pygame.init()
        self.scenes = {}
        self.active_scene_id = None
        log_info('Initialized.')

    def __del__(self):
        log_info(self)

    def setup_display(self, *args, **kwargs):
        self.display = Display(*args, **kwargs)
        return self.display

    def add_scene(self, Scene, *args, **kwargs):
        try:
            scene_id = kwargs.pop('scene_id')
        except KeyError:
            scene_id = None
        if scene_id is None:
            scene_id = ('<%s>' % random.random()).replace('.', '')
        log_info('Adding scene %s with ID "%s".' % (Scene, scene_id))
        self.scenes[scene_id] = dict(
            prototype=(Scene, args, kwargs),
            instance=None,
            scene_id=scene_id,  # Backref for faster looping.
        )

    def create_scene(self, scene_id):
        try:
            scene_frame = self.scenes[scene_id]
        except KeyError:
            raise Exception('Unknown scene ID: %s' % scene_id)
        if scene_frame['instance'] is not None:
            return scene_frame['instance']
        Scene, args, kwargs = scene_frame['prototype']
        log_info('Creating scene with ID "%s".' % scene_id)
        scene = Scene(scene_id, self)
        scene_frame['instance'] = scene
        return scene_frame['instance']

    def setup_scene(self, scene_id):
        try:
            scene_frame = self.scenes[scene_id]
        except KeyError:
            raise Exception('Unknown scene ID: %s' % scene_id)
        Scene, args, kwargs = scene_frame['prototype']
        scene = scene_frame['instance']
        cur_ticks = get_ticks()
        log_info('Setting up scene %s with ID: %s' % (scene, scene_id))
        scene.setup(*args, **kwargs)
        # Changing the ticker offset is necessary to compensate the startup time.
        # TODO test this!
        event.emit('ticker.force_ticks', dict(ticks=cur_ticks))

    def teardown_scene(self, scene_id):
        try:
            scene_frame = self.scenes[scene_id]
        except KeyError:
            raise Exception('Unknown scene ID: %s' % scene_id)
        scene = scene_frame['instance']
        log_info('Tearing down scene %s with ID "%s".' % (scene, scene_id))
        scene.teardown()
        scene_frame['instance'] = None
        log_info('Deleted scene instance with ID: %s' % scene_id)

    def show_scene(self, scene_id):
        try:
            scene_frame = self.scenes[scene_id]
        except KeyError:
            raise Exception('Unknown scene ID: %s' % scene_id)
        if scene_frame['instance'] is None:
            self.create_scene(scene_id)
            self.setup_scene(scene_id)
        self.active_scene_id = scene_id
        scene_frame['instance'].show()

    def hide_scene(self, scene_id):
        try:
            scene_frame = self.scenes[scene_id]
        except KeyError:
            raise Exception('Unknown scene ID: %s' % scene_id)
        if scene_frame['instance'] is None:
            raise Exception('Error hiding scene. Scene not instanciated: %s' % scene_id)
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

    def _loop_scene(self):
        scenes = self.scenes.values()
        for scene in scenes:
            if scene['instance'] is not None:
                event.emit('scene.ready', scene['instance'])
                scene['instance'].show()

        display_update = self.display.update
        event_get = pygame.event.get
        translate_view_to_screen_coord = self.display.translate_view_to_screen_coord
        old_pos = translate_view_to_screen_coord(*pygame.mouse.get_pos())
        while self.active_scene_id is not None:
            # TODO generate list of instances somewhere for faster looping.
            for scene in scenes:
                scene_instance = scene['instance']
                try:
                    loop_iteration = scene_instance.loop_iteration
                except AttributeError:
                    pass
                else:
                    try:
                        if scene['scene_id'] == self.active_scene_id:
                            for pg_event in event_get():
                                if pg_event.type == pygame.locals.MOUSEMOTION:
                                    pos = translate_view_to_screen_coord(*pg_event.pos)
                                    rel = pos[0] - old_pos[0], pos[1] - old_pos[1]
                                    old_pos = pos
                                    pg_event = pygame.event.Event(pg_event.type, dict(
                                        buttons=pg_event.buttons,
                                        pos=pos,
                                        rel=rel,
                                    ))
                                elif pg_event.type in (pygame.locals.MOUSEBUTTONDOWN, pygame.locals.MOUSEBUTTONUP):
                                    pos = translate_view_to_screen_coord(*pg_event.pos)
                                    old_pos = pos
                                    pg_event = pygame.event.Event(pg_event.type, dict(
                                        button=pg_event.button,
                                        pos=pos,
                                    ))
                                event.emit('scene.event.system', Array(
                                    scene=scene_instance, event=pg_event))
                        loop_iteration()
                    except QuitSceneEvent:
                        scene_id = scene['scene_id']
                        self.teardown_scene(scene_id)
                        if self.active_scene_id == scene_id:
                            self.active_scene_id = None
            display_update()

        for scene in scenes:
            if scene['instance'] is not None:
                self.teardown_scene(scene['scene_id'])

        display_update()

        # print locals().keys()

    def run(self, scene_id=None):
        event.emit('scenemanager.ready', self)

        if scene_id is not None:
            self.active_scene_id = scene_id
        else:
            scene_id = self.active_scene_id

        # Instanciate active scene if not already done.
        if scene_id is None:
            raise Exception('SceneManager has no active scene to work with!')
        self.create_scene(scene_id)
        self.setup_scene(scene_id)

        # We enclose our loop in order to have it easier with our GC.
        self._loop_scene()

        self.display.__del__()  # Tell display to clean it up.

        # Catch statistics and if some found output things.
        log_info('Checking for stuff that should be cleaned up already.')
        from diamond.display import Texture, TextureDl
        listeners = event.get_listeners()
        tickers = event.emit('ticker.dump')
        textures = Texture.get_instance_cache()
        texture_dls = TextureDl.get_instance_cache()
        display_list = self.display.display_list
        drawables = self.display._drawables
        drawables_dl = self.display._drawables_dl
        if listeners or tickers or textures or texture_dls or display_list or drawables:
            log_warning('Found stuff that should be cleaned up earlier!')
            if listeners:
                log_warning('Events:')
                for key, val in listeners.iteritems():
                    log_warning({key: val})
            if tickers:
                log_warning('Tickers:')
                for func, items in tickers:
                    log_warning((func, items))
            if textures:
                log_warning('Textures:')
                for key, val in textures.iteritems():
                    log_warning((key, val))
            if texture_dls:
                log_warning('TexturesDLs:')
                for key, val in texture_dls.iteritems():
                    log_warning((key, val))
            if display_list:
                log_warning('Display list:')
                for val in display_list:
                    log_warning(val)
            if drawables:
                log_warning('Drawable list:')
                for val in drawables:
                    log_warning(val)
            if drawables_dl:
                log_warning('Drawable display list:')
                log_warning(drawables_dl)

        log_info('Done.')
