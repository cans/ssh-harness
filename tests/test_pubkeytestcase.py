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
import subprocess

from ssh_harness import PubKeyAuthSshClientTestCase


class PubKeyTestCase(PubKeyAuthSshClientTestCase):

    _context_name = 'test_pubkey'

    def test_default_setup_tear_down(self):
        files = [
            'authorized_keys',
            'host_ssh_dsa_key',
            'host_ssh_dsa_key.pub',
            'host_ssh_ecdsa_key',
            'host_ssh_ecdsa_key.pub',
            'host_ssh_rsa_key',
            'host_ssh_rsa_key.pub',
            'id_rsa',
            'id_rsa.pub',
            'sshd.pid',
            'sshd_config',
            ]

        # Because Py2 and Py3 suprocess modules produce incompatible
        # output data types (str and bytes resp.).
        # We basically convert every literals in the code to bytes, thus
        #  - since in python 2 str == bytes and subprocess methods produce str
        #  - and since in python 3 subprocess methods produce bytes
        # then all the literal we compare to program output end-up in
        # equivalent/compatible data types. Hurrah !
        expected_out = [x.encode('utf-8') for x in files]
        expected_err = ''.encode('utf-8')

        client = subprocess.Popen([
            'ssh',
            '-T',
            '-i',
            self.USER_RSA_KEY_PATH,
            '-p', str(self.PORT),
            self.BIND_ADDRESS,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        out, err = client.communicate(
            input='ls -1 {}\nexit 0'.format(self.SSH_BASEDIR).encode('utf-8'))

        self._debug(out, err, client)

        out = out.strip().split('\n'.encode('utf-8'))
        # Sorting should not be necessary as LS(1) should sort for us, yet we
        # have seen occurrences where the last two items were not in the right
        # order (!) Is it a problem with the slicing applied below ?
        # Better safe san sorry as they say ...
        out.sort()

        self.assertEqual(err, expected_err)

        self.assertTrue(len(out) >= len(expected_out))
        # Did we get all the files we expect ?
        self.assertEqual(out[-(len(expected_out)):], expected_out)
        self.assertEqual(client.returncode, 0)


# vim: syntax=python:sws=4:sw=4:et:
