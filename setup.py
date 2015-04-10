# -*- coding: utf-8-unix; -*-
#
#  Copyright © 2013-2014, Nicolas CANIART <nicolas@caniart.net>
#
#  This file is part of ssh-harness.
#
#  ssh-harness is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License version 2 as
#  published by the Free Software Foundation.
#
#  ssh-harness is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with ssh-harness.  If not, see <http://www.gnu.org/licenses/>.
#
from distutils.core import setup, Command
from ssh_harness import VERSION

_version = "{}.{}.{}".format(*VERSION)


class NcaTest(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        import subprocess
        import sys
        errno = subprocess.call([
            sys.executable, '-m', 'unittest', 'tests.__main__'])
        raise SystemExit(errno)

with opent('./README.rst', 'r') as README:
    SETUP_CONFIG = {
        'name': 'ssh-harness',
        'description': "A Test Harness for SSH dependant applications",
        'long_description': README.read(),
        'version': _version,
        'author': 'Nicolas CANIART',
        'author_email': 'nicolas@caniart.net',
        'url': 'http://www.caniart.net/devel/ssh-harness/',
        'download_url': 'https://github.com/cans/ssh-harness/tarball/{}'
            .format(_version),
        # 'test_suite': 'tests',
        'cmdclass': {
            'test': NcaTest,
            },
        'packages': [
            'ssh_harness',
            'ssh_harness.contexts',
            ],
        'license': 'GNU GPLv2.0',
        'classifiers': [
            'Development Status :: 5 - Production/Stable',
            'Environment :: Console',
            'Intended Audience :: End Users/Desktop',
            'Intended Audience :: Developers',
            'Intended Audience :: System Administrators',
            'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
            'Operating System :: POSIX',
            'Operating System :: MacOS :: MacOS X',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3.3',
            'Programming Language :: Python :: 3.4',
            'Topic :: Software Development :: Version Control',
            ],
       }


if '__main__' == __name__:
    setup(**SETUP_CONFIG)

# vim: syntax=python:sws=4:sw=4:et:
