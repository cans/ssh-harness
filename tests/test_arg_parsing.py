# -*- coding: utf-8-unix; -*-
#
#  Copyright © 2014, Nicolas CANIART <nicolas@caniart.net>
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
import os
import sys
from unittest import TestCase

from ssh_harness.contexts import IOCapture
from vcs_ssh import parse_args, VERSION

Py34 = True
if (3, 4, 0, ) > sys.version_info:
    Py34 = False


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
                parse_args(self._rw_dirs * 1
                           + ['--read-only', ]
                           + self._ro_dirs * 1
                           + ['-v', ])
        if Py34:  # Assuming version write on stdout since 3.4
            self.assertEqual(ioc.get_stderr(), '')
            self.assertEqual(ioc.get_stdout(), self._version)
        else:
            # Python 2 argparse writes to stderr.
            # Python 3.3.5 on travis-ci does too.
            self.assertEqual(ioc.get_stdout(), '')
            self.assertEqual(ioc.get_stderr(), self._version)


# vim: syntax=python:sws=4:sw=4:et:
