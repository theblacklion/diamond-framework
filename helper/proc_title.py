try:
    import setproctitle
except ImportError:
    print('Please install the setproctitle module.')
    import sys
    sys.exit()


def set_title(text):
    setproctitle.setproctitle(text)


def get_title():
    return setproctitle.getproctitle()
