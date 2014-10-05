# -*- coding: utf-8-unix; -*-
#
#  Copyright © 2014, Nicolas CANIART <nicolas@caniart.net>
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
from io import StringIO, BytesIO
import os
import sys
from tempfile import TemporaryFile


__all__ = [
    'Py3',
    'IOCapture',
    ]

Py3 = True
MemoryIO = StringIO
if (3, 0, 0, ) > sys.version_info:
    Py3 = False
    MemoryIO = BytesIO


class IOCapture(object):

    def __init__(self, stdout=True, stderr=False, file=False):
        self._olderr = self.stderr = sys.stderr
        self._oldout = self.stdout = sys.stdout

        if stderr:
            self._redirect_stderr(file=file)
        if stdout:
            self._redirect_stdout(file=file)

    def __enter__(self):
        sys.stderr = self.stderr
        sys.stdout = self.stdout
        return self

    def __exit__(self, exc, exc_type, tb):
        if exc is None:
            sys.stderr = self._olderr
            sys.stdout = self._oldout
            return True
        else:
            raise

    def _redirect_output(self, name, file=False):
        if file is True:
            f = TemporaryFile(mode='w+b', prefix='iocpt-')
        else:
            f = MemoryIO()
        setattr(self, name, f)

    def _redirect_stderr(self, file=False):
        self._redirect_output('stderr', file=file)

    def _redirect_stdout(self, file=False):
        self._redirect_output('stdout', file=file)

    def _get_output(self, name):
        attr = getattr(self, name)
        if attr == getattr(sys, name):
            raise Exception()

        if isinstance(attr, MemoryIO):
            return attr.getvalue()
        else:
            attr.seek(0, os.SEEK_SET)
            return attr.read()

    def get_stderr(self):
        return self._get_output('stderr')

    def get_stdout(self):
        return self._get_output('stdout')


# vim: syntax=python:sws=4:sw=4:et:
