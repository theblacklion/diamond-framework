#!/usr/bin/env python
import sys
import os
import hotshot


module_path = os.path.dirname(sys.argv[1])
module_name = os.path.splitext(os.path.basename(sys.argv[1]))[0]
sys.path.insert(0, os.path.abspath(module_path))
sys.argv.pop(0)


def run():
    module = __import__(module_name, globals(), locals(), [], -1)
    module.main()


if not os.path.exists('results'):
    os.makedirs('results')
filename = 'results/pythongrind.prof'
prof = hotshot.Profile(filename, lineevents=1)
prof.runcall(run)
prof.close()
path = os.path.dirname(__file__)
os.system('%s/hotshot2calltree.py -o results/callgrind.out results/pythongrind.prof' % path)
