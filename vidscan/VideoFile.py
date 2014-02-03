
import json


class VideoFileOp:
	TRANSCODE_AUDIO=1
	TRANSCODE_VIDEO=2

class VideoFile(object):
	def __init__(self, fullpath = None, relpath = None):
			
		self.fullpath = fullpath	
		self.relpath = relpath
		self.bitrate = None
		self.duration = None
		self.v_codec = None
		self.v_resolution = None
		self.a_codec = None
		self.a_channel = None
		self.a_bitrate = None
		self.op_flag = 0
		self.size = None

	def update(self, entries):
		self.__dict__.update(entries)	
	
