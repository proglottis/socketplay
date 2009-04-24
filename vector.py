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

class Vec2(object):
    """2-dimensional vector"""
    VEC_X = 0
    VEC_Y = 1

    def __init__(self, x, y):
        self.__x = x
        self.__y = y

    @classmethod
    def origin(cls):
        return cls(0.0, 0.0)

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
        new_x = self.x + other[self.VEC_X]
        new_y = self.y + other[self.VEC_Y]
        return Vec2(new_x, new_y)

    def __sub__(self, other):
        new_x = self.x - other[self.VEC_X]
        new_y = self.y - other[self.VEC_Y]
        return Vec2(new_x, new_y)

    def __getitem__(self, name):
        if name == self.VEC_X:
            return self.x
        elif name == self.VEC_Y:
            return self.y
        raise IndexError('Vec2 index out of range')

    def __len__(self):
        return 2
