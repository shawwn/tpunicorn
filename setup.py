#!/usr/bin/env python3

import setuptools
import os

package_name = "tpunicorn"
packages = setuptools.find_packages(
    include=[package_name, "{}.*".format(package_name)]
)

# Version info -- read without importing
_locals = {}
with open(os.path.join(package_name, "_version.py")) as fp:
    exec(fp.read(), None, _locals)
version = _locals["__version__"]
binary_names = _locals["binary_names"]

# Frankenstein long_description: changelog note + README
long_description = """
To find out what's new in this version of tpunicorn, please see `the repo
<https://github.com/shawwn/tpunicorn>`_.

Welcome to tpunicorn!
=====================

`tpunicorn` is a Python library and command-line program
for managing TPUs.
"""

setuptools.setup(
    name=package_name,
    version=version,
    description="TPU management",
    license="BSD",
    long_description=long_description,
    author="Shawn Presser",
    author_email="shawnpresser@gmail.com",
    url="https://github.com/shawwn/tpunicorn",
    install_requires=[
        'Click>=7.1.2',
        'six>=1.11.0',
        'ring>=0.7.3',
        'moment>=0.0.10',
        'google-auth>=0.11.0',
        'google-api-python-client>=1.7.11',
    ],
    packages=packages,
    entry_points={
        "console_scripts": [
            "{} = {}.program:cli".format(binary_name, package_name)
            for binary_name in binary_names
        ]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: BSD License",
        "Operating System :: POSIX",
        "Operating System :: Unix",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Topic :: Software Development",
        "Topic :: Software Development :: Libraries",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Software Distribution",
        "Topic :: System :: Systems Administration",
    ],
)

