VidScan
=======

VidScan is a batch video encoding tool for creating Chromecast, iPhone/iPad, and smart TV (DLNA) compatible encodings. 

Main features:

- Maximum device compatibility with H.264 (High) 8/10 bit and AAC audio transcoding
- Splits transcoding among multiple computers using a scheduling algorithm and cross-platform file locking
- Simple command-line interface and a non-interactive option for starting from cron and other scripts

Also:

- Optimized scanning and transcoding logic for quality and encoding speed
- Thorough logging and error reporting
- Scalable OO design and developer support
- Extensively tested in a cross platform environment

## Requirements
Python (2.x) and FFmpeg (h264 + aac support) is required
### Python
- Python 2.6 or 2.7 in the PATH (3+ doesn't work)
- setuptools, a common lib for managing python packages is requried: https://pypi.python.org/pypi/setuptools#installation-instructions
    - On Windows, download `ez_setup.py` and run `python ez_setup.py`
    - On Linux/OSX run 
            
            wget https://bitbucket.org/pypa/setuptools/raw/bootstrap/ez_setup.py -O - | sudo python

### FFmpeg
Required: ***FFmpeg + h264 (libx264) + aac (libfdk_aac) + mp3 (lame) support***

- Windows instructions
    - http://taer-naguur.blogspot.com/2013/09/compiling-x64x86-ffmpeg-with-fdk-aac-lib-on-64bit-windows-how-to.html
- OSX
    - https://trac.ffmpeg.org/wiki/MacOSXCompilationGuide
    - Brew is the easiest way: `brew install ffmpeg --with-fdk-aac`
- Linux
    - https://trac.ffmpeg.org/wiki/UbuntuCompilationGuide

### Path
The commands `x264` `ffmpeg` `python` (python 2.6+) must be on the path.

Also on windows it's helpful to add the python scripts folder (e.g. `c:\Python27\Scripts`) to the PATH but this isn't required for runtime.

## Installing

### Windows
From project folder run `python setup.py install`

    $ python setup.py install
    
## Running

### Windows
Python setup installs an executable in the `Scripts` folder:
`c:\Python27\Scripts\vidscan.exe`

### Multiple box transcoding example
Say we have a Windows and a Mac box which will split transcoding duties:

- Have a network share (smb) with 2 folders for "source" and "destination"
- Mount up the share:
    - On the Windows box map the share to a drive: `net use y:\ \\my-server\public`
    - On the Mac box, browse via finder to the `\\my-server\public` and it will be automatically mapped to this folder on your computer `/Volumes/public` -- check that it exists.
- On each computer start VidScan:
    - Windows, `vidscan -s Y:\source -d Y:\destination`
    - Mac, `vidscan -s /Volumes/public/source -d /Volumes/public/destination`
- Follow the prompts and that's it!


## Uninstall
To uninstall you must have `pip` https://pypi.python.org/pypi/pip. 

`easy_install pip` or `c:\Python27\Scripts\easy_install.exe install pip`.

Then run `pip uninstall vidscan` or `c:\Python27\Scripts\pip.exe uninstall vidscan`:

    C:\>c:\Python27\Scripts\pip.exe uninstall VidScan
    ...
    Proceed (y/n)? 
    

