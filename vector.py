"""
Vector maths
"""
# Copyright (C) 2008 James Fargher

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms of the Do What The Fuck You Want
# To Public License, Version 2, as published by Sam Hocevar. See
# http://sam.zoy.org/wtfpl/COPYING for more details.

import math

(VEC_X, VEC_Y, VEC_Z) = range(3)

class Vec2(object):
    """2-dimensional vector"""
    def __init__(self, x=0.0, y=0.0):
        self.__x = x
        self.__y = y

    @classmethod
    def from_angle(cls, angle, magnitude=1.0):
        x = math.cos(angle) * magnitude
        y = math.sin(angle) * magnitude
        return cls(x, y)

    @property
    def x(self):
        return self.__x

    @property
    def y(self):
        return self.__y

    def magnitude(self):
        """Return the length or magnitude"""
        return math.sqrt(self.x ** 2 + self.y ** 2)

    def normalised(self):
        """Return a normalised copy"""
        mag = self.magnitude()
        if mag == 0.0:
            return Vec2(self.x, self.y)
        return Vec2(self.x / mag, self.y / mag)

    def scale(self, scalar):
        """Return a scaled copy"""
        new_x = self.x * scalar
        new_y = self.y * scalar
        return Vec2(new_x, new_y)

    def __add__(self, other):
        new_x = self.x + other[VEC_X]
        new_y = self.y + other[VEC_Y]
        return Vec2(new_x, new_y)

    def __sub__(self, other):
        new_x = self.x - other[VEC_X]
        new_y = self.y - other[VEC_Y]
        return Vec2(new_x, new_y)

    def __getitem__(self, name):
        if name == VEC_X:
            return self.x
        elif name == VEC_Y:
            return self.y
        raise IndexError('Vec2 index out of range')

    def __len__(self):
        return 2
