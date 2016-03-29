#!/usr/bin/env python

from setuptools import setup

sctk = {
    "name": "obscura",
    "description": "Python camera rail controller",
    "author":"Giles Hall",
    "author_email": "giles@polymerase.org",
    "packages": ["obscura"],
    "package_dir": {"obscura": "src"},
    "install_requires": [
        "gphoto2",
        "exifread",
    ],
    "url": "https://github.com/vishnubob/obscura",
}

if __name__ == "__main__":
    setup(**sctk)
