# SocketPlay - Simple client/server python game.
# Copyright (C) 2008 James Fargher

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms of the Do What The Fuck You Want
# To Public License, Version 2, as published by Sam Hocevar. See
# http://sam.zoy.org/wtfpl/COPYING for more details.

import logging
import optparse
import select
import socket
import struct

import pygame
from pygame.locals import *

logging.basicConfig(level=logging.DEBUG)

(
    CMD_HELLO,
    CMD_QUIT,
    CMD_SPAWN,
    CMD_DESTROY,
    CMD_UPDATE,
) = range(5)

(
    ENT_PLAYER,
    ENT_BOXMAN,
) = range(2)

def cmd_unpack_command(data, offset=0):
    return struct.unpack("!B", data[offset:offset+1])

def cmd_header(data):
    return struct.pack("!6s", "BOXMAN") + data

def cmd_command(cmd, data):
    return struct.pack("!B", cmd) + data

def cmd_hello():
    return cmd_header(cmd_command(CMD_HELLO, ""))

def cmd_quit():
    return cmd_header(cmd_command(CMD_QUIT, ""))

def cmd_spawn(type, id, color):
    return cmd_header(
            cmd_command(CMD_SPAWN, struct.pack("!BBBBB", type, id, *color)))

def cmd_destroy(id):
    return cmd_header(cmd_command(CMD_DESTROY, struct.pack("!B", id)))

def cmd_update(id, position):
    return cmd_header(
            cmd_command(CMD_UPDATE, struct.pack("!Bll", id, *position)))

class HeaderDispatch(object):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher

    def dispatch(self, data, address):
        ident, = struct.unpack("!6s", data[:6])
        if ident != "BOXMAN":
            logging.warning("HeaderDispatch:Bad header")
            return
        self.dispatcher.dispatch(data[6:], address)

class SocketReadDispatch(object):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher

    def dispatch(self, sock):
        data, address = sock.recvfrom(4096)
        self.dispatcher.dispatch(data, address)

class SocketWriteQueue(object):
    def __init__(self):
        self.writequeue = []

    def push(self, data, address):
        self.writequeue.append((data, address))

    def write(self, sock):
        for cmd in self.writequeue:
            sock.sendto(cmd[0], cmd[1])
        self.writequeue = []

class SocketServer(object):
    def __init__(self, dispatcher, queue, sock):
        self.dispatcher = dispatcher
        self.queue = queue
        self.socks = (sock,)

    def update(self):
        result = select.select(self.socks, self.socks, (), 0)
        sock_read, sock_write, sock_error = result
        for sock in sock_read:
            self.dispatcher.dispatch(sock)
        for sock in sock_write:
            self.queue.write(sock)

class IdentFetchError(Exception):
    pass

class IdentAlloc(object):
    def __init__(self, idrange):
        self.__used = []
        self.__free = [x for x in range(idrange)]

    def free(self, oldid):
        try:
            used_index = self.__used.index(oldid)
            self.__free.append(oldid)
            del self.__used[used_index]
        except ValueError:
            pass

    def fetch(self):
        if len(self.__free) < 1:
            raise IdentFetchError("no more ID's in range")
        newid = self.__free.pop(0)
        self.__used.append(newid)
        return newid

class ServerBoxman(object):
    def __init__(self, id, color=(255,255,255)):
        self.id = id
        self.color = color
        self.rect = pygame.Rect(0,0,20,20)

    def update(self, **dict):
        self.rect.x += 1
        self.rect.y += 1

class ServerHelloDispatch(object):
    def __init__(self, cmdqueue, players, idalloc):
        self.cmdqueue = cmdqueue
        self.players = players
        self.idalloc = idalloc

    def dispatch(self, data, address):
        if address not in self.players:
            newid = self.idalloc.fetch()
            boxman = ServerBoxman(newid)
            for sendto, player in self.players.iteritems():
                # Notify new player of existing players
                self.cmdqueue.push(
                        cmd_spawn(ENT_BOXMAN, player.id, player.color),
                        address)
                # Notify existing players of new player
                self.cmdqueue.push(
                        cmd_spawn(ENT_BOXMAN, boxman.id, boxman.color),
                        sendto)
            self.players[address] = boxman
            # Notify new player of its entity
            self.cmdqueue.push(
                    cmd_spawn(ENT_PLAYER, newid, boxman.color),
                    address)
            logging.debug("Server:Hello:New client:%s", repr(address))
        else:
            logging.debug("Server:Hello:Client already known")

class ServerQuitDispatch(object):
    def __init__(self, cmdqueue, players, idalloc):
        self.cmdqueue = cmdqueue
        self.players = players
        self.idalloc = idalloc

    def dispatch(self, data, address):
        if address in self.players:
            oldid = self.players[address].id
            self.idalloc.free(oldid)
            del self.players[address]
            self.cmdqueue.push(cmd_quit(), address)
            logging.debug("Server:Quit:Client quit:%s", repr(address))
            for address in self.players.iterkeys():
                self.cmdqueue.push(cmd_destroy(oldid), address)
        else:
            logging.debug("Server:Quit:Client not known")

class ServerCommandDispatch(object):
    def __init__(self, hello_dispatcher, quit_dispatcher):
        self.hello_dispatcher = hello_dispatcher
        self.quit_dispatcher = quit_dispatcher

    def dispatch(self, data, address):
        cmd, = struct.unpack("!B", data[:1])
        if cmd == CMD_HELLO:
            logging.debug("Server:Command:CMD_HELLO")
            self.hello_dispatcher.dispatch(data[1:], address)
        elif cmd == CMD_QUIT:
            logging.debug("Server:Command:CMD_QUIT")
            self.quit_dispatcher.dispatch(data[1:], address)
        else:
            logging.warning("Server:Command:Bad command")

class Server(object):
    def __init__(self, sock_server, players):
        self.sock_server = sock_server
        self.players = players

    def update(self):
        for player in self.players.itervalues():
            player.update()
        for address in self.players.iterkeys():
            for player in self.players.itervalues():
                self.sock_server.queue.push(
                    cmd_update(player.id, player.rect.topleft),
                    address)
        self.sock_server.update()

def create_server(address, port=11235):
    players = {}
    idalloc = IdentAlloc(256)
    sock_writequeue = SocketWriteQueue()
    hello = ServerHelloDispatch(sock_writequeue, players, idalloc)
    quit = ServerQuitDispatch(sock_writequeue, players, idalloc)
    cmd = ServerCommandDispatch(hello, quit)
    header = HeaderDispatch(cmd)
    sock_dispatcher = SocketReadDispatch(header)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(0)
    sock.bind((address, port))
    sock_server = SocketServer(sock_dispatcher, sock_writequeue, sock)
    server = Server(sock_server, players)
    return server

class ClientBoxman(pygame.sprite.Sprite):
    def __init__(self, color=(255,255,255)):
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.Surface((20,20))
        self.image.fill(color)
        self.rect = self.image.get_rect()

    def update(self, **dict):
        pass

class ClientQuitDispatch(object):
    def __init__(self, quit_flag):
        self.quit_flag = quit_flag

    def dispatch(self, data, address):
        self.quit_flag.set_quit()

class ClientSpawnDispatch(object):
    def __init__(self, players):
        self.players = players

    def dispatch(self, data, address):
        type, id, color_r, color_g, color_b = struct.unpack("!BBBBB", data[:5])
        color = (color_r, color_g, color_b)
        logging.debug("Client:Spawn:Spawn entity %d" % id)
        if type == ENT_PLAYER:
            logging.debug("Client:Spawn:ENT_PLAYER")
            self.players[id] = ClientBoxman(color)
        elif type == ENT_BOXMAN:
            logging.debug("Client:Spawn:ENT_BOXMAN")
            self.players[id] = ClientBoxman(color)
        else:
            logging.warning("Client:Spawn:Unknown type")

class ClientDestroyDispatch(object):
    def __init__(self, players):
        self.players = players

    def dispatch(self, data, address):
        id, = struct.unpack("!B", data[:1])
        if id in self.players:
            logging.debug("Client:Destroy:Destroy entity %d" % id)
            del self.players[id]
        else:
            logging.warning("Client:Destroy:Unknown entity")

class ClientUpdateDispatch(object):
    def __init__(self, players):
        self.players = players

    def dispatch(self, data, address):
        id, posx, posy = struct.unpack("!Bll", data[:9])
        pos = (posx, posy)
        if id in self.players:
            self.players[id].rect.topleft = pos
        else:
            logging.warning("Client:Update:Unknown entity")

class ClientCommandDispatch(object):
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
            logging.debug("Client:Command:CMD_QUIT")
            self.quit_dispatcher.dispatch(data[1:], address)
        elif cmd == CMD_SPAWN:
            logging.debug("Client:Command:CMD_SPAWN")
            self.spawn_dispatcher.dispatch(data[1:], address)
        elif cmd == CMD_DESTROY:
            logging.debug("Client:Command:CMD_DESTROY")
            self.destroy_dispatcher.dispatch(data[1:], address)
        elif cmd == CMD_UPDATE:
            self.update_dispatcher.dispatch(data[1:], address)
        else:
            logging.warning("Client:Command:Bad command")

class ClientQuit(object):
    def __init__(self):
        self.quit = False

    def set_quit(self):
        self.quit = True

    def is_quit(self):
        return self.quit

class Client(object):
    def __init__(self, sock_server, sendto, players):
        self.sock_server = sock_server
        self.sendto = sendto
        self.players = players

    def send_hello(self):
        self.sock_server.queue.push(cmd_hello(), self.sendto)

    def send_quit(self):
        self.sock_server.queue.push(cmd_quit(), self.sendto)

    def update(self):
        self.sock_server.update()
        for player in self.players.itervalues():
            player.update()

    def render(self, surface):
        for player in self.players.itervalues():
            surface.blit(player.image, player.rect)

def create_client(quit_flag, address, port=11235):
    players = {}
    quit_dispatcher = ClientQuitDispatch(quit_flag)
    spawn_dispatcher = ClientSpawnDispatch(players)
    destroy_dispatcher = ClientDestroyDispatch(players)
    update_dispatcher = ClientUpdateDispatch(players)
    cmd_dispatcher = ClientCommandDispatch(quit_dispatcher,
                                           spawn_dispatcher,
                                           destroy_dispatcher,
                                           update_dispatcher)
    header_dispatcher = HeaderDispatch(cmd_dispatcher)
    sock_dispatcher = SocketReadDispatch(header_dispatcher)
    sock_writequeue = SocketWriteQueue()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(0)
    sendto = (address, port)
    sock_server = SocketServer(sock_dispatcher, sock_writequeue, sock)
    client = Client(sock_server, sendto, players)
    return client

def main(server=True, address="localhost", port=11235):
    quit_flag = ClientQuit()
    logging.info("Socket Play")
    logging.debug("Start pygame")
    pygame.init()
    logging.debug("Create screen")
    screen = pygame.display.set_mode((800, 600))
    logging.debug("Create timer")
    clock = pygame.time.Clock()
    if server:
        logging.debug("Start server")
        server = create_server("0.0.0.0", port)
    logging.debug("Start client")
    client = create_client(quit_flag, address, port)
    client.send_hello()
    logging.debug("Start game loop")
    while not quit_flag.is_quit():
        # Events
        for event in pygame.event.get():
            if event.type == QUIT:
                client.send_quit()
            elif event.type == KEYDOWN:
                logging.debug("Keydown %s" % pygame.key.name(event.key))
                if event.key == K_ESCAPE:
                    client.send_quit()
            elif event.type == KEYUP:
                logging.debug("Keyup %s" % pygame.key.name(event.key))
        # Update
        if server:
            server.update()
        client.update()
        # Graphics
        screen.fill((0,0,0))
        client.render(screen)
        pygame.display.flip()
        # Timing
        clock.tick(60)
    logging.info("Quit")

if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.set_defaults(server=True)
    parser.add_option("-s", "--server", action="store_true", dest="server")
    parser.add_option("-c", "--client", action="store_false", dest="server")
    parser.add_option("-a", "--address", type="string", dest="address", default="localhost")
    parser.add_option("-p", "--port", type="int", dest="port", default=11235)
    (options, args) = parser.parse_args()
    main(server=options.server, address=options.address, port=options.port)
