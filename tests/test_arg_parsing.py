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
from unittest import TestCase
try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

from vcs_ssh import parse_args, VERSION


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


class VcsSshArgsParserTestCase(TestCase):

    def setUp(self):
        self._rw_dirs = ['ABC', 'DEF', 'IJK']
        self._ro_dirs = ['LMN', 'OPQ', 'RST']
        self._version = 'vcs-ssh version {}.{}.{}\n'.format(*VERSION)

    def _mk_proof_list(self, attr='_rw_dirs'):
        cwd = os.getcwd()
        l = [os.path.sep.join([cwd, x]) for x in getattr(self, attr)]
        l.sort()
        return l

    def _mk_ro_proof(self):
        return self._mk_proof_list(attr='_ro_dirs')

    def _mk_rw_proof(self):
        return self._mk_proof_list()

    def test_all_implicit_rw_dirs_command_line(self):

        args = parse_args(self._rw_dirs * 1)

        self.assertEqual(args['rw_dirs'], self._mk_rw_proof())
        self.assertEqual(args['ro_dirs'], [])

    def test_all_explicit_ro_dirs_command_line(self):

        args = parse_args(['--read-only'] + self._ro_dirs * 1)

        self.assertEqual(args['rw_dirs'], [])
        self.assertEqual(args['ro_dirs'], self._mk_ro_proof())

    def test_explicit_rw_and_ro_dirs_command_line(self):

        args = parse_args(['--read-only', ]
                          + self._ro_dirs * 1
                          + ['--read-write', ]
                          + self._rw_dirs * 1)

        self.assertEqual(args['rw_dirs'], self._mk_rw_proof())
        self.assertEqual(args['ro_dirs'], self._mk_ro_proof())

    def test_explicit_and_implicit_rw_dirs_command_line(self):
        args = parse_args(self._rw_dirs[:2]
                          + ['--read-write', ]
                          + self._rw_dirs[2:])

        args['rw_dirs'].sort()
        self.assertEqual(args['rw_dirs'], self._mk_rw_proof())
        self.assertEqual(args['ro_dirs'], [])

    def test_version_option(self):
        with IOCapture(stderr=True) as ioc:
            with self.assertRaises(SystemExit):
                args = parse_args(self._rw_dirs * 1
                                  + ['--read-only', ]
                                  + self._ro_dirs * 1
                                  + ['-v', ])
        if Py3:
            self.assertEqual(ioc.get_stderr(), '')
            self.assertEqual(ioc.get_stdout(), self._version)
        else:  # Python 2 argparse writes to stderr
            self.assertEqual(ioc.get_stdout(), '')
            self.assertEqual(ioc.get_stderr(), self._version)


# vim: syntax=python:sws=4:sw=4:et:
