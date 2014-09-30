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
import subprocess

from ssh_harness import PubKeyAuthSshClientTestCase


class PubKeyTestCase(PubKeyAuthSshClientTestCase):

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
            'sshd_config',
            'sshd.pid',
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
            input='ls -1 {}\nexit 0'.format(self.FIXTURE_PATH).encode('utf-8'))
        out = out.strip().split('\n'.encode('utf-8'))

        self.assertEqual(err, expected_err)

        self.assertTrue(len(out) >= len(expected_out))
        # Did we get all the files we expect ?
        self.assertEqual(out[-(len(expected_out)):], expected_out)
        self.assertEqual(client.returncode, 0)


# vim: syntax=python:sws=4:sw=4:et:
