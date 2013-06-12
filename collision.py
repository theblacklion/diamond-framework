# Tickerable class to test for collisions and emit events if any.
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

from diamond import event
# from diamond.decorators import time


class Collision(object):

    def __init__(self, name='collision'):
        super(Collision, self).__init__()
        self.__name = name
        self.__events = set()
        self.__targets = set()
        self.__source = None
        self.__active_collisions = set()

    def add_targets(self, targets):
        self.__targets |= set(targets)

    def remove_targets(self, targets):
        self.__targets -= set(targets)

    def set_source(self, source):
        self.__source = source

    # @time
    def tick(self):
        if self.__source is None:
            return
        source = self.__source
        targets = list(self.__targets)
        target_rects = [target.get_rect() for target in targets]
        collisions = source.get_rect().collidelistall(target_rects)
        if collisions:
            # print
            source_mask = source.frame['masks'][str(source.frame['current_gamma'])]
            results = set()
            for idx in collisions:
                target = targets[idx]
                try:
                    target_mask = target.frame['masks'][str(target.frame['current_gamma'])]
                except TypeError:  # Race condition.
                    print('Got race condition with sprite: %s' % target)
                    target_mask = target.vault.get_action('none').get_frame(0).get_mask()
                # print(target_mask)
                x, y = source.pos_real_in_tree
                x -= target.pos_real_in_tree[0]
                y -= target.pos_real_in_tree[1]
                # print x, y
                if target_mask.overlap(source_mask, (x, y)):
                    results.add(target)
            # print(results)
            last_results = self.__active_collisions
            added = results - last_results
            removed = last_results - results
            self.__active_collisions = results
            if added or removed:
                event.emit('%s.state.changed' % self.__name, dict(
                    source=source, targets=results,
                    targets_added=added, targets_removed=removed,
                ))
        elif self.__active_collisions:
            last_results = self.__active_collisions
            self.__active_collisions = set()
            event.emit('%s.state.changed' % self.__name, dict(
                source=source, targets=set(),
                targets_added=set(), targets_removed=last_results,
            ))
