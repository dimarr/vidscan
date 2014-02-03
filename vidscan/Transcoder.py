import os
import sys
import subprocess
import logging
import re
import colorama
from termcolor import colored,cprint
import time

import threading
import Queue

import common
from common import AppError, AppLogger
from VideoFile import VideoFile, VideoFileOp
from Scanner import Scanner
from Scheduler import Scheduler, LockError

log = AppLogger(__name__)

class FFmpegMixin(object):
	def init_transcoder(self):
		"""
		Check for x264 support and detect the supported bit depth which will later influence ffmpeg args
		"""
		output = subprocess.Popen(["x264", "--help"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT).communicate()[0]
		match = re.search('Output bit depth: (\d+)', output)
		if match:
			self.x264_bit_depth = int(match.groups()[0])
		else:
			raise AppError("Couldn't detect x264 output bit depth. Check that the x264 executable is in your path.")
			
		log.info('Detected x264 output bit depth = ' + str(self.x264_bit_depth))


	def get_transcoder_args(self, videofile):
		newfilename = videofile.relpath
		ffmpeg_args = ['ffmpeg', '-i', videofile.fullpath, '-y']

		if common.DEBUG_SHORT_TRANSCODE:
			ffmpeg_args.extend(['-ss', '0', '-t', '120'])
		
		ffmpeg_args.append('-c:v')
		if videofile.op_flag & VideoFileOp.TRANSCODE_VIDEO:
			ffmpeg_args.append('libx264')

			if self.x264_bit_depth == 8:
				ffmpeg_args.append('-profile:v')
				ffmpeg_args.append('high')
			else:
				ffmpeg_args.append('-profile:v')
				ffmpeg_args.append('high10')

			ffmpeg_args.append('-crf')
			ffmpeg_args.append('20')

			ffmpeg_args.append('-preset')
			ffmpeg_args.append('veryfast')

			newfilename = os.path.splitext(newfilename)[0] + '.mp4'
		else:
			ffmpeg_args.append('copy')

		ffmpeg_args.append('-c:a')
		if videofile.op_flag & VideoFileOp.TRANSCODE_AUDIO:
			ffmpeg_args.append('libfdk_aac')
		else:
			ffmpeg_args.append('copy')

		newfullpath = os.path.join(self.destpath, newfilename)
		ffmpeg_args.append(newfullpath)
	
		return (ffmpeg_args, newfullpath)
	
	def transcode(self, videofile, ffmpeg_args):
		filename = os.path.basename(videofile.fullpath)

		log.info('STARTING: ' + filename, 'yellow')
		log.debug('CMD = ' + " ".join(ffmpeg_args))

		def log_queue_worker(pipe, queue, stop_event):
			"""
			Read line-by-line from pipe, writing (tag, line) to the
			queue. Also checks for a stop_event to give up before
			the end of the stream.
			"""
			while True:
				chunk = pipe.read(1000)
				while True:
					try:
						# Post to the queue with a large timeout in case the
						# queue is full.
						queue.put(chunk, block=True, timeout=60)
						break
					except Queue.Full:
						if stop_event.isSet():
							break
						continue
				if stop_event.isSet() or chunk=="":
					break
			pipe.close()


		queue = Queue.Queue(1000)
		stop_event = threading.Event()
		
		process = subprocess.Popen(ffmpeg_args, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)

		thread = threading.Thread(target=log_queue_worker, args=(process.stdout, queue, stop_event))
		thread.daemon = True
		thread.start()

		while process.poll() is None or not queue.empty():
			if not queue.empty():
				log.info(queue.get())
				queue.task_done()

		process.wait()
		thread.join(10)
		
		if process.returncode != 0:
			log.error('ERROR: transcoding ' + filename + ' closed with unsuccessful exit code: ' + str(process.returncode))
			return False

		log.info('FINISHED: ' + filename, 'green')
		return True

class Transcoder(object):
	def __init__(self, destpath, videofiles, scheduler):
		self.destpath = destpath
		self.videofiles = videofiles
		self.scheduler = scheduler

		scheduler.attach_cleanup_listener()
		self.init_transcoder()
	
	def init_transcoder(self):
		pass

	def get_transcoder_args(self, videofile):
		pass

	def transcode(self, videofile, transcoder_args):
		pass
	
	def run(self):
		"""
		Start the transcoding loop
		"""
		videofile = self.scheduler.get_next_videofile()
		while videofile is not None:
			transcoder_args, destfullpath = self.get_transcoder_args(videofile)

			try:
				self.scheduler.start(videofile, destfullpath)
			except LockError:
				log.info('Couldn\'t acquire a lock. Skipping file: ' + destfullpath)
				videofile = self.scheduler.get_next_videofile()
				continue

			is_success = self.transcode(videofile, transcoder_args)

			self.scheduler.end(videofile, is_success)

			videofile = self.scheduler.get_next_videofile()


class FFmpegTranscoder(FFmpegMixin, Transcoder):
	pass


