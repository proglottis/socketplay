# SocketPlay - Simple client/server python game.
# Copyright (C) 2008 James Fargher

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms of the Do What The Fuck You Want
# To Public License, Version 2, as published by Sam Hocevar. See
# http://sam.zoy.org/wtfpl/COPYING for more details.

import logging
import pygame
from pygame.locals import *
import socket
import select
import struct

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

def cmd_spawn(type, color):
    return cmd_header(
            cmd_command(CMD_SPAWN, struct.pack("!BBBB", type, *color)))

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

class ServerBoxman(object):
    def __init__(self, color=(255,255,255)):
        self.rect = pygame.Rect(0,0,20,20)
        self.color = color

    def update(self, **dict):
        self.rect.x += 1
        self.rect.y += 1

class ServerHelloDispatch(object):
    def __init__(self, cmdqueue, players):
        self.cmdqueue = cmdqueue
        self.players = players

    def dispatch(self, data, address):
        if address not in self.players:
            boxman = ServerBoxman()
            self.players[address] = boxman
            self.cmdqueue.push(cmd_spawn(ENT_PLAYER, boxman.color), address)
            logging.debug("Server:Hello:New client:%s", repr(address))
        else:
            logging.debug("Server:Hello:Client already known")

class ServerQuitDispatch(object):
    def __init__(self, cmdqueue, players):
        self.cmdqueue = cmdqueue
        self.players = players

    def dispatch(self, data, address):
        if address in self.players:
            del self.players[address]
            self.cmdqueue.push(cmd_quit(), address)
            logging.debug("Server:Quit:Client quit:%s", repr(address))
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
    def __init__(self, sock_server):
        self.sock_server = sock_server

    def update(self):
        self.sock_server.update()

def create_server(address, port=11235):
    players = {}
    sock_writequeue = SocketWriteQueue()
    hello = ServerHelloDispatch(sock_writequeue, players)
    quit = ServerQuitDispatch(sock_writequeue, players)
    cmd = ServerCommandDispatch(hello, quit)
    header = HeaderDispatch(cmd)
    sock_dispatcher = SocketReadDispatch(header)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(0)
    sock.bind((address, port))
    sock_server = SocketServer(sock_dispatcher, sock_writequeue, sock)
    server = Server(sock_server)
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
    def __init__(self, group):
        self.group = group

    def dispatch(self, data, address):
        type, color_r, color_g, color_b = struct.unpack("!BBBB", data[:4])
        color = (color_r, color_g, color_b)
        if type == ENT_PLAYER:
            logging.debug("Client:Spawn:ENT_PLAYER")
            self.group.add(ClientBoxman(color))
        elif type == ENT_BOXMAN:
            logging.debug("Client:Spawn:ENT_BOXMAN")
            self.group.add(ClientBoxman(color))
        else:
            logging.warning("Client:Spawn:Unknown type")

class ClientCommandDispatch(object):
    def __init__(self, quit_dispatcher, spawn_dispatcher):
        self.quit_dispatcher = quit_dispatcher
        self.spawn_dispatcher = spawn_dispatcher

    def dispatch(self, data, address):
        cmd, = struct.unpack("!B", data[:1])
        if cmd == CMD_QUIT:
            logging.debug("Client:Command:CMD_QUIT")
            self.quit_dispatcher.dispatch(data[1:], address)
        elif cmd == CMD_SPAWN:
            logging.debug("Client:Command:CMD_SPAWN")
            self.spawn_dispatcher.dispatch(data[1:], address)
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
    def __init__(self, sock_server, sendto, group):
        self.sock_server = sock_server
        self.sendto = sendto
        self.group = group

    def send_hello(self):
        self.sock_server.queue.push(cmd_hello(), self.sendto)

    def send_quit(self):
        self.sock_server.queue.push(cmd_quit(), self.sendto)

    def update(self):
        self.sock_server.update()

    def render(self, surface):
        self.group.draw(surface)

def create_client(quit_flag, address, port=11235):
    group = pygame.sprite.Group()
    quit_dispatcher = ClientQuitDispatch(quit_flag)
    spawn_dispatcher = ClientSpawnDispatch(group)
    cmd_dispatcher = ClientCommandDispatch(quit_dispatcher, spawn_dispatcher)
    header_dispatcher = HeaderDispatch(cmd_dispatcher)
    sock_dispatcher = SocketReadDispatch(header_dispatcher)
    sock_writequeue = SocketWriteQueue()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(0)
    sendto = (address, port)
    sock_server = SocketServer(sock_dispatcher, sock_writequeue, sock)
    client = Client(sock_server, sendto, group)
    return client

if __name__ == "__main__":
    quit_flag = ClientQuit()
    logging.info("Socket Play")
    logging.debug("Start pygame")
    pygame.init()
    logging.debug("Create screen")
    screen = pygame.display.set_mode((800, 600))
    logging.debug("Create timer")
    clock = pygame.time.Clock()
    logging.debug("Start server")
    server = create_server("localhost")
    logging.debug("Start client")
    client = create_client(quit_flag, "localhost")
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
        server.update()
        client.update()
        # Graphics
        screen.fill((0,0,0))
        client.render(screen)
        pygame.display.flip()
        # Timing
        clock.tick(60)
    logging.info("Quit")
