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
    from unittest.mock import patch
except:
    from mock import patch
import os
import re
from unittest import TestCase, skipIf

from ssh_harness.contexts import IOCapture
from vcs_ssh import git_handle


__all__ = [
    'GitHandleTestCase',
    'GIT_BINARY',
    ]


GIT_BINARY = '/usr/bin/git'
VCS_SSH_MESSAGE = 'remote: \x1b[1;41mYou only have read only access to this ' \
    'repository\x1b[0m: you cannot push anything into it !\n'


@skipIf(not (os.path.isfile(GIT_BINARY) and os.access(GIT_BINARY, os.X_OK)),
        'The Git VCS is not installed on this system.')
class GitHandleTestCase(TestCase):

    _ILLEGAL_REPOSITORY_RE = re.compile('Illegal repository "/.*/WRONG"\n',
                                        re.S)

    def setUp(self):
        self._cwd = os.getcwd()
        self._rw_dirs = ['RWREPO', ]
        self._ro_dirs = ['ROREPO', ]
        self._ko_dir = 'WRONG'
        self._rw_absdirs = [os.path.join(self._cwd, x) for x in self._rw_dirs]
        self._ro_absdirs = [os.path.join(self._cwd, x) for x in self._ro_dirs]
        self._ko_absdirs = os.path.join(self._cwd, self._ko_dir)
        self._push_cmd = 'git-receive-pack'
        self._pull_cmd = 'git-upload-pack'
        self._push_command_ro = 'git-receive-pack ROREPO'
        self._push_command_rw = 'git-receive-pack RWREPO'
        self._push_command_ko = 'git-receive-pack WRONG'
        self._pull_command_ro = 'git-upload-pack ROREPO'
        self._pull_command_rw = 'git-upload-pack RWREPO'
        self._pull_command_ko = 'git-upload-pack WRONG'

    def tearDown(self):
        if 'SSH_ORIG_COMMAND' in os.environ:
            del os.environ['SSH_ORIG_COMMAND']

    def test_git_push_to_rw_repository(self):
        with patch('vcs_ssh.pipe_dispatch') as pipe_dispatch_mock:
            pipe_dispatch_mock.return_value = 0
            res = git_handle(
                self._push_command_rw.split(),
                self._rw_absdirs,
                self._ro_absdirs)
        self.assertEqual(res, 0)
        pipe_dispatch_mock.assert_called_once_with([
            self._push_cmd, ] + self._rw_absdirs)

    def test_git_push_to_ro_repository(self):
        with IOCapture(stdout=False, stderr=True, module='vcs_ssh') as ioc:
            with patch('vcs_ssh.pipe_dispatch') as pipe_dispatch_mock:
                pipe_dispatch_mock.return_value = 0
                res = git_handle(
                    self._push_command_ro.split(),
                    self._rw_absdirs,
                    self._ro_absdirs)

        self.assertEqual(
            ioc.get_stderr(),
            VCS_SSH_MESSAGE)
        self.assertEqual(res, 255)
        self.assertFalse(pipe_dispatch_mock.called)

    def test_git_push_to_ko_repository(self):
        with IOCapture(stdout=False, stderr=True, module='vcs_ssh') as ioc:
            with patch('vcs_ssh.pipe_dispatch') as pipe_dispatch_mock:
                pipe_dispatch_mock.return_value = 0
                res = git_handle(
                    self._push_command_ko.split(),
                    self._rw_absdirs,
                    self._ro_absdirs)
        self.assertRegexpMatches(
            ioc.get_stderr(), self._ILLEGAL_REPOSITORY_RE)
        self.assertEqual(res, 255)
        self.assertFalse(pipe_dispatch_mock.called)

    def test_git_pull_from_rw_repository(self):
        with patch('vcs_ssh.pipe_dispatch') as pipe_dispatch_mock:
            pipe_dispatch_mock.return_value = 0
            res = git_handle(
                self._pull_command_rw.split(),
                self._rw_absdirs,
                self._ro_absdirs)
        self.assertEqual(res, 0)
        pipe_dispatch_mock.assert_called_once_with([
            self._pull_cmd, ] + self._rw_absdirs)

    def test_git_pull_from_ro_repository(self):
        with patch('vcs_ssh.pipe_dispatch') as pipe_dispatch_mock:
            pipe_dispatch_mock.return_value = 0
            res = git_handle(
                self._pull_command_ro.split(),
                self._rw_absdirs,
                self._ro_absdirs)
        self.assertEqual(res, 0)
        pipe_dispatch_mock.assert_called_once_with([
            self._pull_cmd, ] + self._ro_absdirs)

    def test_git_pull_from_ko_repository(self):
        with IOCapture(stdout=False, stderr=True, module='vcs_ssh') as ioc:
            with patch('vcs_ssh.pipe_dispatch') as pipe_dispatch_mock:
                pipe_dispatch_mock.return_value = 0
                res = git_handle(
                    self._pull_command_ko.split(),
                    self._rw_absdirs,
                    self._ro_absdirs)

        self.assertRegexpMatches(
            ioc.get_stderr(), self._ILLEGAL_REPOSITORY_RE)
        self.assertEqual(res, 255)
        self.assertFalse(pipe_dispatch_mock.called)


# vim: syntax=python:sws=4:sw=4:et:
