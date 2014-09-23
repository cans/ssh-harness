# -*- coding: utf-8-unix; -*-
from __future__ import print_function
from unittest import TestCase
import os
import subprocess

try:
    from unittest.mock import Mock, patch
except:
    from mock import Mock, patch
from twisted.internet import reactor, protocol, defer
from ssh_harness import PubKeyAuthSshClientTestCase


class VcsSshIntegrationTestCase(PubKeyAuthSshClientTestCase):

    AUTHORIZED_KEY_OPTIONS = 'command={}'.format(
        os.path.join(os.getcwd(), vcs-ssh))

    def test_self(self):
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
        out, err = client.communicate(input='ls\nexit 0')
        self.assertEqual(client.returncode, 0)


# vim: syntax=python:sws=4:sw=4:et:
