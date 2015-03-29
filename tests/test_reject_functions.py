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
try:
    from unittest.mock import Mock, patch
except:
    from mock import Mock, patch
from unittest import TestCase

from vcs_ssh import rejectpush, rejectcommand, have_required_command


class RejectFunctionsTestCase(TestCase):

    def test_rejectpush_without_argument(self):
        with patch('vcs_ssh.stderr') as stderrmock:
            res = rejectpush()

        self.assertEqual(res, 255)
        stderrmock.write.assert_called_once_with(
            "remote: \033[1;41mYou only have read only access to this "
            "repository\033[0m: you cannot push anything into it !\n")

    def test_rejectpush_with_ui_argument(self):
        ui = Mock()
        with patch('vcs_ssh.stderr') as stderrmock:
            res = rejectpush(ui)

        self.assertEqual(res, 255)
        ui.warn.assert_called_once_with('Permission denied\n')
        stderrmock.write.assert_called_once_with(
            "\033[1;41mYou only have read only access to this "
            "repository\033[0m: you cannot push anything into it !\n")

    def test_rejectcommand_without_extra(self):
        with patch('vcs_ssh.stderr') as stderrmock:
            res = rejectcommand('foo')

        self.assertEqual(res, 255)
        stderrmock.write.assert_called_once_with(
            'remote: Illegal command "foo"\n')

    def test_rejectcommand_with_extra(self):
        with patch('vcs_ssh.stderr') as stderrmock:
            res = rejectcommand('foo', extra='bar')

        self.assertEqual(res, 255)
        stderrmock.write.assert_called_once_with(
            'remote: Illegal command "foo": bar\n')


@have_required_command
def fake_handler(command, ro_dirs, rw_dirs):
    return 0


class HaveRequiredCommandTestCase(TestCase):

    def test_have_required_command_with_good_command(self):
        res = fake_handler(['true', ], [], [])

        self.assertEqual(0, res)

    def test_have_required_command_with_bad_command(self):
        with patch('vcs_ssh.stderr') as stderrmock:
            res = fake_handler(['command_that_does_not_exist', ],
                               [],
                               [])

        self.assertEqual(254, res)
        stderrmock.write.assert_called_once_with(
            'The command required to fulfill your request has not '
            'been found on this system.')


# vim: syntax=python:sws=4:sw=4:et:
