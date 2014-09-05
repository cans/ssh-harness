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
        self._push_command_ro = 'git-receive-pack ROREPO'
        self._push_command_rw = 'git-receive-pack RWREPO'
        self._pull_command_ro = 'git-upload-pack ROREPO'
        self._pull_command_rw = 'git-upload-pack RWREPO'

    def test_git_push_to_rw_repository(self):
        with patch('vcs_ssh.pipe_dispatch') as pipe_dispatch_mock:
            pipe_dispatch_mock.return_value = 0
            res = git_handle(self._push_command_rw.split(),
                             [os.path.join(self._cwd, x) for x in self._rw_dirs],
                             [os.path.join(self._cwd, x) for x in self._ro_dirs])
            self.assertEqual(0, res)
