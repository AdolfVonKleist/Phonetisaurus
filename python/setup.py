#!/usr/bin/python
from setuptools import setup, find_packages
import glob
#Install phonetisaurus 
setup (
    name         = 'phonetisaurus',
    version      = '0.3',
    description  = 'Phonetisaurus G2P python package (OpenFst-1.6.x)',
    url          = 'http://code.google.com/p/phonetisaurus',
    author       = 'Josef Novak',
    author_email = 'josef.robert.novak@gmail.com',
    license      = 'BSD',
    packages=find_packages(),
    data_files   = [
        ('.', ['Phonetisaurus.so'])
    ],
    include_package_data = True,
    install_requires = ["argparse", "bottle"],
    zip_safe     = False
)
