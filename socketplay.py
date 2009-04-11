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
) = range(3)

(
    ENT_BOXMAN,
    ENT_BOXMAN_CONTROLLED,
) = range(2)

def cmd_pack_header(len):
    return struct.pack("!6s", "BOXMAN")

def cmd_pack_command(cmd):
    return struct.pack("!B", cmd)

def cmd_unpack_command(data, offset=0):
    return struct.unpack("!B", data[offset:offset+1])

def cmd_pack(cmd, data):
    part = cmd_pack_command(cmd) + data
    return cmd_pack_header(len(part)) + part

class HelloCommand(object):
    def __init__(self, sendto):
        self.data = cmd_pack(CMD_HELLO, "")
        self.sendto = sendto

class QuitCommand(object):
    def __init__(self, sendto):
        self.data = cmd_pack(CMD_QUIT, "")
        self.sendto = sendto

class SpawnCommand(object):
    def __init__(self, sendto, type, color):
        self.data = cmd_pack(CMD_SPAWN, struct.pack("!BBBB", type, *color))
        self.sendto = sendto

class HeaderDispatch(object):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher

    def dispatch(self, data, address):
        ident, = struct.unpack("!6s", data[:6])
        if ident != "BOXMAN":
            logging.warning("HeaderDispatch:Bad header")
            return
        self.dispatcher.dispatch(data[6:], address)

class SocketDispatch(object):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher

    def dispatch(self, sock_list):
        for sock in sock_list:
            data, address = sock.recvfrom(4096)
            self.dispatcher.dispatch(data, address)

class SocketSendQueue(object):
    def __init__(self):
        self.sendqueue = []

    def push_command(self, command):
        self.sendqueue.append(command)

    def send(self, sock_list):
        for sock in sock_list:
            for cmd in self.sendqueue:
                sock.sendto(cmd.data, cmd.sendto)
            self.sendqueue = []

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
            self.cmdqueue.push_command(SpawnCommand(address,
                    ENT_BOXMAN_CONTROLLED,
                    boxman.color))
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
            self.cmdqueue.push_command(QuitCommand(address))
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
    def __init__(self, sock_dispatcher, sock_sendqueue, sock):
        self.quit = False
        self.sock_dispatcher = sock_dispatcher
        self.sock_sendqueue = sock_sendqueue
        self.sock = sock

    def update(self):
        sock_read, sock_write, sock_error = select.select((self.sock,),
                                                          (self.sock,),
                                                          (),
                                                          0)
        self.sock_dispatcher.dispatch(sock_read)
        self.sock_sendqueue.send(sock_write)

def create_server(address, port=11235):
    players = {}
    sock_sendqueue = SocketSendQueue()
    hello = ServerHelloDispatch(sock_sendqueue, players)
    quit = ServerQuitDispatch(sock_sendqueue, players)
    cmd = ServerCommandDispatch(hello, quit)
    header = HeaderDispatch(cmd)
    sock_dispatcher = SocketDispatch(header)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(0)
    sock.bind((address, port))
    server = Server(sock_dispatcher, sock_sendqueue, sock)
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
        if type == ENT_BOXMAN:
            logging.debug("Client:Spawn:ENT_BOXMAN")
            self.group.add(ClientBoxman(color))
        elif type == ENT_BOXMAN_CONTROLLED:
            logging.debug("Client:Spawn:ENT_BOXMAN_CONTROLLED")
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
    def __init__(self, sock_dispatcher, sock_sendqueue, sock, sendto, group):
        self.dispatcher = sock_dispatcher
        self.sendqueue = sock_sendqueue
        self.sock = sock
        self.sendto = sendto
        self.group = group
        # Trigger startup
        self.sendqueue.push_command(HelloCommand(self.sendto))

    def update(self):
        sock_read, sock_write, sock_error = select.select((self.sock,),
                                                          (self.sock,),
                                                          (),
                                                          0)
        self.dispatcher.dispatch(sock_read)
        self.sendqueue.send(sock_write)

    def render(self, surface):
        self.group.draw(surface)

def create_client(quit_flag, address, port=11235):
    group = pygame.sprite.Group()
    quit_dispatcher = ClientQuitDispatch(quit_flag)
    spawn_dispatcher = ClientSpawnDispatch(group)
    cmd_dispatcher = ClientCommandDispatch(quit_dispatcher, spawn_dispatcher)
    header_dispatcher = HeaderDispatch(cmd_dispatcher)
    sock_dispatcher = SocketDispatch(header_dispatcher)
    sock_sendqueue = SocketSendQueue()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(0)
    sendto = (address, port)
    client = Client(sock_dispatcher, sock_sendqueue, sock, sendto, group)
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
    logging.debug("Start game loop")
    while not quit_flag.is_quit():
        # Events
        for event in pygame.event.get():
            if event.type == QUIT:
                client.sendqueue.push_command(QuitCommand(client.sendto))
            elif event.type == KEYDOWN:
                logging.debug("Keydown %s" % pygame.key.name(event.key))
                if event.key == K_ESCAPE:
                    client.sendqueue.push_command(QuitCommand(client.sendto))
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
