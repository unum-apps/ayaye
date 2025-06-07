#!/usr/bin/env python

import os
from setuptools import setup

version = os.environ.get("BUILD_VERSION")

if version is None:
    with open("VERSION", "r") as version_file:
        version = version_file.read().strip()

setup(
    name="unum-ayaye",
    version=version,
    package_dir = {'': 'daemon/lib'},
    py_modules = ['unum_ayaye'],
    install_requires=[
        'ayaye.py==2.4.0'
    ]
)
