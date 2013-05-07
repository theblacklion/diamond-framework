# TODO
#
# @author    Oktay Acikalin <oktay.acikalin@gmail.com>
# @copyright Oktay Acikalin
# @license   MIT (LICENSE.txt)

from random import random

from diamond.node import Node
from diamond.sprite import Sprite
from diamond.effects import TransitionEffects


class Particles(Node):

    def __init__(self, num_particles, vault, Sprite):
        super(Particles, self).__init__('%d Particles of "%s"' % (num_particles, Sprite))
        self.num_particles = 0
        self.vault = vault
        self.Sprite = Sprite
        self.order_matters = False
        self.set_num_particles(num_particles)

    def set_num_particles(self, amount):
        # print 'set_num_particles(%s, %s)' % (self, amount)
        particles = self.child_sprites
        for particle in particles:
            particle.last_round = False
        variance = amount - len(particles)
        if variance > 0:
            new_particles = self.Sprite.make_many(self.vault, amount=variance)
            self.add_children(new_particles)
        elif variance < 0:
            for item in particles[amount:]:
                # print 'mark %s for last round' % item
                item.last_round = True
        self.num_particles = amount


class Particle(Sprite):
    # TODO Try to use tickers and transitions instead of rounds.

    def __init__(self, *args, **kwargs):
        super(Particle, self).__init__(*args, **kwargs)
        self.round = 0
        self.speed = None
        self.last_round = False
        self.reset()
        self.start_rect = (0, 0, 640, 0)  # Top line of screen
        self.stop_rect = (0, 480, 640, 0)  # Bottom line of screen
        self.transition = TransitionEffects()

    def reset(self):
        if self.last_round:
            # print 'gone', self
            self.remove_from_parent()
            self.detach_from_display()
            return
        x = int(640 * random())
        y = int(480 * random()) - 480
        s = max(30, int(80 * random()))
        alpha = (64 + int(75 * random())) / 255.0 * 100
        # print x, y, s, alpha
        self.set_pos(x, y)
        self.set_alpha(alpha)
        self.speed = s
        # print 'reset(%s)' % self

    def update(self):
        if self.round == 1:
            self.round = 0
            x, y = self.pos
            if y > 480:
                self.reset()
            else:
                y += self.speed
                self.set_pos(x, y)
            super(Particle, self).update()
        else:
            self.round += 1
