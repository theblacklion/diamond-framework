# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

from diamond.transition import TransitionManager, Transition
from diamond.decorators import dump_args


class TransitionEffects(TransitionManager):

    def wait(self, *args, **kwargs):
        return super(TransitionEffects, self).add_wait(*args, **kwargs)

    def fade_in(self, sprite, stack='global', msecs=1000, delay=0, append=True, min_step_msecs=50):
        transition = (
            Transition.change(callback=(sprite, 'set_alpha'), args=0) +
            Transition.change(callback=(sprite, 'show')) +
            Transition.range(
                callback=(sprite, 'set_alpha'),
                args=lambda value: value,
                range=(0, 100),
                msecs=msecs,
                delay=delay,
                min_step_msecs=min_step_msecs,
            )
        )
        self.add(transition, stack=stack, append=append)

    def fade_out(self, sprite, stack='global', msecs=1000, delay=0, append=True, min_step_msecs=50):
        transition = (
            Transition.range(
                callback=(sprite, 'set_alpha'),
                args=lambda value: value,
                range=(100, 0),
                msecs=msecs,
                delay=delay,
                min_step_msecs=min_step_msecs,
            ) +
            Transition.change(callback=(sprite, 'hide'))
        )
        self.add(transition, stack=stack, append=append)

    # @dump_args
    def _fade_to(self, sprite, value, msecs, delay, stack, type_, min_step_msecs):
        if type_ == 'alpha':
            get_func = sprite.get_alpha
            set_func = sprite.set_alpha
        elif type_ == 'gamma':
            get_func = sprite.get_gamma
            set_func = sprite.set_gamma
        else:
            raise Exception('Unknown type for fading: %s' % type_)
        start = int(get_func())
        stop = int(value)
        # print start, stop
        transition = (
            Transition.range(
                callback=set_func,
                args=lambda value: value,
                range=(start, stop),
                msecs=msecs,
                min_step_msecs=min_step_msecs,
            )
        )
        if type_ == 'alpha':
            if start == 0 and stop > 0:
                transition = Transition.change(callback=(sprite, 'show')) + transition
            if start > 0 and stop == 0:
                transition += Transition.change(callback=(sprite, 'hide'))
        if delay:
            transition = Transition.wait(delay) + transition
        return transition

    # @dump_args
    def fade_to(self, sprite, stack='global', value=50, msecs=1000, delay=0, append=True, type_='alpha', min_step_msecs=50):
        if append:
            self.add_injection(callback=self._fade_to, args=(sprite, value, msecs, 0, stack, type_, min_step_msecs), delay=delay, stack=stack, append=append)
        else:
            transition = self._fade_to(sprite, value, msecs, delay, stack, type_, min_step_msecs)
            self.add(transition, stack=stack, append=append)

    def brighten_to(self, sprite, stack='global', brightness=100, msecs=1000, delay=0, append=True, min_step_msecs=50):
        value = 100 + max(0, min(100, brightness))
        self.fade_to(sprite, stack, value, msecs, delay, append, 'gamma', min_step_msecs)

    def darken_to(self, sprite, stack='global', darkness=100, msecs=1000, delay=0, append=True, min_step_msecs=50):
        value = 100 - max(0, min(100, darkness))
        self.fade_to(sprite, stack, value, msecs, delay, append, 'gamma', min_step_msecs)

    def _calc_movement(self, sprite, msecs, x1, y1, x2, y2):
        transition = []
        append = lambda *args, **kwargs: transition.extend(Transition.change(*args, **kwargs))

        dx = x2 - x1
        dy = y2 - y1
        # print dx, dy

        longest = max(abs(dx), abs(dy))
        # print longest

        if longest == 0:
            return transition

        tstep = msecs / float(longest)

        if abs(dx) > abs(dy):
            step = (dx / float(abs(dx)), dy / float(abs(dx)))
        else:
            step = (dx / float(abs(dy)), dy / float(abs(dy)))

        delay = 0
        delay_flush_limit = min(10, msecs)
        for i in range(1, longest):
            delay += tstep
            if delay < delay_flush_limit:
                continue
            x = x1 + int(step[0] * i)
            y = y1 + int(step[1] * i)
            append(callback=(sprite, 'set_pos'), args=(x, y), delay=delay, dropable=True)
            delay = 0

        append(callback=(sprite, 'set_pos'), args=(x2, y2), delay=tstep, dropable=False)

        # print 'TRANSITION =', len(transition), longest

        return transition

    def _move_by(self, sprite, pos, msecs, delay):
        # Calc distance from src to dst.
        x1, y1 = sprite.pos
        x2, y2 = x1 + pos[0], y1 + pos[1]
        transition = (
            self._calc_movement(sprite, msecs, x1, y1, x2, y2)
        )
        return transition

    def move_by(self, sprite, stack='global', pos=(0, 0), msecs=1000, delay=0, append=True):
        sprite.recalc_real_pos()
        if append:
            self.add_injection(callback=self._move_by, args=(sprite, pos, msecs, 0), delay=delay, stack=stack, append=append)
        else:
            transition = self._move_by(sprite, pos, msecs, delay)
            self.add(transition, stack=stack, append=append)

    # @dump_args
    def _move_to(self, sprite, pos, msecs, delay):
        # Calc distance from src to dst.
        x1, y1 = sprite.pos
        x2, y2 = pos
        transition = (
            self._calc_movement(sprite, msecs, x1, y1, x2, y2)
        )
        return transition

    # @dump_args
    def move_to(self, sprite, stack='global', pos=(0, 0), msecs=1000, delay=0, append=True):
        sprite.recalc_real_pos()
        if append:
            self.add_injection(callback=self._move_to, args=(sprite, pos, msecs, 0), delay=delay, stack=stack, append=append)
        else:
            transition = self._move_to(sprite, pos, msecs, delay)
            self.add(transition, stack=stack, append=append)

    def hide(self, sprite, stack='global', delay=0, append=True):
        self.add_change(callback=(sprite, 'hide'), delay=delay, stack=stack, append=append)

    def show(self, sprite, stack='global', delay=0, append=True):
        self.add_change(callback=(sprite, 'show'), delay=delay, stack=stack, append=append)

    @dump_args
    def _rotate_to(self, sprite, angle, msecs):
        start = int(sprite.rotation)  # TODO should get rotation_inherited
        stop = int(angle)
        # print start, stop
        transition = (
            Transition.range(
                callback=(sprite, 'set_rotation'),
                args=lambda value: value,
                range=(start, stop),
                msecs=msecs,
                # min_step_msecs=1,
            )
        )
        return transition

    @dump_args
    def rotate_to(self, sprite, stack='global', angle=0.0, msecs=1000, delay=0, append=True):
        sprite.recalc_real_pos()
        if append:
            self.add_injection(callback=self._rotate_to, args=(sprite, angle, msecs), delay=delay, stack=stack, append=append)
        else:
            transition = self._rotate_to(sprite, angle, msecs)
            self.add(transition, stack=stack, append=append)
