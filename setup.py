#!/usr/bin/python
from setuptools import setup

#Install phonetisaurus 
setup (name         = 'phonetisaurus',
       version      = '0.2',
       description  = 'Phonetisaurus G2P python package',
       url          = 'http://code.google.com/p/phonetisaurus',
       author       = 'Josef Novak',
       author_email = 'josef.robert.novak@gmail.com',
       license      = 'BSD',
       packages     = ['phonetisaurus'],
       package_data = {'' : ['Phonetisaurus.so']},
       include_package_data = True,
       zip_safe     = False)

#Install the RnnLM bindings
setup (name         = 'rnnlm',
       version      = '0.1',
       description  = 'RnnLM python bindings.',
       url          = 'http://code.google.com/p/phonetisaurus',
       author       = 'Josef Novak',
       author_email = 'josef.robert.novak@gmail.com',
       license      = 'BSD',
       packages     = ['rnnlm'],
       package_data = {'' : ['RnnLM.so']},
       include_package_data = True,
       zip_safe     = False)
