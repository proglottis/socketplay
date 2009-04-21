"""
Protocol command packing/wrapping
"""
# Copyright (C) 2008 James Fargher

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms of the Do What The Fuck You Want
# To Public License, Version 2, as published by Sam Hocevar. See
# http://sam.zoy.org/wtfpl/COPYING for more details.

import struct

from protocol.local import *

class HeaderPack(object):
    """Top level packet packer"""
    def __init__(self, queue):
        self.queue = queue

    def pack(self, data, sendto):
        data = struct.pack("!6s", "BOXMAN") + data
        self.queue.push(data, sendto)

class CommandPack(object):
    """Command packet packer"""
    def __init__(self, packer):
        self.packer = packer

    def pack(self, cmd, data, sendto):
        data = struct.pack("!B", cmd) + data
        self.packer.pack(data, sendto)

class HelloCommand(object):
    """Client announce command"""
    def __init__(self, packer):
        self.packer = packer

    def send(self, sendto):
        self.packer.pack(CMD_HELLO, "", sendto)

class QuitCommand(object):
    """Client quit command"""
    def __init__(self, packer):
        self.packer = packer

    def send(self, sendto):
        self.packer.pack(CMD_QUIT, "", sendto)

class SpawnCommand(object):
    """Spawn entity command"""
    def __init__(self, packer):
        self.packer = packer

    def send(self, entitytype, entity, sendto):
        self.packer.pack(CMD_SPAWN,
                struct.pack("!BBBBB", entitytype, entity.id, *entity.color),
                sendto)

class DestroyCommand(object):
    """Destroy entity command"""
    def __init__(self, packer):
        self.packer = packer

    def send(self, entityid, sendto):
        self.packer.pack(CMD_DESTROY, struct.pack("!B", entityid), sendto)

class UpdateCommand(object):
    """Update entity command"""
    def __init__(self, packer):
        self.packer = packer

    def send(self, entities, sendto):
        if len(entities) < 1:
            return
        data = struct.pack("!I", len(entities))
        for entity in entities:
            pos = entity.get_position()
            data += struct.pack("!Bfff", entity.id, pos[0], pos[1],
                                entity.get_direction())
        self.packer.pack(CMD_UPDATE, data, sendto)

class ClientCommand(object):
    """Update client state command"""
    def __init__(self, packer):
        self.packer = packer

    def send(self, direction, sendto):
        self.packer.pack(CMD_CLIENT, struct.pack("!????", *direction), sendto)
