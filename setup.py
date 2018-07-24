# -*- coding: utf-8 -*-
# Copyright (c) 2018 Petter Reinholdtsen <pere@hungry.com>
# This file is covered by the GPLv2 or later, read COPYING for details.

import io
from os.path import abspath, dirname, join
from setuptools import find_packages, setup

CWD = dirname(abspath(__file__))
READ_CONTENT = lambda filename: io.open(join(CWD, filename), encoding='UTF-8').read()
REQUIREMENTS = READ_CONTENT('requirements.txt')
DESCRIPTION = '\n\n'.join(READ_CONTENT(_) for _ in [
    'README.rst',
    'CHANGES.rst',
])
setup(
    name='valutakrambod',
    version='0.0.0',
    description='pluggable (virtual) currency exchange API client library',
    long_description=DESCRIPTION,

    # See https://pypi.org/pypi?%3Aaction=list_classifiers for values
    classifiers=[
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Development Status :: 2 - Pre-Alpha',
    ],

    keywords='currency exchange bitcoin',
    author='Petter Reinholdtsen',
    author_email='pere@hungry.com',
    url='https://github.com/petterreinholdtsen/valutakrambod',
    install_requires=REQUIREMENTS,
    tests_require=[
    ],
    packages=find_packages(),
    scripts=['bin/btc-rates'],
    include_package_data=True,
    zip_safe=False)
