class Rect(object):

    def __init__(self, *args):
        try:
            if len(args) == 4:
                self.x, self.y, self.w, self.h = args
            elif len(args) == 2:
                self.x, self.y = args[0]
                self.w, self.h = args[1]
            else:
                raise Exception()
        except:
            raise Exception('Invalid call args. Rect can either accept: (x, y, w, h) or ((x, y), (w, h))')
