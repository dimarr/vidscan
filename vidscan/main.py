#!/usr/bin/env python


import logging
import logging.config
import sys
import getopt
from termcolor import colored,cprint
import colorama
import re
import os
import io
import cStringIO

vidscan_log_file = os.path.join(os.path.expanduser("~"), 'vidscan.log')
logconf_file = os.path.join(os.path.dirname(__file__), 'logging.conf')
logging.config.fileConfig(logconf_file, disable_existing_loggers=True, defaults = {'logFilePath': vidscan_log_file})

from vidscan import common
from common import AppLogger
from vidscan.VideoFile import VideoFile, VideoFileOp
from vidscan.Scanner import SourceScanner
from vidscan.Transcoder import FFmpegTranscoder
from vidscan.Scheduler import Scheduler

colorama.init(autoreset=True)
log = AppLogger(__name__)

def help():
	print 'VidScan, a batch video encoding tool.\n'
	usage()

def usage():
	print '''
Common commands:
	vidscan --src /dir/movies --dst /dir/destination
	vidscan --src /dir/movies --datafile videos.json --whatif 

Startup:
	-h, --help				Print this help			 

Transcoding:
	-s, --src DIR				Scans DIR for video files
	-d. --dst DIR				Outputs transcoded files to DIR. DIR will be created if it doesn't exist

Misc:
	-y					Attempt to transcode without prompting for confirmation
	-f, --datafile FILE			Save list of detected videos to FILE (in JSON format)
	-w, --whatif				Do a dry run to see proposed changes. No files will be transcoded with this option 
'''.strip()


def main():

	srcdir = ''
	dstdir = ''
	yestranscode = ''
	whatif = ''
	datafile = ''
	try:
		optlist, args = getopt.getopt(sys.argv[1:],"hs:d:ywf:",["help","src=", "dst=","","whatif","datafile","debug-short-transcode", "debug-log-enable"])
	except getopt.GetoptError as e:
		print 'Input error: ' + e.msg
		usage();
		sys.exit(2)
	for opt, arg in optlist:
		if opt in ('-h', '--help'):
			help()
			sys.exit()
		elif opt in ('-s', '--src'):
			srcdir = arg
		elif opt in ('-d', '--dst'):
			dstdir = arg
		elif opt == '-y':
			yestranscode = True
		elif opt in ('-w', '--whatif'):
			whatif = True
		elif opt in ('-f', '--datafile'):
			datafile = arg
		elif opt == '--debug-short-transcode':
			log.warn('DEBUG_SHORT_TRANSCODE On')
			common.DEBUG_SHORT_TRANSCODE = True
		elif opt == '--debug-log-enable':
			log.warn('DEBUG_LOG_ENABLE On')
			common.DEBUG_LOG_ENABLE = True
		else:
			print 'invalid option: ' + opt
			usage()
			sys.exit(2)
	if not srcdir or not os.path.isdir(srcdir):
		print 'missing or invalid source'
		usage()
		sys.exit(2)
	if not whatif and (not dstdir or os.path.isfile(dstdir)):
		print 'missing or invalid destination'
		usage()
		sys.exit(2)


	cprint(
	'''
 __      ___     _  _____                 
 \ \    / (_)   | |/ ____|                
  \ \  / / _  __| | (___   ___ __ _ _ __  
   \ \/ / | |/ _` |\___ \ / __/ _` | '_ \ 
    \  /  | | (_| |____) | (_| (_| | | | |
     \/   |_|\__,_|_____/ \___\__,_|_| |_|

 2014
 github.com/dimarr/vidscan
	''', 'blue')
	cprint('Logging to ' + vidscan_log_file, 'cyan')
	log.info('Source dir is ' + srcdir, 'yellow')

	"""
	Scanner
	"""
	data_out = ''
	if datafile:
		data_out = open(datafile, 'w')

	result = SourceScanner(srcdir, data_out).run()

	if data_out:
		data_out.close()


	"""
	Scheduler
	"""
	scheduler = Scheduler(result.videofiles, dstdir)

	completed_dict = {}

	for tupl in scheduler.get_completed_list():
		instance_name = tupl[0]
		videofile = tupl[1]
		destinationfile = tupl[2]
		destinationfile.relpath
		completed_dict[videofile.relpath] = tupl


	"""
	Print scanner and scheduler info
	"""
	log.info('# Extensions Found:', 'yellow')
	log.info(common.json_prettify(result.extension_count_map))

	log.info('# Video Codecs Found:', 'yellow')
	log.info(common.json_prettify(result.v_codec_count_map))

	log.info('# Audio Codecs Found:', 'yellow')
	log.info(common.json_prettify(result.a_codec_count_map))

	log.info('Previously completed transcodes:', 'yellow')
	for vf in result.videofiles:
		if vf.relpath in completed_dict:
			tupl = completed_dict[vf.relpath]
			instance_name = tupl[0]
			videofile = tupl[1]
			destinationfile = tupl[2]
			
			log.info(os.path.join(dstdir,destinationfile.relpath) + ' (status=' + destinationfile.status + ', instance=' + instance_name + ')')
			
	log.info('Files to transcode:', 'yellow')
	num_transcode = 0
	for vf in result.videofiles:
		if vf.op_flag and vf.relpath not in completed_dict:
			num_transcode += 1
			log.info(os.path.basename(vf.fullpath))
			if vf.op_flag & VideoFileOp.TRANSCODE_VIDEO:
				log.info('\tVideo: ' + vf.v_codec + ' --> h264 (High) [mp4]')
			if vf.op_flag & VideoFileOp.TRANSCODE_AUDIO:
				log.info('\tAudio: ' + vf.a_codec + ' --> aac')

	if whatif:
		log.info('Found ' + str(num_transcode) + ' files to transcode')
		log.info('Running in "whatif" mode. Exiting.', 'cyan')
		sys.exit()
	
	if not num_transcode:
		log.info('No transcoding needed. Exiting.', 'cyan')
		sys.exit()

	do_continue = ''
	if yestranscode:
		do_continue = 'y'

	while not do_continue:
		do_continue = raw_input(colored('\nFound ' + str(num_transcode) + ' files to transcode. Do you wish to Continue (y/n) ? ', 'yellow'))
		if do_continue not in ['y','n']:
			print 'Invalid choice: ' + do_continue + '. Please try again.'
			do_continue = ''

	if do_continue.strip().lower() != 'y':
		log.info('Exiting as per user command')
		sys.exit()

	if not os.path.isdir(dstdir):
		os.makedirs(dstdir)

	log.info('Initializing transcoder...')
	FFmpegTranscoder(dstdir, result.videofiles, scheduler).run()
	log.info('Finished transcoding. Exiting.')
	
if __name__ == "__main__":
	main()

