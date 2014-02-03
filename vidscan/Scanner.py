import os
from subprocess import Popen, PIPE
import re

from VideoFile import VideoFile, VideoFileOp
from common import AppError, AppLogger
import common

log = AppLogger(__name__)

class SourceScanResult():
	videofiles = []
	extension_count_map = {}
	v_codec_count_map = {}
	a_codec_count_map = {}
	def addFile(self, videofile):
		self.videofiles.append(videofile)
		if videofile.v_codec not in self.v_codec_count_map:
			self.v_codec_count_map[videofile.v_codec] = 0
		self.v_codec_count_map[videofile.v_codec] += 1
		if videofile.a_codec not in self.a_codec_count_map:
			self.a_codec_count_map[videofile.a_codec] = 0
		self.a_codec_count_map[videofile.a_codec] += 1
	def incrementExtensionCount(self, ext):
		if ext not in self.extension_count_map:
			self.extension_count_map[ext] = 0
		self.extension_count_map[ext] += 1

class Scanner(object): 
	def __init__(self, path):
		self.path = path
		
	def processFile(self, fullpath, lines):
		pass

	def checkFile(self, file):
		extension = os.path.splitext(file)[1][1:]
		# Check 2 things:
		# 1) if this is not a sample file
		# 2) if extension is whitelisted
		return not re.search('[\-\.\(\)\[\]]?sample[\-\.\(\)\[\]]', file, re.IGNORECASE) and extension in common.EXTENSION_WHITELIST

	def run(self):
		videoObjs = []
		for root, dirs, files in os.walk(self.path):
			for file in files:
				if self.checkFile(file):
					fullpath = os.path.join(root, file)
					
					log.info("Processing video file " + fullpath + "...")
					
					# Call ffmpeg to get file information and capture output lines
					lines = Popen(["ffmpeg", "-i", fullpath], stdout=PIPE, stderr=PIPE).communicate()
					log.debug("\n".join(lines))

					videObj = None

					# processFile file
					try:
						videoObj = self.processFile(fullpath, lines)
					except Exception as e:
						log.error('Error processing file (' + file + '): ' + e.value)

					# Basic integrity check. Assume if duration is set then it's a valid video file
					if videoObj and videoObj.duration:
						videoObjs.append(videoObj)
					else:
						log.error('Cannot process file. Check if valid video using "ffmpeg -i <file>": ' + file)
				else:
					log.warn('Unhandled file/extension: ' + file)

		return videoObjs


class SourceScanner(Scanner):
	
	def __init__(self, path, data_out):
		super(SourceScanner, self).__init__(path)
		self.data_out = data_out

	def writeData(self, msg):
		if self.data_out:
			self.data_out.write(msg)

	def processFile(self, fullpath, lines): 
		vf = VideoFile(fullpath, os.path.relpath(fullpath, self.path).replace('\\', '/'))		
		# loop through lines of ffmpeg output
		for line in lines:
			# Extract video file info
			# Duration: 01:37:58.08, start: 0.000000, bitrate: 997 kb/s"
			match = re.search('Duration: (\d\d:\d\d:\d\d\.\d\d),[^,]+, bitrate: (\d+ [a-z\/]+)', line)
			if match:
				if vf.duration or vf.bitrate:
					raise AppError("Video file data already exists. Check regex")
				else:
					vf.duration = match.group(1)
					vf.bitrate = match.group(2)
			# Extract video stream info
			# Stream #0:0: Video: mpeg4 (Advanced Simple Profile) (XVID / 0x44495658), yuv420p, 640x352 [SAR 1:1 DAR 20:11], 23.98 tbr, 23.98 tbn, 23.98 tbc
			match = re.search('Stream #\d+:\d+[^:]*: Video: ([^,]+), [^,]+, ([^,]+)', line)
			if match:
				if vf.v_codec or vf.v_resolution:
					raise AppError('Video stream already exists. Check regex')
				else:
					vf.v_codec = match.group(1)
					vf.v_resolution = match.group(2)
			# Exract audio stream info
			# Stream #0:1: Audio: mp3 (U[0][0][0] / 0x0055), 48000 Hz, stereo, s16p, 126 kb/s
			# Stream #0:1(eng): Audio: aac, 48000 Hz, stereo, fltp (default)
			match = re.search('Stream #\d+:\d+[^:]*: Audio: ([^,]+), [^,]+, ([^,]+), [^,]+(?:, (\d+ [a-z\/]+))?', line)
			if match:
				if vf.a_codec or vf.a_channel or vf.a_bitrate:
					raise AppError('Audio stream already exists. Check regex')
				else:
					vf.a_codec = match.group(1)
					vf.a_channel = match.group(2)
					if match.group(3) is not None:
						vf.a_bitrate = match.group(3)
		# Determine if file requires video transcoding
		# These video codecs do not need transcoding:
		# 1) h264 (High)
		# 2) h264 (Main) OR h264 (Main) (avc1 / 0x31637661) 
		if not (vf.v_codec == '' or re.search('h264 \(High\)', vf.v_codec) or re.match('^h264 \(Main\)(\s\(avc1 .*)?$', vf.v_codec)):
			vf.op_flag = vf.op_flag | VideoFileOp.TRANSCODE_VIDEO
		
		# Determine if file requires audio transcoding
		if not (vf.a_codec == '' or re.search('aac|mp3|dts', vf.a_codec, re.IGNORECASE)):
		   vf.op_flag = vf.op_flag | VideoFileOp.TRANSCODE_AUDIO
		vf.size = os.path.getsize(fullpath)
		   
		return vf 

	def checkFile(self, file):
		extension = os.path.splitext(file)[1][1:]
		self.__result.incrementExtensionCount(extension) 
		return super(SourceScanner, self).checkFile(file)

	def run(self): 
		self.__result = SourceScanResult() 

		videofiles = super(SourceScanner, self).run()

		for vf in videofiles:
			self.__result.addFile(vf)


		# Dump list of videos to json file
		self.writeData(common.json_prettify(videofiles))
		return self.__result

