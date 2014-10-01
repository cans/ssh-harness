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
    from unittest.mock import patch
except:
    from mock import patch
import os
from unittest import TestCase

from vcs_ssh import hg_handle


class HgHandleTestCase(TestCase):

    def setUp(self):
        self._cwd = os.getcwd()
        self._rw_dir = 'RWREPO'
        self._ro_dir = 'ROREPO'
        self._ko_dir = 'WRONG'
        self._ca_dir = os.path.join(self._cwd, 'CANNONICAL')
        self._rw_absdir = os.path.join(self._cwd, self._rw_dir)
        self._ro_absdir = os.path.join(self._cwd, self._ro_dir)
        self._ko_absdir = os.path.join(self._cwd, self._ko_dir)
        self._cmd = ['hg', '-R', 'serve', '--stdio', ]
        self._ro_cmd_suffix = [
            '--config',
            'hooks.prechangegroup.hg-ssh=python:vcs_ssh.rejectpush',
            '--config',
            'hooks.prepushkey.hg-ssh=python:vcs_ssh.rejectpush',
            ]
        for action in ('push', 'pull', ):
            for mode in ('ro', 'rw', 'ko', 'ca', ):
                cmd_attr = '_{}_command_{}'.format(action, mode)
                dir_attr = '_{}_dir'.format(mode)
                setattr(self, cmd_attr, self._cmd * 1)
                if 'ro' == mode:
                    setattr(self, cmd_attr, (self._cmd + self._ro_cmd_suffix))
                else:
                    setattr(self, cmd_attr, self._cmd * 1)
                getattr(self, cmd_attr).insert(2, getattr(self, dir_attr))

    def test_hg_push_to_rw_repository(self):
        with patch('vcs_ssh.hg_dispatch') as hg_dispatch_mock:
            hg_dispatch_mock.return_value = 0
            res = hg_handle(
                self._push_command_rw * 1,
                [self._rw_absdir, ],
                [self._ro_absdir, ],)

        # update path to its canonicalized form
        self._push_command_rw[2] = os.path.join(self._cwd, self._rw_dir)
        self.assertEqual(res, 0)
        hg_dispatch_mock.assert_called_once_with(
            self._push_command_rw[1:])

    def test_hg_push_to_ko_repository(self):
        with patch('vcs_ssh.rejectrepo') as rejectrepo_mock:
            rejectrepo_mock.return_value = 255
            res = hg_handle(
                self._push_command_ko * 1,
                [self._rw_absdir, ],
                [self._ro_absdir, ],)

        # update path to its canonicalized form
        self.assertEqual(res, 255)
        rejectrepo_mock.assert_called_once_with(
            os.path.join(self._cwd, self._ko_dir))

    def test_hg_push_to_ca_repository(self):
        with patch('vcs_ssh.hg_dispatch') as hg_dispatch_mock:
            hg_dispatch_mock.return_value = 0
            res = hg_handle(
                self._push_command_ca * 1,
                [self._ca_dir, ],
                [self._ro_absdir, ],)

        self.assertEqual(res, 0)
        hg_dispatch_mock.assert_called_once_with(
            self._push_command_ca[1:])

    def test_hg_push_to_ro_repository(self):
        with patch('vcs_ssh.hg_dispatch') as hg_dispatch_mock:
            hg_dispatch_mock.return_value = 0
            res = hg_handle(
                self._push_command_ro * 1,
                [self._rw_absdir, ],
                [self._ro_absdir, ],)

        # update path to its canonicalized form
        self._push_command_ro[2] = os.path.join(self._cwd, self._ro_dir)
        self.assertEqual(res, 0)
        hg_dispatch_mock.assert_called_once_with(
            self._push_command_ro[1:])


# vim: syntax=python:sws=4:sw=4:et:
