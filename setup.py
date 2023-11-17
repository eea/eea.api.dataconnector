""" eea.api.dataconnector Installer
"""
import os
from os.path import join

from setuptools import find_packages, setup

NAME = "eea.api.dataconnector"
PATH = NAME.split(".") + ["version.txt"]
VERSION = "1.0.0"


def read(filename):
    """
    Read the contents of a file.

    Parameters:
    - filename (str): The path to the file to be read.

    Returns:
    - str: The contents of the file as a string.

    If reading as text fails due to a UnicodeDecodeError, the function
    will retry opening the file as bytes and decode it using UTF-8.
    """
    with open(filename, "r", encoding="utf8") as file:
        try:
            return file.read()
        except UnicodeDecodeError:
            pass
    # Opening and reading as text failed, so retry opening as bytes.
    with open(filename, "rb") as file:
        contents = file.read()
        return contents.decode("utf-8")


with open(join(*PATH), "r", encoding="utf8") as version_file:
    VERSION = version_file.read().strip()

long_description = (
    read("README.rst") +
    "\n" +
    read(os.path.join("docs", "HISTORY.txt")) +
    "\n"
)

setup(
    name=NAME,
    version=VERSION,
    description="eea.api.dataconnector integration for Plone",
    long_description_content_type="text/x-rst",
    long_description=long_description,
    classifiers=[
        "Environment :: Web Environment",
        "Framework :: Plone",
        "Framework :: Plone :: Addon",
        "Framework :: Plone :: 5.2",
        "Framework :: Plone :: 6.0",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
    ],
    keywords="EEA Add-ons Plone Zope",
    author="European Environment Agency: IDM2 A-Team",
    author_email="eea-edw-a-team-alerts@googlegroups.com",
    url="https://github.com/eea/eea.api.dataconnector",
    license="GPL version 2",
    packages=find_packages(exclude=["ez_setup"]),
    namespace_packages=["eea", "eea.api"],
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        "setuptools",
        # -*- Extra requirements: -*-
        "mo-sql-parsing",
        "XlsxWriter",
        "collective.folderishtypes",
        "eea.schema.slate",
    ],
    extras_require={
        "test": [
            "plone.app.testing",
        ],
    },
    entry_points="""
    [z3c.autoinclude.plugin]
    target = plone
    """,
)
