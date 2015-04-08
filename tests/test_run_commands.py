# -*- coding: utf-8-unix; -*-
#
#  Copyright © 2014-2015, Nicolas CANIART <nicolas@caniart.net>
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
from __future__ import unicode_literals
from unittest import TestCase
import warnings

from ssh_harness import PubKeyAuthSshClientTestCase


class RunCommandsTestCase(TestCase):

    def test_run_command_success(self):
        retval, out, err = PubKeyAuthSshClientTestCase.runCommand(['true'])

        self.assertEqual(out, '')
        self.assertEqual(err, '')
        self.assertEqual(retval, 0)

    def test_run_command_failure(self):
        retval, out, err = PubKeyAuthSshClientTestCase.runCommand(['false'])

        self.assertEqual(out, '')
        self.assertEqual(err, '')
        self.assertEqual(retval, 1)

    def test_run_command_warn_if_fail_success(self):
        with warnings.catch_warnings(record=True) as w:
            retval = PubKeyAuthSshClientTestCase.runCommandWarnIfFails(
                ['true'],
                'Success test')

        self.assertEqual(retval, 0)
        self.assertEqual(len(w), 0)

    def test_run_command_warn_if_fail_failure(self):

        with warnings.catch_warnings(record=True) as w:
            retval = PubKeyAuthSshClientTestCase.runCommandWarnIfFails(
                ['false'],
                'Failure test')

        self.assertEqual(retval, 1)
        self.assertEqual(len(w), 1)
        self.assertEqual(w[-1].category, UserWarning)


# vim: syntax=python:sws=4:sw=4:et:
