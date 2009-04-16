"""
Light UDP socket wrapper.
"""
# Copyright (C) 2008 James Fargher

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms of the Do What The Fuck You Want
# To Public License, Version 2, as published by Sam Hocevar. See
# http://sam.zoy.org/wtfpl/COPYING for more details.

import select
import socket

def create_server_socket(address, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(0)
    sock.bind((address, port))
    return sock

def create_client_socket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(0)
    return sock

class SocketReadDispatch(object):
    """Dispatch packet read from socket"""
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher

    def dispatch(self, sock):
        data, address = sock.recvfrom(4096)
        self.dispatcher.dispatch(data, address)

class SocketWriteQueue(object):
    """Queue packets to be written to a socket"""
    def __init__(self):
        self.writequeue = []

    def push(self, data, address):
        self.writequeue.append((data, address))

    def empty(self):
        return len(self.writequeue) < 1

    def write(self, sock):
        try:
            cmd = self.writequeue.pop(0)
            sock.sendto(cmd[0], cmd[1])
        except IndexError:
            pass

class SocketServer(object):
    """Handle socket and dispatch packets"""
    def __init__(self, dispatcher, queue, sock):
        self.dispatcher = dispatcher
        self.queue = queue
        self.socks = (sock,)

    def select(self):
        result = select.select(self.socks, self.socks, (), 0)
        sock_read, sock_write, sock_error = result
        for sock in sock_read:
            self.dispatcher.dispatch(sock)
        for sock in sock_write:
            self.queue.write(sock)

    def update(self):
        self.select()
        while not self.queue.empty():
            self.select()
