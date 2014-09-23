# -*- coding: utf-8-unix; -*-
from ssh_harness import PubKeyAuthSshClientTestCase


class PubKeyTestCase(PubKeyAuthSshClientTestCase):

    def test_default_setup_tear_down(self):
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
            input='ls -1 {}\nexit 0'.format(self.FIXTURE_PATH))
        self.assertEqual('', err)
        self.assertEqual('', out)
        self.assertEqual(client.returncode, 0)
