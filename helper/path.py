from os.path import dirname, join
import inspect


def abspath(filename):
    '''
    Gets a filename, gets the filename of the file who called this method
    and creates and absolute path for the filename.
    '''
    path = inspect.stack()[1][1]
    filename = join(dirname(path), filename)
    return filename