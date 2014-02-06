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
				is_success = self.transcode(videofile, transcoder_args)
				self.scheduler.end(videofile, is_success)
			except LockError:
				log.info('Couldn\'t acquire a lock. Skipping file: ' + destfullpath)

			videofile = self.scheduler.get_next_videofile()

class FFmpegTranscoder(Transcoder):
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
			ffmpeg_args.append('23')

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

		log.info('Starting ' + filename)
		log.debug('CMD = ' + " ".join(ffmpeg_args))

		def log_queue_worker(pipe, queue, stop_event):
			while True:
				chunk = pipe.read(256)
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


		hour, minute, second = videofile.duration.split(':')
		target_seconds = float(hour) * 3600 + float(minute) * 60 + float(second)

		avg_fps, encode_time_start, num_samples = (0, time.time(), 0)
		while process.poll() is None or not queue.empty():
			if not queue.empty():
				chunk = queue.get()
				log.debug(chunk)
				queue.task_done()
				for line in chunk.split("\n"):
					match = re.search('frame=\s*([^\s]+)\s*fps=\s*([^\s]+)\s*q=\s*([^\s]+)\s*size=\s*([^\s]+)\s*time=\s*([^\s]+)\s*bitrate=\s*([^\s]+)\s*', line)
					if match:
						frame, fps, q, size, video_time, bitrate = match.groups()
						hour, minute, second = video_time.split(':')
						current_seconds = float(hour) * 3600 + float(minute) * 60 + float(second)
						progress = int(current_seconds/target_seconds*10000) / 100.0

						avg_fps += float(fps)
						num_samples += 1
						
						sys.stdout.write(
							("In progress ({progress}%) "	
							+ "fps = {fps} "
							+ "time = {video_time} "
							+ "bitrate = {bitrate} "
							+ "size = {size} "
							+ "\r").format( 
								progress = progress,
								fps = fps,
								video_time = video_time,
								bitrate = bitrate,
								size = size
							)
						)
						sys.stdout.flush()

		sys.stdout.write('                                                                                             \r')
		sys.stdout.flush()

		process.wait()
		thread.join(10)
		
		if process.returncode != 0:
			log.error('ERROR: transcoding ' + filename + ' closed with unsuccessful exit code: ' + str(process.returncode))
			return False

		avg_fps = int(avg_fps / num_samples)
		total_sec = int(time.time() - encode_time_start)
		total_min = int(total_sec / 60.0)
		remainder_sec = total_sec % 60
		encode_time = str(remainder_sec) + 's'
		if total_min > 0:
			encode_time = str(total_min) + 'm ' + encode_time
		sys.stdout.write(("Encode time = {encode_time}, Avg fps = {fps}\n").format(encode_time = encode_time, fps = avg_fps))
		sys.stdout.flush()
		log.info('Finished ' + filename, 'green')
		return True

