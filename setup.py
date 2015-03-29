# -*- coding: utf-8-unix; -*-
#
#  Copyright © 2013-2014, Nicolas CANIART <nicolas@caniart.net>
#
#  This file is part of vcs-ssh.
#
#  vcs-ssh is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License version 2 as
#  published by the Free Software Foundation.
#
#  vcs-ssh is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with vcs-ssh.  If not, see <http://www.gnu.org/licenses/>.
#
from distutils.core import setup, Command
import glob
from vcs_ssh import VERSION

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

setup(name='vcs-ssh',
      description="VCS agnostic repository sharing through SSH",
      version=_version,
      author='Nicolas CANIART',
      author_email='nicolas@caniart.net',
      url='http://www.caniart.net/devel/vcs-ssh/',
      download_url='https://github.com/cans/vcs-ssh/tarball/{}'
          .format(_version),
      py_modules=[
          'vcs_ssh',
          ],
      # test_suite='tests',
      cmdclass={
          'test': NcaTest,
          },
      packages=[
          'ssh_harness',
          'ssh_harness.tests',
          'ssh_harness.contexts',
          ],
      data_files=[
          ('share/doc/vcs-ssh/',
           ['./run-tests.sh',
            'ssh_harness/__init__.py',
            'ssh_harness/contexts/backupeditandrestore.py',
            'ssh_harness/contexts/iocapture.py',
            'ssh_harness/contexts/inthrowabletempdir.py',
            ]
           + glob.glob('tests/test_*.py')
           ),
          ],
      scripts=['vcs-ssh', ],
      license='GNU GPLv2.0',
      classifiers=[
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
      )


# vim: syntax=python:sws=4:sw=4:et:
