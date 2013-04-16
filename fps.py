# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

from diamond.font import Font


class Fps(Font):

    def __init__(self, ticker, font_vault=None, details=False):
        super(Fps, self).__init__(font_vault)
        self.details = details
        self.ticker = ticker
        self.ticker.add(self.update_fps, 1000)
        self.recent_frame_lenghts = [0, 0, 0, 0, 0]

    def __del__(self):
        # print 'Fps.__del__(%s)' % self
        super(Fps, self).__del__()
        self.ticker.remove(self.update_fps)

    def show_details(self):
        self.details = True

    def hide_details(self):
        self.details = False

    def update_fps(self):
        fps = self.display.clock.get_fps()
        recent_flens = self.recent_frame_lenghts
        recent_flens.pop(0)
        recent_flens.append(fps)
        if self.details:
            avg_flen = sum(recent_flens) / 5
            nodes = len(self.display.get_root_node().get_node_tree_as_list())
            sprites = len(self.display.display_list)
            drawables = len(self.display._drawables)
            text = '%d fps (avg %d), %d objs (%d nds, %d sprts, %d drwbls)' % (
                fps, avg_flen, nodes + sprites, nodes, sprites, drawables)
        else:
            text = '%d fps' % fps
        self.set_text(text)
