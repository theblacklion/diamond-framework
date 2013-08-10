#!/usr/bin/env python
#
# Command line interface helper.
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

import textwrap
import argparse


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


class Cli(object):

    def __init__(self,
            app_name='Example application',
            app_version=0.1,
            app_description='Runs some example application.',
            prog_name='example.py'):
        super(Cli, self).__init__()
        app_version = str(app_version)
        self.parser = argparse.ArgumentParser(
            description=textwrap.dedent('''
            %s (%s)

            %s
            ''') % (app_name, app_version, app_description),
            prog=prog_name,
            formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
        )
        self.parser.add_argument(
            '-v', '--version', action='version',
            version='%(prog)s ' + app_version,
            help='Show applications\'s version number and exit.')
        self.args = dict()

    def add_screen_size(self, default='640x480'):
        self.parser.add_argument(
            '-s', '--screen-size', dest='screen_size', action='store',
            default=default, metavar='WIDTHxHEIGHT',
            help='Provide screen size (width and height) for the display.',
        )

    def add_fullscreen(self):
        self.parser.add_argument(
            '-f', '--fullscreen', dest='fullscreen', action='store_true',
            help='Enable fullscreen mode.',
        )

    def add_debug_logging(self):
        self.parser.add_argument(
            '-d', '--debug', dest='debug', action='store_true',
            help='Enable debugging output.',
        )

    def add_profiler(self):
        self.parser.add_argument(
            '-p', '--profiler', dest='profiler', action='store_true',
            help='Run with profiler. Print stats on exit.',
        )

    def parse_args(self):
        args = self.parser.parse_args()
        if args.debug:
            from diamond.helper import logging
            logging.LOG_LEVEL_THRESHOLD = logging.LOG_LEVEL_DEBUG
        self.args = args
        return args

    def run(self, command, *args, **kwargs):
        if self.args.profiler:
            import cProfile
            func = lambda: command(*args, **kwargs)
            cProfile.runctx('func()', globals(), locals(), 'profiler-stats.dat')
            import pstats
            print
            print 'Top 10 algorithms which take time:'
            p = pstats.Stats('profiler-stats.dat')
            p.sort_stats('cumulative').print_stats(10)
            print 'Top 10 functions which take time:'
            p = pstats.Stats('profiler-stats.dat')
            p.sort_stats('time').print_stats(10)
            # print 'Init routines:'
            # p = pstats.Stats('profiler-stats.dat')
            # p.sort_stats('time', 'cumulative').print_stats(.5, 'init')
            # print 'Callees:'
            # p.print_callers(.5, 'init')
        else:
            command()
        from diamond.decorators import print_time_stats
        print_time_stats()
