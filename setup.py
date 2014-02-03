#!/usr/bin/env python

from setuptools import setup, find_packages
setup(
    name = "VidScan",
    version = "1.0",
    packages = find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    entry_points = {
        'console_scripts' : ['vidscan=vidscan.main:main']
    },
    package_data = {
        '': ['*.conf']
    },

    install_requires = [
        "termcolor>=1.1",
        "colorama>=0.2",
		"zc.lockfile>=1.1"
    ]
)
