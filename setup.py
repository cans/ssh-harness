# -*- coding: utf-8-unix; -*-
#
#  Copyright © 2013-2014, Nicolas CANIART <nicolas@caniart.net>
#
#  This file is part of vs-ssh.
#
#  vs-ssh is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License version 2 as
#  published by the Free Software Foundation.
#
#  vs-ssh is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with vs-ssh.  If not, see <http://www.gnu.org/licenses/>.
#
import pdb
pdb.set_trace()
try:
    from distutils import setup
except ImportError:
    from setuptools import setup

from vcs_ssh import VERSION


setup(name='vcs-ssh',
      version="{}.{}.{}".format(*VERSION),
      author='Nicolas CANIART',
      author_email='nicolas@caniart.net',
      description='VCS agnostic sharing through SSH',
      url='http://www.caniart.net/devel/vcs-ssh/',
      py_modules=[
          'vcs_ssh',
          ],
      packages=[
          'ssh_harness',
          'ssh_harness.tests',
          'tests',
          ],
      package_data={
          '': ['docs/source/*',
               'run-tests.sh', ],
          },
      scripts=['vcs-ssh', ],
      license='GNU GPLv2.0',
      )


# vim: syntax=python:sws=4:sw=4:et:
