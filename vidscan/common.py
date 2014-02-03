import json
import socket
import hashlib
import os
from colorama import Fore, Back, Style
import logging

EXTENSION_WHITELIST = ['avi', 'mkv', 'mp4', 'm4v']

DEBUG_SHORT_TRANSCODE = False
DEBUG_LOG_ENABLE = False

class AppJsonEncoder(json.JSONEncoder):
	def default(self, obj):
		if hasattr(obj, '__dict__'):
			return obj.__dict__

		return json.JSONEncoder.default(self, obj)

class AppError(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return repr(self.value)

def json_prettify(obj):
	return json.dumps(obj, sort_keys=True, indent=4, separators=(',', ': '), cls=AppJsonEncoder)

def json_prettify_to_file(obj, file):
	json.dump(obj, file, sort_keys=True, indent=4, separators=(',', ': '), cls=AppJsonEncoder)


def gethostname():
	return socket.gethostname().split('.')[0]

def md5Checksum(filePath):
    with open(filePath, 'rb') as fh:
        m = hashlib.md5()
        while True:
            data = fh.read(8192)
            if not data:
                break
            m.update(data)
        return m.hexdigest()


class AppLogger(object):
	COLOR_MAP = {
		'red' : Fore.RED,
		'green' : Fore.GREEN,
		'magenta' : Fore.MAGENTA,
		'blue' : Fore.BLUE,
		'yellow' : Fore.YELLOW,
		'cyan' : Fore.CYAN
	}

	def __init__(self, name):
		self.logger = logging.getLogger(name)


	def debug(self, msg, fore_color=None):
		self.logger.debug(msg)
		if DEBUG_LOG_ENABLE:
			if fore_color:
				print(AppLogger.COLOR_MAP[fore_color.lower()] + msg)
			else:
				print(msg)

	def info(self, msg, fore_color=None):
		self.logger.info(msg)
		if fore_color:
			print(AppLogger.COLOR_MAP[fore_color.lower()] + msg)
		else:
			print(msg)

	def warn(self, msg):
		self.logger.warn(msg)
		print(Fore.MAGENTA + msg)

	def error(self, msg):
		self.logger.error(msg)
		print(Fore.RED + msg)

