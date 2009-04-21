"""
Miscellaneous utilities

These are small enough not to require a module of their own.
"""
# Copyright (C) 2008 James Fargher

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms of the Do What The Fuck You Want
# To Public License, Version 2, as published by Sam Hocevar. See
# http://sam.zoy.org/wtfpl/COPYING for more details.

import pyglet

class IdentFetchError(Exception):
    """Error raised when no unique identities are available"""
    pass

class IdentAlloc(object):
    """Manage unique identity numbers in range"""
    def __init__(self, idrange):
        self.__used = []
        self.__free = [x for x in range(idrange)]

    def free(self, oldid):
        """Tell ID allocator an ID is free"""
        try:
            used_index = self.__used.index(oldid)
            self.__free.append(oldid)
            del self.__used[used_index]
        except ValueError:
            # Don't error on free
            pass

    def fetch(self):
        """Get new unique ID from allocator"""
        if len(self.__free) < 1:
            raise IdentFetchError("no more ID's in range")
        newid = self.__free.pop(0)
        self.__used.append(newid)
        return newid

class ColoredSprite(pyglet.sprite.Sprite):
    """Sprite that replaces a color based on a color mask image"""
    def __init__(self, image, mask, color, batch=None, group=None):
        super(ColoredSprite, self).__init__(
                self.__generate_image(image, mask, color),
                batch=batch,
                group=group)

    def __alpha_blend(self, src, dst, alpha):
        """Alpha blend 0-255 integer color channel

        See http://www.codeguru.com/cpp/cpp/algorithms/general/article.php/c15989/
        """
        return ((src * alpha) + (dst * (255 - alpha))) // 255

    def __generate_image(self, image, mask, color):
        mask_data = mask.get_image_data().get_data('A', mask.width)
        image_data = image.get_image_data().get_data('RGBA', image.width * 4)
        new_data = ""
        for index, alpha in enumerate(mask_data):
            alpha_ord = ord(alpha)
            if alpha_ord > 0:
                img_color = (ord(image_data[index*4]),
                             ord(image_data[index*4+1]),
                             ord(image_data[index*4+2]))
                new_data += chr(self.__alpha_blend(color[0], img_color[0],
                                                   alpha_ord)) + \
                            chr(self.__alpha_blend(color[1], img_color[1],
                                                   alpha_ord)) + \
                            chr(self.__alpha_blend(color[2], img_color[2],
                                                   alpha_ord)) + \
                            image_data[index*4+3]
            else:
                new_data += image_data[index*4] + \
                            image_data[index*4+1] + \
                            image_data[index*4+2] + \
                            image_data[index*4+3]
        return pyglet.image.ImageData(image.width, image.height, "RGBA",
                                      new_data, image.width * 4)

