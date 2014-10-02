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
try:
    from unittest.mock import Mock, patch
except ImportError:
    from mock import Mock, patch
import os
from unittest import TestCase

from vcs_ssh import main
from .test_bzr import BZR_COMMAND


class MainTestCase(TestCase):

    def setUp(self):
        self._repo_name = 'SOMEREPO'
        self._hg_cmd = 'hg -R {} serve --stdio'.format(self._repo_name)
        self._git_cmd = 'git-upload-pack {}'.format(self._repo_name)
        self._svn_cmd = 'svnserve -t'
        self._bzr_cmd = BZR_COMMAND
        self._unparsable_cmd = \
            'git-receive-pack "unterminated-quoted-repo-name'
        self._side_effect = 'foo-bar'
        os.environ['SSH_ORIGINAL_COMMAND'] = '?'

    def tearDown(self):
        if 'SSH_ORIGINAL_COMMAND' in os.environ:
            del os.environ['SSH_ORIGINAL_COMMAND']

    def test_main_without_command(self):
        res = main()
        self.assertEqual(res, 255)

    def test_main_with_git_command_with_too_many_args(self):
        os.environ['SSH_ORIGINAL_COMMAND'] = \
            '{} extranous'.format(self._git_cmd)

        with patch('vcs_ssh.git_handle') as git_handle_mock:
            res = main()

        self.assertEqual(res, 255)
        self.assertFalse(git_handle_mock.called)

    def test_main_with_valid_git_command(self):
        os.environ['SSH_ORIGINAL_COMMAND'] = self._git_cmd

        with patch('vcs_ssh.git_handle') as git_handle_mock:
            git_handle_mock.return_value = 0
            res = main()

        self.assertEqual(res, 0)
        git_handle_mock.assert_called_once_with(
            self._git_cmd.split(),
            [],
            [])

    def test_main_with_hg_command_with_too_many_args(self):
        os.environ['SSH_ORIGINAL_COMMAND'] = \
            '{} extranous'.format(self._hg_cmd)

        with patch('vcs_ssh.hg_handle') as hg_handle_mock:
            res = main()

        self.assertEqual(res, 255)
        self.assertFalse(hg_handle_mock.called)

    def test_main_with_hg_command(self):
        os.environ['SSH_ORIGINAL_COMMAND'] = self._hg_cmd

        with patch('vcs_ssh.hg_handle') as hg_handle_mock:
            hg_handle_mock.return_value = 0
            res = main()

        self.assertEqual(res, 0)
        hg_handle_mock.assert_called_once_with(
            self._hg_cmd.split(),
            [],
            [])

    def test_main_with_hg_valid_command_but_unknown_repo(self):
        os.environ['SSH_ORIGINAL_COMMAND'] = self._hg_cmd

        with patch('vcs_ssh.rejectrepo') as rejectrepo_mock:
            with patch('vcs_ssh.hg_dispatch') as hg_dispatch_mock:
                rejectrepo_mock.return_value = 255
                res = main()

        self.assertEqual(res, 255)
        self.assertTrue(rejectrepo_mock.called)
        self.assertFalse(hg_dispatch_mock.called)

    def test_main_with_svn_command(self):
        os.environ['SSH_ORIGINAL_COMMAND'] = self._svn_cmd * 1
        process_mock = Mock()
        process_mock.returncode = self._side_effect

        with patch('vcs_ssh.subprocess.Popen') as popen_mock:
            popen_mock.return_value = process_mock
            res = main()

        popen_mock.assert_called_once_with(
            self._svn_cmd.split(),
            shell=False)
        process_mock.communicate.assert_called_once_with(*())
        self.assertEqual(res, self._side_effect)

    def test_main_with_crazy_command(self):
        os.environ['SSH_ORIGINAL_COMMAND'] = \
            self._unparsable_cmd * 1
        with patch('vcs_ssh.stderr') as stderr_mock:
            res = main()

        self.assertEqual(res, 255)
        stderr_mock.write.assert_called_once_with(
            'remote: Illegal command "{}": No closing quotation\n'
            .format(self._unparsable_cmd))

    def test_main_with_bzr_command(self):
        os.environ['SSH_ORIGINAL_COMMAND'] = \
            self._bzr_cmd * 1
        with patch('vcs_ssh.warn_no_access_control') as warn_no_ac_mock:
            with patch('vcs_ssh.bzr_handle') as bzr_handle_mock:
                bzr_handle_mock.return_value = 0xEE
                res = main()

        self.assertEqual(res, 0xEE)
        bzr_handle_mock.assert_called_once_with(
            self._bzr_cmd.split(' '), [], [])
        warn_no_ac_mock.assert_called_once_with('Bazaar')


# vim: syntax=python:sws=4:sw=4:et:
