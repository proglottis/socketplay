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
	return struct.pack("!6sB", "BOXMAN", len)

def cmd_unpack_header(data, offset=0):
	return struct.unpack("!6sB", data[offset:offset+7])

def cmd_pack_command(cmd):
	return struct.pack("!B", cmd)

def cmd_unpack_command(data, offset=0):
	return struct.unpack("!B", data[offset:offset+1])

def cmd_pack(cmd, data):
	part = cmd_pack_command(cmd) + data
	return cmd_pack_header(len(part)) + part

class ClientHelloCommand(object):
	def __init__(self):
		self.data = cmd_pack(CMD_HELLO, "")

class ClientQuitCommand(object):
	def __init__(self):
		self.data = cmd_pack(CMD_QUIT, "")

class ServerQuitCommand(object):
	def __init__(self, sendto):
		self.data = cmd_pack(CMD_QUIT, "")
		self.sendto = sendto

class ServerSpawnCommand(object):
	def __init__(self, sendto, type, color):
		self.data = cmd_pack(CMD_SPAWN,
					struct.pack("!BBBB", type, *color))
		self.sendto = sendto

class BoxManServer(object):
	def __init__(self, color=(255,255,255)):
		self.rect = pygame.Rect(0,0,20,20)
		self.color = color

	def update(self, **dict):
		self.rect.x += 1
		self.rect.y += 1

class BoxManClient(pygame.sprite.Sprite):
	def __init__(self, color=(255,255,255)):
		pygame.sprite.Sprite.__init__(self)
		self.image = pygame.Surface((20,20))
		self.image.fill(color)
		self.rect = self.image.get_rect()

	def update(self, **dict):
		pass

class ServerPlayer(object):
	def __init__(self, server, address):
		self.server = server
		self.address = address
		self.entity = None

	def spawn(self):
		self.entity = BoxManServer()
		self.server.push_command(ServerSpawnCommand(self.address,
						ENT_BOXMAN_CONTROLLED,
						self.entity.color))

	def packet(self, data):
		cmd, = cmd_unpack_command(data)
		if cmd == CMD_HELLO:
			if self.entity == None:
				logging.debug("Server:Recv:CMD_HELLO")
				self.spawn()
			else:
				logging.debug("Server:Recv:CMD_HELLO duplicate")
				self.server.push_command(
					ServerQuitCommand(self.address))
		elif cmd == CMD_QUIT:
			logging.debug("Server:Recv:CMD_QUIT")
			self.server.push_command(
					ServerQuitCommand(self.address))
		elif cmd == CMD_SPAWN:
			logging.debug("Server:Recv:CMD_SPAWN")

class Server(object):
	def __init__(self, server, port=11235):
		self.quit = False
		self.writequeue = []
		self.readqueue = {}
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.sock.setblocking(0)
		self.sock.bind((server, port))
		self.players = {}

	def push_command(self, command):
		self.writequeue.append(command)

	def update(self):
		sock_read, sock_write, sock_error = select.select((self.sock,),
								(self.sock,),
								(),
								0)
		for sock in sock_read:
			data, address = sock.recvfrom(4096)
			ident, length = cmd_unpack_header(data)
			if ident != "BOXMAN":
				logging.debug("Server:Bad packet!")
				break
			player = self.players.setdefault(address,
						ServerPlayer(self, address))
			player.packet(data[7:])
		for sock in sock_write:
			for cmd in self.writequeue:
				sock.sendto(cmd.data, cmd.sendto)
			self.writequeue = []

class Client(object):
	def __init__(self, server, port=11235):
		self.quit = False
		self.writequeue = []
		self.group = pygame.sprite.Group()
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.sock.setblocking(0)
		self.sendto = (server, port)
		self.push_command(ClientHelloCommand())
	
	def push_command(self, command):
		self.writequeue.append(command)

	def handle_command(self, command):
		print command

	def update(self):
		sock_read, sock_write, sock_error = select.select((self.sock,),
								(self.sock,),
								(),
								0)
		for sock in sock_read:
			data, address = sock.recvfrom(4096)
			ident, length = cmd_unpack_header(data)
			if ident != "BOXMAN":
				logging.debug("Client:Recv:Bad packet!")
				break
			cmd, = cmd_unpack_command(data, 7)
			if cmd == CMD_HELLO:
				logging.debug("Client:Recv:CMD_HELLO")
			elif cmd == CMD_QUIT:
				logging.debug("Client:Recv:CMD_QUIT")
				self.quit = True
			elif cmd == CMD_SPAWN:
				logging.debug("Client:Recv:CMD_SPAWN")
		for sock in sock_write:
			for cmd in self.writequeue:
				sock.sendto(cmd.data, self.sendto)
			self.writequeue = []

	def render(self, surface):
		self.group.draw(surface)

if __name__ == "__main__":
	quit = False
	logging.info("Socket Play")
	logging.debug("Start pygame")
	pygame.init()
	logging.debug("Create screen")
	screen = pygame.display.set_mode((800, 600))
	logging.debug("Create timer")
	clock = pygame.time.Clock()
	logging.debug("Start server")
	server = Server("localhost")
	logging.debug("Start client")
	client = Client("localhost")
	logging.debug("Start game loop")
	while not quit:
		# Events
		for event in pygame.event.get():
			if event.type == QUIT:
				client.push_command(ClientQuitCommand())
			elif event.type == KEYDOWN:
				logging.debug("Keydown %s" %
						pygame.key.name(event.key))
				if event.key == K_ESCAPE:
					client.push_command(
							ClientQuitCommand())
			elif event.type == KEYUP:
				logging.debug("Keyup %s" %
						pygame.key.name(event.key))
		# Update
		server.update()
		client.update()
		quit = quit or client.quit
		# Graphics
		screen.fill((0,0,0))
		client.render(screen)
		pygame.display.flip()
		# Timing
		clock.tick(60)
	logging.info("Quit")
