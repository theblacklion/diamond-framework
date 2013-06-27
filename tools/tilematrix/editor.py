#!/usr/bin/env python
#
# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

import os
import sys
import textwrap
import argparse
import ConfigParser

# Make sure that our diamond engine can be found.
engine_path = os.path.join(os.path.dirname(__file__), '..', '..', '..')
sys.path.insert(0, os.path.abspath(engine_path))

from diamond.scene import SceneManager

from diamond.tools.tilematrix.tilesheet import TilesheetScene
from diamond.tools.tilematrix.tilemap import TilemapScene


APP_NAME = 'TileMatrix Editor'
APP_VERSION = '0.1'


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
    shared_data = dict()

    parser = argparse.ArgumentParser(
        description=textwrap.dedent('''
        %s (%s)

        Loads a tilematrix map and shows an editor which enables you
        to create, edit and save a map.
        ''') % (APP_NAME, APP_VERSION),
        prog='editor.py',
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('config', action='store',
                        metavar='CONFIG',
                        help='Provide filepath to the matrix spec (ini-file) to work with.',
    )
    parser.add_argument('--screen-size', dest='screen_size', action='store',
                        default='1024x-768', metavar='WIDTHxHEIGHT',
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

    # Display options
    DISPLAY_LAYOUT = {
        'screen_size': map(int, args.screen_size.split('x')),
        'fullscreen': args.fullscreen,
        'show_mouse_in_windowed_mode': True,
        'show_mouse_in_fullscreen_mode': True,
        'auto_center_mouse_on_screen': True,
        # 'expand_in_fullscreen': True,
        # 'maximize_fullscreen': True,
    }

    # Setup data to work with.
    shared_data['config_file'] = args.config
    base_dir = os.path.dirname(os.path.relpath(args.config, os.getcwd()))
    shared_data['base_dir'] = base_dir
    config = ConfigParser.ConfigParser()
    config.read(args.config)
    shared_data['sheet_files'] = [(alias, os.path.join(base_dir, filename)) for alias, filename in config.items('tilesheets')]
    shared_data['matrix_data_path'] = os.path.join(base_dir, config.get('matrix', 'data_path'))
    shared_data['selection'] = None

    # Setup our editor.
    manager = SceneManager()
    display = manager.setup_display(**DISPLAY_LAYOUT)
    display.set_caption('%s (%s)' % (APP_NAME, APP_VERSION))
    manager.add_scene(TilesheetScene, scene_id='tilesheet', shared_data=shared_data)
    manager.add_scene(TilemapScene, scene_id='tilemap', shared_data=shared_data)
    # manager.add_scene(PaletteScene, scene_id='palette', shared_data=shared_data)

    # Run it!
    manager.run('tilemap')


if __name__ == '__main__':
    main()
