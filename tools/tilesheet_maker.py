#!/usr/bin/env python
#
# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

import os
from collections import OrderedDict
import textwrap
import argparse

import pygame


APP_NAME = 'Tilesheet Maker'
APP_VERSION = '0.1'

PYTHON_TEMPLATE = '''
from json import load
from collections import OrderedDict
from os.path import splitext


locals().update(load(open('%s.json' % splitext(__file__)[0], 'rb'), object_pairs_hook=OrderedDict))
'''.lstrip()

JSON_SPRITE_TEMPLATE = '''
        "%(id)s": {"none": [[[%(x)d, %(y)d, %(w)d, %(h)d], [%(x)d, %(y)d], [0, 0], 60]]},
'''.rstrip()

JSON_TEMPLATE = '''
{
    "filename": "%(filename)s",
    "sprites": {%(sprites)s
    },
    "tile_size": [%(tile_w)d, %(tile_h)d]
}
'''.lstrip()


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


def get_size(filename):
    image = pygame.image.load(filename)
    # print image
    image_width, image_height = image.get_size()
    # print image_width, image_height
    return image_width, image_height


def get_spritesheet(img_w, img_h, tile_w, tile_h, use_ids=False):
    sheet = OrderedDict()
    cur_id = 0
    y = 0
    while y < img_h:
        x = 0
        while x < img_w:
            key = str(cur_id) if use_ids else '%d,%d' % (x // tile_w, y // tile_h)
            sheet[key] = {'none': [[(x, y, tile_w, tile_h), (x, y), (0, 0), 60]]}
            cur_id += 1
            x += tile_w
        y += tile_h
    return sheet


def main():
    parser = argparse.ArgumentParser(
        description=textwrap.dedent('''
        %s (%s)

        Creates a vault and a JSON file for use as a tilemap resource for the diamond engine.

        The following example would load mysheet.png with a tile size of 32x32 and produce tilesheet.py and tilesheet.json:
        > tilesheet_maker.py mysheet.png tilesheet 32x32
        ''') % (APP_NAME, APP_VERSION),
        prog='tilesheet_maker.py',
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('image', action='store',
                        metavar='IMAGE',
                        help='Provide filepath to the image to be used for the sheet.',
    )
    parser.add_argument('sheet', action='store',
                        metavar='SHEET',
                        help='Provide filepath *without extension* for the files to be generated.',
    )
    parser.add_argument('dimensions', action='store',
                        metavar='WIDTHxHEIGHT',
                        help='Provide size (width and height) of each tile.',
    )
    parser.add_argument('--use-ids', dest='use_ids', action='store_true',
                        default=False,
                        help='Use IDs as generated keys instead of matrix coordinates.',
    )
    parser.add_argument('--version', action='version',
                        version='%(prog)s ' + APP_VERSION,
                        help='Show program\'s version number and exit.')
    args = parser.parse_args()

    pygame.init()

    image_width, image_height = get_size(args.image)
    tile_width, tile_height = map(int, args.dimensions.split('x'))

    data = OrderedDict(
        filename=args.image,
        sprites=get_spritesheet(image_width, image_height, tile_width, tile_height, use_ids=args.use_ids),
        tile_size=(tile_width, tile_height),
    )
    # print data
    # from pprint import pprint
    # pprint(data)

    python_file = '%s.py' % args.sheet
    json_file = '%s.json' % args.sheet
    # print python_file
    # print json_file

    if not os.path.exists(python_file):
        open(python_file, 'wb').write(PYTHON_TEMPLATE)
    else:
        print('INFO: Not created python file. Seems to already exist: %s' % python_file)

    sprites = []
    for key, actions in data['sprites'].iteritems():
        frame = actions['none'][0]
        sprites.append(JSON_SPRITE_TEMPLATE % dict(
            id=key,
            x=frame[0][0],
            y=frame[0][1],
            w=frame[0][2],
            h=frame[0][3],
        ))
    json = JSON_TEMPLATE % dict(
        filename=os.path.relpath(data['filename'], os.path.dirname(json_file)),  # data['filename'],
        sprites=''.join(sprites).rstrip(','),
        tile_w=tile_width,
        tile_h=tile_height,
    )
    open(json_file, 'wb').write(json)
    print('Written JSON data to file: %s' % json_file)


if __name__ == '__main__':
    main()
