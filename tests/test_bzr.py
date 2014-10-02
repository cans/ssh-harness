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

from vcs_ssh import bzr_handle

__all__ = [
    'BzrHandleTestCase',
    'BZR_COMMAND',
    ]

BZR_COMMAND = 'bzr serve --inet --directory=/ --allow-writes'


class BzrHandleTestCase(TestCase):

    def setUp(self):
        global BZR_COMMAND
        self._bzr_cmd = BZR_COMMAND.split(' ')

    def test_bzr_handle(self):
        with patch('vcs_ssh.pipe_dispatch') as pipe_dispatch_mock:
            pipe_dispatch_mock.return_value = 0xEE
            res = bzr_handle(self._bzr_cmd * 1, [], [],)

        self.assertEqual(res, 0xEE)
        # update path to its canonicalized form
        pipe_dispatch_mock.assert_called_once_with(self._bzr_cmd)


# vim: syntax=python:sws=4:sw=4:et:
