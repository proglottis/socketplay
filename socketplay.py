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

import pyglet

from client import create_client
from server import create_server

logging.basicConfig(level=logging.DEBUG)

class MainWindow(pyglet.window.Window):
    def __init__(self, client):
        super(MainWindow, self).__init__()
        self.clock = pyglet.clock.ClockDisplay()
        self.client = client

    def on_key_press(self, symbol, modifiers):
        if symbol == pyglet.window.key.UP:
            self.client.start_move(forward=True)
        elif symbol == pyglet.window.key.DOWN:
            self.client.start_move(backward=True)
        elif symbol == pyglet.window.key.LEFT:
            self.client.start_move(rot_ccw=True)
        elif symbol == pyglet.window.key.RIGHT:
            self.client.start_move(rot_cw=True)
        elif symbol == pyglet.window.key.ESCAPE:
            self.client.send_quit()

    def on_key_release(self, symbol, modifiers):
        if symbol == pyglet.window.key.UP:
            self.client.stop_move(forward=True)
        elif symbol == pyglet.window.key.DOWN:
            self.client.stop_move(backward=True)
        elif symbol == pyglet.window.key.LEFT:
            self.client.stop_move(rot_ccw=True)
        elif symbol == pyglet.window.key.RIGHT:
            self.client.stop_move(rot_cw=True)

    def on_client_quit(self):
        pyglet.app.event_loop.exit()

    def on_close(self):
        self.client.send_quit()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self):
        self.clear()
        self.client.draw()
        self.clock.draw()

def start(server=True, address="localhost", port=11235):
    """Entry point"""
    pyglet.resource.path = ['res', 'res/images']
    pyglet.resource.reindex()
    if server:
        logging.debug("Start server")
        server = create_server("0.0.0.0", port)
        pyglet.clock.schedule_interval(server.update, 1/20.0)
    logging.debug("Start client")
    client = create_client(address, port)
    client.send_hello()
    pyglet.clock.schedule_interval(client.update, 1/60.0)
    logging.debug("Open window")
    window = MainWindow(client)
    client.push_handlers(window)
    pyglet.app.run()

def parse_arguments():
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
    start(server=options.server, address=options.address, port=options.port)

if __name__ == "__main__":
    parse_arguments()
