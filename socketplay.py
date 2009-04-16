"""
SocketPlay

Simple client/server python game.
"""
# Copyright (C) 2008 James Fargher

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms of the Do What The Fuck You Want
# To Public License, Version 2, as published by Sam Hocevar. See
# http://sam.zoy.org/wtfpl/COPYING for more details.

import logging
import optparse
import random
import struct

import pygame

from protocol import command, dispatch
import sockwrap

logging.basicConfig(level=logging.DEBUG)

class IdentFetchError(Exception):
    """Error raised when no unique identities are available"""
    pass

class IdentAlloc(object):
    """Manage unique identity numbers in range"""
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
    """Server Boxman entity"""
    SPEED = 2
    COLORS = (
        (0, 0, 255),
        (0, 255, 0),
        (0, 255, 255),
        (255, 0, 0),
        (255, 0, 255),
        (255, 255, 0),
        (255, 255, 255),
    )

    def __init__(self, id):
        self.id = id
        self.color = random.choice(self.COLORS)
        self.rect = pygame.Rect(0, 0, 20, 20)
        self.north = False
        self.east = False
        self.south = False
        self.west = False

    def set_direction(self, direction):
        self.north, self.east, self.south, self.west = direction

    def update(self, **dict):
        if self.north:
            self.rect.y -= self.SPEED
        if self.south:
            self.rect.y += self.SPEED
        if self.west:
            self.rect.x -= self.SPEED
        if self.east:
            self.rect.x += self.SPEED

class ServerBoxmanFactory(object):
    """Server Boxman entity factory"""
    def create(self, id):
        return ServerBoxman(id)

class Server(object):
    """Handle updating entities and socket server"""
    def __init__(self, sock_server, updatecmd, players):
        self.sock_server = sock_server
        self.updatecmd = updatecmd
        self.players = players

    def update(self):
        for player in self.players.itervalues():
            player.update()
        for address in self.players.iterkeys():
            self.updatecmd.send(self.players.values(), address)
        self.sock_server.update()

def create_server(address, port=11235):
    """Server creation factory method"""
    players = {}
    idalloc = IdentAlloc(256)
    sock_writequeue = sockwrap.SocketWriteQueue()
    boxmanfactory = ServerBoxmanFactory()
    headpack = command.HeaderPack(sock_writequeue)
    cmdpack = command.CommandPack(headpack)
    quitcmd = command.QuitCommand(cmdpack)
    spawncmd = command.SpawnCommand(cmdpack)
    destroycmd = command.DestroyCommand(cmdpack)
    updatecmd = command.UpdateCommand(cmdpack)
    hello = dispatch.ServerHelloDispatch(spawncmd, players, idalloc,
                                         boxmanfactory)
    quit = dispatch.ServerQuitDispatch(quitcmd, destroycmd, players, idalloc)
    client = dispatch.ServerClientDispatch(players)
    cmd = dispatch.ServerCommandDispatch(hello, quit, client)
    header = dispatch.HeaderDispatch(cmd)
    sock_dispatcher = sockwrap.SocketReadDispatch(header)
    sock = sockwrap.create_server_socket(address, port)
    sock_server = sockwrap.SocketServer(sock_dispatcher, sock_writequeue, sock)
    server = Server(sock_server, updatecmd, players)
    return server

class ClientBoxman(pygame.sprite.Sprite):
    """Client Boxman entity"""
    def __init__(self, color=(255,255,255)):
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.Surface((20,20))
        self.image.fill(color)
        self.rect = self.image.get_rect()

    def update(self, **dict):
        pass

class ClientBoxmanFactory(object):
    """Client Boxman entity factory"""
    def create(self, color):
        return ClientBoxman(color)

class ClientQuit(object):
    """Dispatch packet unwrapping client quit command"""
    def __init__(self):
        self.quit = False

    def set_quit(self):
        self.quit = True

    def is_quit(self):
        return self.quit

class Client(object):
    """Handle updating and rendering client entities and socket server"""
    def __init__(self, sock_server, hellocmd, quitcmd, clientcmd, sendto,
                 players):
        self.sock_server = sock_server
        self.hellocmd = hellocmd
        self.quitcmd = quitcmd
        self.clientcmd = clientcmd
        self.sendto = sendto
        self.players = players
        self.north = False
        self.east = False
        self.south = False
        self.west = False
        self.changed = False

    def send_hello(self):
        self.hellocmd.send(self.sendto)

    def send_quit(self):
        self.quitcmd.send(self.sendto)

    def send_client(self):
        if self.changed:
            dir = (self.north, self.east, self.south, self.west)
            self.clientcmd.send(dir, self.sendto)
            self.changed = False

    def start_move(self, north=False, east=False, south=False, west=False):
        self.north = self.north or north
        self.east = self.east or east
        self.south = self.south or south
        self.west = self.west or west
        self.changed = north or east or south or west

    def stop_move(self, north=False, east=False, south=False, west=False):
        self.north = self.north and not north
        self.east = self.east and not east
        self.south = self.south and not south
        self.west = self.west and not west
        self.changed = north or east or south or west

    def update(self):
        self.send_client()
        self.sock_server.update()
        for player in self.players.itervalues():
            player.update()

    def render(self, surface):
        for player in self.players.itervalues():
            surface.blit(player.image, player.rect)

def create_client(quit_flag, address, port=11235):
    """Client creation factory method"""
    players = {}
    boxmanfactory = ClientBoxmanFactory()
    quit_dispatcher = dispatch.ClientQuitDispatch(quit_flag)
    spawn_dispatcher = dispatch.ClientSpawnDispatch(players, boxmanfactory)
    destroy_dispatcher = dispatch.ClientDestroyDispatch(players)
    update_dispatcher = dispatch.ClientUpdateDispatch(players)
    cmd_dispatcher = dispatch.ClientCommandDispatch(quit_dispatcher,
                                                    spawn_dispatcher,
                                                    destroy_dispatcher,
                                                    update_dispatcher)
    header_dispatcher = dispatch.HeaderDispatch(cmd_dispatcher)
    sock_dispatcher = sockwrap.SocketReadDispatch(header_dispatcher)
    sock_writequeue = sockwrap.SocketWriteQueue()
    headpack = command.HeaderPack(sock_writequeue)
    cmdpack = command.CommandPack(headpack)
    hellocmd = command.HelloCommand(cmdpack)
    quitcmd = command.QuitCommand(cmdpack)
    clientcmd = command.ClientCommand(cmdpack)
    sock = sockwrap.create_client_socket()
    sendto = (address, port)
    sock_server = sockwrap.SocketServer(sock_dispatcher, sock_writequeue, sock)
    client = Client(sock_server, hellocmd, quitcmd, clientcmd, sendto, players)
    return client

def main(server=True, address="localhost", port=11235):
    """Entry point"""
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
            if event.type == pygame.QUIT:
                client.send_quit()
            elif event.type == pygame.KEYDOWN:
                logging.debug("Keydown %s" % pygame.key.name(event.key))
                if event.key == pygame.K_UP:
                    client.start_move(north=True)
                elif event.key == pygame.K_RIGHT:
                    client.start_move(east=True)
                elif event.key == pygame.K_DOWN:
                    client.start_move(south=True)
                elif event.key == pygame.K_LEFT:
                    client.start_move(west=True)
                elif event.key == pygame.K_ESCAPE:
                    client.send_quit()
            elif event.type == pygame.KEYUP:
                logging.debug("Keyup %s" % pygame.key.name(event.key))
                if event.key == pygame.K_UP:
                    client.stop_move(north=True)
                elif event.key == pygame.K_RIGHT:
                    client.stop_move(east=True)
                elif event.key == pygame.K_DOWN:
                    client.stop_move(south=True)
                elif event.key == pygame.K_LEFT:
                    client.stop_move(west=True)
        # Update
        if server:
            server.update()
        client.update()
        # Graphics
        screen.fill((0, 0, 0))
        client.render(screen)
        pygame.display.flip()
        # Timing
        clock.tick(60)
    logging.info("Quit")

if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.set_defaults(server=True)
    parser.add_option("-s", "--server", action="store_true", dest="server",
                      help="run server and client connecting to ADDRESS "
                           "via PORT")
    parser.add_option("-c", "--client", action="store_false", dest="server",
                      help="run client connecting to ADDRESS via PORT")
    parser.add_option("-a", "--address", type="string", dest="address",
                      default="localhost", help="set IP address to listen "
                              "or connect to")
    parser.add_option("-p", "--port", type="int", dest="port", default=11235,
                      help="set port to listen or connect to")
    (options, args) = parser.parse_args()
    main(server=options.server, address=options.address, port=options.port)
