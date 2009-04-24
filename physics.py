"""
Physics Engine
"""
# Copyright (C) 2008 James Fargher

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms of the Do What The Fuck You Want
# To Public License, Version 2, as published by Sam Hocevar. See
# http://sam.zoy.org/wtfpl/COPYING for more details.

import vector

class Space(object):
    """Physics simulation space"""
    def __init__(self):
        self.bodies = []

    def add(self, body):
        """Add body to simulation"""
        self.bodies.append(body)

    def remove(self, body):
        """Remove body from simulation"""
        self.bodies.remove(body)

    def update(self, dt):
        """Update all bodies"""
        for body in self.bodies:
            body.update_position(dt)
            body.update_angle(dt)

class Body(object):
    """A physical object"""
    def __init__(self):
        self.position = vector.Vec2.origin()
        self.velocity = vector.Vec2.origin()
        self.angle = 0.0
        self.angular_velocity = 0.0

    def update_position(self, dt):
        self.position = self.position + self.velocity.scale(dt)

    def update_angle(self, dt):
        self.angle += self.angular_velocity * dt
