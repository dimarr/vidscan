import sys
import os
import re
import time

import zc.lockfile
import json
import signal

import common
from common import AppError, AppLogger
from VideoFile import VideoFile, VideoFileOp

log = AppLogger(__name__)

class LockError(AppError):
	"""Thrown if scheduler couldn't acquire a lock on a file"""
	pass

class DestinationFile(object):
	def __init__(self, relpath=None, timestamp_start=None):
		self.status = 'IN_PROGRESS'
		self.relpath = relpath
		self.timestamp_start = timestamp_start
		self.md5 = None
		self.timestamp_end = None

	def update(self, entries):
		self.__dict__.update(entries)	

class Scheduler(object):
	def __init__(self, videofiles, destpath):
		self.skiplist = []
		self.videofiles = videofiles
		self.destpath = destpath
		self.status_list = None
		self.status_file_rw = None
		self.md5_cache = None

		"""
		Initialize md5 cache for video files in the destination folder
		"""
		self.md5_cache = {}
		for root, dirs, files in os.walk(destpath):
			for file in files:
				extension = os.path.splitext(file)[1][1:]
				if extension in common.EXTENSION_WHITELIST:
					fullpath = os.path.join(root, file)
					relpath = self.getrelpath(fullpath)
					self.md5_cache[relpath] = common.md5Checksum(fullpath)

		"""
		Scan for previous successful or failed transcodes and initialize status list
		"""
		self.status_list = []
		status_file_path = os.path.join(destpath, '_status.' + common.gethostname() + '.json')
		if os.path.isfile(status_file_path):
			self.status_file_rw = open(status_file_path, 'r+') 
		else:
			self.status_file_rw = open(status_file_path, 'w+') 

		for tupl in self.get_completed_list():
			instance_name = tupl[0]
			videofile = tupl[1]
			destinationfile = tupl[2]

			status = {
				'videofile': videofile,
				'destinationfile': destinationfile
			}			

			self.status_list.append(status)

	def attach_cleanup_listener(self):
		def clean(signum, frame):
			print '\n'
			
			try:
				log.debug('Removing lock file: ' + self.lock_fullpath)
				self.lock.close()
				time.sleep(0.5)	# this is needed for windows!
				if os.path.isfile(self.lock_fullpath):
					os.remove(self.lock_fullpath.replace('\\', '\\\\'))
			except:
				log.debug('Error removing lock file')

			try:
				log.warn('Stopping transcoder. Got a signal: ' + str(signum))

				if self.status_list and len(self.status_list) > 0 and self.status_list[-1]['destinationfile'].status == 'IN_PROGRESS':
					destinationfile = self.status_list[-1]['destinationfile']
					destinationfile.status = 'INTERRUPTED'	
					destinationfile.timestamp_end = int(time.time())
					log.warn('Transcoding ' + destinationfile.relpath + ' was interrupted')
					self.updatestatus()
			except:
				log.debug('Error updating status during signal interrupt')
			finally:
				self.closestatusfile()
				sys.exit(0)

		for sig in (signal.SIGABRT, signal.SIGILL, signal.SIGINT, signal.SIGSEGV, signal.SIGTERM):
			signal.signal(sig, clean)

	def updatestatus(self):
		if self.status_file_rw is None:
			self.openstatusfile()
		self.status_file_rw.seek(0)
		common.json_prettify_to_file(self.status_list, self.status_file_rw)
		self.status_file_rw.truncate()		# truncate it to current position ie correct size

	def closestatusfile(self):
		if self.status_file_rw is not None:
			self.status_file_rw.close()

	def is_completed(self, instance_name, videofile, destinationfile):
		status = destinationfile.status
		destrelpath = destinationfile.relpath
		md5 = destinationfile.md5

		return ( status == 'FAIL' 
				or (status == 'SUCCESS' and destrelpath in self.md5_cache and md5 == self.md5_cache[destrelpath])
				)

	def get_completed_list(self):
		return self.get_status_list(self.is_completed)

	def get_status_list(self, filter = None):
		status_relpath_dict = {}
		for file in os.listdir(self.destpath):
			match = re.match('^_status\.([^\.]+)\.json$', file)
			if match:
				log.debug('Checking ' + file)
				instance_name = match.group(1)
				instance_status_list = []

				status_json = open(os.path.join(self.destpath, file)).read().decode('utf-8')
				if status_json != '':
					try:
						instance_status_list = json.loads(status_json)
					except ValueError as e:
						raise AppError('Error loading status list. Check that it is a valid json file or remove it. Error = ' + str(e))	
						#log.warn('Error reading status file (' + file + ') so we will skip it. Error = ' + str(e))
						#log.debug('Contents of ' + file + ': ' + status_json)

				for status in instance_status_list:
					videofile = VideoFile()
					videofile.update(status['videofile'])

					destinationfile = DestinationFile()
					destinationfile.update(status['destinationfile'])

	
					destrelpath = destinationfile.relpath

					if destrelpath in status_relpath_dict:
						status_tupl = status_relpath_dict[destrelpath]
						if destinationfile.timestamp_start > status_tupl[2].timestamp_start:
							del status_relpath_dict[destrelpath]

					if destrelpath not in status_relpath_dict:
						status_relpath_dict[destrelpath] = (instance_name, videofile, destinationfile)
			
		if filter is not None:
			result = []
			for tupl in status_relpath_dict.values():
				if filter(*tupl):
					result.append(tupl)
			return result

		return status_relpath_dict.values()

	def start(self, videofile, destfullpath):
		# Create destination subfolders if necessary
		destfolder = os.path.dirname(destfullpath)
		if not os.path.exists(destfolder):
			os.makedirs(destfolder)

		try:
			self.lock_fullpath = os.path.join(destfolder,'.' + os.path.basename(destfullpath) + '.vslock')
			self.lock = zc.lockfile.LockFile(self.lock_fullpath)
		except (zc.lockfile.LockError, IOError) as e:
			self.skiplist.append(videofile.relpath)
			raise LockError('Error locking file')

		destrelpath = self.getrelpath(destfullpath).replace('\\', '/')
		destinationfile = DestinationFile(destrelpath, int(time.time()))
		status = {
			'videofile': videofile,
			'destinationfile': destinationfile 
		}

		self.status_list.append(status)
		
		self.updatestatus()

	def end(self, videofile, is_success):
		self.lock.close()
		os.remove(self.lock_fullpath)

		destinationfile = self.status_list[-1]['destinationfile']
		if is_success:
			destfullpath = os.path.join(self.destpath, destinationfile.relpath)
			destinationfile.status = 'SUCCESS'
			destinationfile.timestamp_end = int(time.time())
			destinationfile.md5 = common.md5Checksum(destfullpath)
			self.md5_cache[destinationfile.relpath] = destinationfile.md5
		else:
			destinationfile.status = 'FAIL'

		self.updatestatus()

	def get_next_videofile(self):
		completed_dict = {}
		destinationfile_dict = {}

		def filter(instance_name, videofile, destinationfile):
			is_completed = self.is_completed(instance_name, videofile, destinationfile)
			destinationfile_dict[videofile.relpath] = (instance_name,destinationfile)
			if is_completed:
				completed_dict[videofile.relpath] = 1
			return True

		self.get_status_list(filter)

		for videofile in self.videofiles:
			if videofile.op_flag and videofile.relpath not in completed_dict and videofile.relpath not in self.skiplist:
				if videofile.relpath in destinationfile_dict:
					tupl = destinationfile_dict[videofile.relpath]
					instance_name = tupl[0]
					destinationfile = tupl[1]
					destfullpath = os.path.join(self.destpath, destinationfile.relpath)
					status = destinationfile.status
					timestamp_start = destinationfile.timestamp_start
					if ((status == 'INTERRUPTED' 
						 or (status == 'IN_PROGRESS' and int(time.time()) - timestamp_start > 86400)) and os.path.isfile(destfullpath)):
							log.debug('Removing incomplete file because encoding was stopped or interrupted ' + destinationfile.relpath + ' (status=' + destinationfile.status + ', instance=' + instance_name + ')')
							os.remove(destfullpath)

					if os.path.isfile(destfullpath):
						log.debug('Skipping existing file ' + destinationfile.relpath + ' (status=' + destinationfile.status + ', instance=' + instance_name + ')')
						continue

				log.debug('Suggesting file to encode next: ' + videofile.relpath)
				return videofile

		return None

	def getrelpath(self, fullpath):
		return os.path.relpath(fullpath, self.destpath)

