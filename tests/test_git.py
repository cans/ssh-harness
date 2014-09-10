# -*- coding: utf-8-unix; -*-
try:
    from unittest.mock import Mock, patch
except:
    from mock import Mock, patch
import multiprocessing
import os
from unittest import TestCase

from vcs_ssh import git_handle


class GitHandleTestCase(TestCase):

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
        with patch('vcs_ssh.pipe_dispatch') as pipe_dispatch_mock:
            pipe_dispatch_mock.return_value = 0
            res = git_handle(
                self._push_command_ro.split(),
                self._rw_absdirs,
                self._ro_absdirs)
        self.assertEqual(res, 255)
        self.assertFalse(pipe_dispatch_mock.called)

    def test_git_push_to_ko_repository(self):
        with patch('vcs_ssh.pipe_dispatch') as pipe_dispatch_mock:
            pipe_dispatch_mock.return_value = 0
            res = git_handle(
                self._push_command_ko.split(),
                self._rw_absdirs,
                self._ro_absdirs)
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
        with patch('vcs_ssh.pipe_dispatch') as pipe_dispatch_mock:
            pipe_dispatch_mock.return_value = 0
            res = git_handle(
                self._pull_command_ko.split(),
                self._rw_absdirs,
                self._ro_absdirs)
        self.assertEqual(res, 255)
        self.assertFalse(pipe_dispatch_mock.called)
