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
            body.update(dt)

class Body(object):
    """A physical object"""
    def __init__(self, mass, moment):
        # Positional
        self.mass = mass
        self.position = vector.Vec2()
        self.velocity = vector.Vec2()
        self.force = vector.Vec2()
        # Angular
        self.moment = moment
        self.angle = 0.0
        self.angular_velocity = 0.0
        self.torque = 0.0

    def reset_force(self):
        self.force = vector.Vec2()

    def add_force(self, force):
        self.force = self.force + force

    def reset_torque(self):
        self.torque = 0.0

    def add_torque(self, torque):
        self.torque = self.torque + torque

    def update_positional(self, dt):
        acceleration = vector.Vec2(self.force.x / self.mass,
                                   self.force.y / self.mass)
        self.velocity += acceleration.scale(dt)
        self.position += self.velocity.scale(dt)

    def update_angular(self, dt):
        acceleration = self.torque / self.moment
        self.angular_velocity += acceleration * dt
        self.angle += self.angular_velocity * dt

    def update(self, dt):
        self.update_positional(dt)
        self.update_angular(dt)
