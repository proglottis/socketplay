"""
Protocol command interpret/dispatch
"""
# Copyright (C) 2008 James Fargher

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms of the Do What The Fuck You Want
# To Public License, Version 2, as published by Sam Hocevar. See
# http://sam.zoy.org/wtfpl/COPYING for more details.

import logging
import struct

from protocol.local import *

logger = logging.getLogger(__name__)

class HeaderDispatch(object):
    """Dispatch packet unwrapping header"""
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher

    def dispatch(self, data, address):
        ident, = struct.unpack("!6s", data[:6])
        if ident != "BOXMAN":
            return
        self.dispatcher.dispatch(data[6:], address)

class ServerHelloDispatch(object):
    """Dispatch packet unwrapping server hello command"""
    def __init__(self, spawncmd, players, idalloc, entityfactory):
        self.spawncmd = spawncmd
        self.players = players
        self.idalloc = idalloc
        self.entityfactory = entityfactory

    def dispatch(self, data, address):
        if address not in self.players:
            newid = self.idalloc.fetch()
            boxman = self.entityfactory.create(newid)
            for sendto, player in self.players.iteritems():
                # Notify new player of existing players
                self.spawncmd.send(ENT_BOXMAN, player, address)
                # Notify existing players of new player
                self.spawncmd.send(ENT_BOXMAN, boxman, sendto)
            self.players[address] = boxman
            # Notify new player of its entity
            self.spawncmd.send(ENT_PLAYER, boxman, address)
            logger.debug("Server:Hello:New client:%s", repr(address))
        else:
            logger.debug("Server:Hello:Client already known")

class ServerQuitDispatch(object):
    """Dispatch packet unwrapping server quit command"""
    def __init__(self, quitcmd, destroycmd, players, idalloc):
        self.quitcmd = quitcmd
        self.destroycmd = destroycmd
        self.players = players
        self.idalloc = idalloc

    def dispatch(self, data, address):
        if address in self.players:
            oldid = self.players[address].id
            self.idalloc.free(oldid)
            del self.players[address]
            self.quitcmd.send(address)
            logger.debug("Server:Quit:Client quit:%s", repr(address))
            for address in self.players.iterkeys():
                self.destroycmd.send(oldid, address)
        else:
            logger.debug("Server:Quit:Client not known")

class ServerClientDispatch(object):
    """Dispatch packet unwrapping server client state command"""
    def __init__(self, players):
        self.players = players

    def dispatch(self, data, address):
        if address not in self.players:
            logger.debug("Server:Client:Client not known")
            return
        north, east, south, west = struct.unpack("!????", data[:4])
        self.players[address].set_direction((north, east, south, west))

class ServerCommandDispatch(object):
    """Dispatch packet unwrapping server command type"""
    def __init__(self, hello_dispatcher, quit_dispatcher, client_dispatcher):
        self.hello_dispatcher = hello_dispatcher
        self.quit_dispatcher = quit_dispatcher
        self.client_dispatcher = client_dispatcher

    def dispatch(self, data, address):
        cmd, = struct.unpack("!B", data[:1])
        if cmd == CMD_HELLO:
            logger.debug("Server:Command:CMD_HELLO")
            self.hello_dispatcher.dispatch(data[1:], address)
        elif cmd == CMD_QUIT:
            logger.debug("Server:Command:CMD_QUIT")
            self.quit_dispatcher.dispatch(data[1:], address)
        elif cmd == CMD_CLIENT:
            self.client_dispatcher.dispatch(data[1:], address)
        else:
            logger.warning("Server:Command:Bad command")

class ClientQuitDispatch(object):
    """Dispatch packet unwrapping client quit command"""
    def __init__(self, quit_flag):
        self.quit_flag = quit_flag

    def dispatch(self, data, address):
        self.quit_flag.set_quit()

class ClientSpawnDispatch(object):
    """Dispatch packet unwrapping client spawn entity command"""
    def __init__(self, players, entfactory):
        self.players = players
        self.entfactory = entfactory

    def dispatch(self, data, address):
        type, id, color_r, color_g, color_b = struct.unpack("!BBBBB", data[:5])
        color = (color_r, color_g, color_b)
        logger.debug("Client:Spawn:Spawn entity %d" % id)
        if type == ENT_PLAYER:
            logger.debug("Client:Spawn:ENT_PLAYER")
            self.players[id] = self.entfactory.create(color)
        elif type == ENT_BOXMAN:
            logger.debug("Client:Spawn:ENT_BOXMAN")
            self.players[id] = self.entfactory.create(color)
        else:
            logger.warning("Client:Spawn:Unknown type")

class ClientDestroyDispatch(object):
    """Dispatch packet unwrapping client destroy entity command"""
    def __init__(self, players):
        self.players = players

    def dispatch(self, data, address):
        id, = struct.unpack("!B", data[:1])
        if id in self.players:
            logger.debug("Client:Destroy:Destroy entity %d" % id)
            del self.players[id]
        else:
            logger.warning("Client:Destroy:Unknown entity")

class ClientUpdateDispatch(object):
    """Dispatch packet unwrapping client update entity command"""
    def __init__(self, players):
        self.players = players

    def single(self, data, address):
        id, posx, posy = struct.unpack("!Bll", data[:9])
        pos = (posx, posy)
        if id in self.players:
            self.players[id].set_position(*pos)
        else:
            logger.warning("Client:Update:Unknown entity")

    def dispatch(self, data, address):
        count, = struct.unpack("!I", data[:4])
        for n in range(count):
            self.single(data[4+9*n:], address)

class ClientCommandDispatch(object):
    """Dispatch packet unwrapping client command type"""
    def __init__(self,
                 quit_dispatcher,
                 spawn_dispatcher,
                 destroy_dispatcher,
                 update_dispatcher):
        self.quit_dispatcher = quit_dispatcher
        self.spawn_dispatcher = spawn_dispatcher
        self.destroy_dispatcher = destroy_dispatcher
        self.update_dispatcher = update_dispatcher

    def dispatch(self, data, address):
        cmd, = struct.unpack("!B", data[:1])
        if cmd == CMD_QUIT:
            logger.debug("Client:Command:CMD_QUIT")
            self.quit_dispatcher.dispatch(data[1:], address)
        elif cmd == CMD_SPAWN:
            logger.debug("Client:Command:CMD_SPAWN")
            self.spawn_dispatcher.dispatch(data[1:], address)
        elif cmd == CMD_DESTROY:
            logger.debug("Client:Command:CMD_DESTROY")
            self.destroy_dispatcher.dispatch(data[1:], address)
        elif cmd == CMD_UPDATE:
            self.update_dispatcher.dispatch(data[1:], address)
        else:
            logger.warning("Client:Command:Bad command")
