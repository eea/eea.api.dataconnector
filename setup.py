""" eea.restapi.dataconnector Installer
"""
import os
from os.path import join

from setuptools import find_packages, setup

NAME = "eea.api.dataconnector"
PATH = NAME.split(".") + ["version.txt"]
VERSION = open(join(*PATH)).read().strip()

setup(
    name=NAME,
    version=VERSION,
    description="eea.restapi dataconnector integration for Plone",
    long_description_content_type="text/x-rst",
    long_description=(
        open("README.rst").read() +
        "\n" +
        open(os.path.join("docs", "HISTORY.txt")).read()
    ),
    classifiers=[
        "Environment :: Web Environment",
        "Framework :: Plone",
        "Framework :: Plone :: Addon",
        "Framework :: Plone :: 5.1",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
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
    python_requires="==2.7",
    install_requires=[
        "setuptools",
        # -*- Extra requirements: -*-
        "moz-sql-parser",
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
