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
from __future__ import print_function
from unittest import TestCase


from ssh_harness import BaseSshClientTestCase as SshHarness


class SshHarnessHelpersTestCase(TestCase):

    def setUp(self):
        self._unknown_program = './do-not-exists'

    def tearDown(self):
        SshHarness._errors = dict()

    def test_check_auxiliary_program_success(self):
        self.assertTrue(SshHarness._check_auxiliary_program('/bin/false'))

    def test_check_auxiliary_program_failure_without_error(self):
        self.assertFalse(
            SshHarness._check_auxiliary_program(self._unknown_program,
                                                error=False))
        self.assertNotIn(self._unknown_program, SshHarness._errors)

    def test_check_auxiliary_program_failure_with_error(self):
        self.assertFalse(
            SshHarness._check_auxiliary_program(self._unknown_program))
        self.assertIn(self._unknown_program, SshHarness._errors)
