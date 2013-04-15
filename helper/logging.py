import inspect
from os.path import basename


LOG_FILENAME = False  # Whether to show filename in logging output or not.

LOG_LEVEL_DEBUG = 'DEBUG'
LOG_LEVEL_INFO = 'INFO'
LOG_LEVEL_WARNING = 'WARNING'
LOG_LEVEL_ERROR = 'ERROR'
LOG_LEVEL_NONE = 'NONE'
LOG_LEVELS = [
    LOG_LEVEL_DEBUG,
    LOG_LEVEL_INFO,
    LOG_LEVEL_WARNING,
    LOG_LEVEL_ERROR,
    LOG_LEVEL_NONE,
]

LOG_LEVEL_THRESHOLD = LOG_LEVEL_WARNING  # Default log level threshold.


def log(level, msg):
    if level in LOG_LEVELS:
        index = LOG_LEVELS.index(level)
        if index < LOG_LEVELS.index(LOG_LEVEL_THRESHOLD):
            return
    method = inspect.stack()[2][3]
    # print
    # print inspect.stack()[2]
    # print inspect.stack()[2][1]
    # print dir(inspect.stack()[2][0])
    # print inspect.stack()[2][0].f_code
    # print dir(inspect.stack()[2][0].f_code)
    # print inspect.stack()[2][0].f_code.co_name
    # print inspect.stack()[2][0].f_code.co_filename
    # print inspect.stack()[2][0].f_code.co_varnames
    # print inspect.stack()[2][0].f_locals
    # print
    filename = basename(inspect.stack()[2][1]) if LOG_FILENAME else None
    klass = None
    self = inspect.stack()[2][0].f_locals.get('self', None)
    cls = inspect.stack()[2][0].f_locals.get('cls', None)
    if self is not None:
        klass = self.__class__.__name__
    elif cls is not None:
        klass = cls.__name__
    if klass is not None:
        name = '%s.%s()' % (klass, method)
    else:
        name = '%s()' % method
    name = '%s:%s' % (filename, name) if LOG_FILENAME else name
    if type(msg) is tuple:
        msg = ' '.join([str(item) for item in msg])
    msgs = msg.split('\n')
    for msg in msgs:
        print '[%s] [%s] %s' % (level, name, msg)


def log_info(*args):
    log(level='INFO', msg=args)


def log_debug(*args):
    log(level='DEBUG', msg=args)


def log_warning(*args):
    log(level='WARNING', msg=args)


def log_error(*args):
    log(level='ERROR', msg=args)


# Demo code follows.
class Test(object):

    def msg(self):
        log_info('from method')

    @classmethod
    def msg2(cls):
        log_info('from classmethod')


def main():
    Test().msg()
    Test.msg2()
    log_info('from function')


if __name__ == '__main__':
    main()
    log_debug('from main')
    log_info('from main')
    log_error('from main')
