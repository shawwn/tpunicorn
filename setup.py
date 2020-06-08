#!/usr/bin/env python

# Support setuptools only, distutils has a divergent and more annoying API and
# few folks will lack setuptools.
import setuptools
import os

package_name = "tpudiepie"
binary_name = "tpu"
packages = setuptools.find_packages(
    include=[package_name, "{}.*".format(package_name)]
)

# Version info -- read without importing
_locals = {}
with open(os.path.join(package_name, "_version.py")) as fp:
    exec(fp.read(), None, _locals)
version = _locals["__version__"]

# Frankenstein long_description: changelog note + README
long_description = """
To find out what's new in this version of TPUDiePie, please see `the repo
<https://github.com/shawwn/tpudiepie>`_.

{}
""".format(
    open("README.rst").read()
)

setuptools.setup(
    name=package_name,
    version=version,
    description="TPU management",
    license="BSD",
    long_description=long_description,
    author="Shawn Presser",
    author_email="shawnpresser@gmail.com",
    url="https://github.com/shawwn/tpudiepie",
    install_requires=[
        "invoke>=1.0,<2.0",
    ],
    packages=packages,
    entry_points={
        "console_scripts": [
            "{} = {}.main:program.main".format(binary_name, package_name)
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

