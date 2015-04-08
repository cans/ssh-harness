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
from __future__ import unicode_literals
import os
from unittest import TestCase
try:
    from unittest.mock import patch
except ImportError:
    from mock import patch
import sys

from .mod4tests import (write_to_stderr, write_to_stdout,
                        write_to_sys_stderr, write_to_sys_stdout, )

from ssh_harness.contexts import IOCapture


class IOCaptureTestCase(TestCase):

    MODULE_NAME = 'ssh_harness.tests.mod4tests'

    def setUp(self):
        self.args = ('message,', )
        self.msg1, self.msg2, self.msg3, self.msg4 = [
            'message{}\n'.format(x) for x in range(1, 5)
            ]

    def test_no_capture_stderr(self):
        with patch('sys.stderr') as mockstderr:
            write_to_sys_stderr(*self.args)

        mockstderr.write.assert_called_once(self.args)

    def test_no_capture_stdout(self):
        with patch('sys.stdout') as mockstdout:
            write_to_sys_stdout(*self.args)

        mockstdout.write.assert_called_once(self.args)

    def test_capture_all_stdout(self):
        with IOCapture(stdout=True) as io:
            write_to_sys_stdout(self.msg1)
            sys.stdout.write(self.msg2)

        write_to_stdout(self.msg3)
        sys.stdout.write(self.msg4)

        self.assertEqual(io.get_stdout(), self.msg1 + self.msg2)
        # Message "message3" should be seen on the console.

    def test_capture_all_stderr(self):
        with IOCapture(stdout=False, stderr=True) as io:
            write_to_sys_stderr(self.msg1)
            sys.stderr.write(self.msg2)

        write_to_stderr(self.msg3)
        sys.stderr.write(self.msg4)

        self.assertEqual(io.get_stderr(), self.msg1 + self.msg2)
        # Message "message3" should be seen on the console.

    def test_capture_stdout_only_in_module_mod4tests(self):
        with IOCapture(stdout=True,
                       module=self.MODULE_NAME,
                       out_attr='stdout') as io:
            write_to_stdout(self.msg1)
            sys.stdout.write(self.msg2)

        write_to_stdout(self.msg3)
        sys.stdout.write(self.msg4)

        self.assertEqual(io.get_stdout(), self.msg1)
        # Message "message3" should be seen on the console.

    def test_capture_stderr_only_in_module_mod4tests(self):
        with IOCapture(stdout=False,
                       stderr=True,
                       module=self.MODULE_NAME,
                       err_attr='stderr') as io:
            write_to_stderr(self.msg1)
            sys.stderr.write(self.msg2)

        write_to_stderr(self.msg3)
        sys.stderr.write(self.msg4)

        self.assertEqual(io.get_stderr(), self.msg1)
        # Message "message3" should be seen on the console.

    def test_capture_fails_if_module_not_loaded(self):
        with self.assertRaisesRegexp(RuntimeError,
                                     "Module `.*' is not yet loaded!"):
            with IOCapture(module='a_module_that_is_expected_to_not_exists'):
                pass

    def test_capture_to_file(self):
        """Ensures redirection to file creates a file indeed.

        .. warning::

           This test may not be portable (see :class:`tempfile.TemporaryFile`)
           As a matter of fact it is not protable on Linux across Python
           versions.
        """
        filename = None
        with IOCapture(module=self.MODULE_NAME, stdout=True, file=True) as io:
            write_to_stdout(self.msg1)
            filename = io.stdout.name
            self.assertTrue(os.path.exists(filename)
                            or (filename.startswith('<')
                                and filename.endswith('>')))

        self.assertEqual(io.get_stdout(), self.msg1)

    def test_get_output_of_uncaptured_io_returns_empty_string(self):
        with IOCapture(stderr=False, stdout=False) as io:
            pass

        self.assertEqual(io.get_stderr(), '')
        self.assertEqual(io.get_stdout(), '')

    def test_call_to_get_stdout_are_forbidden_within_the_context(self):
        """Ensure calls to the :method:`iocapture.IOCapture.get_stdout` method
        are not allowed while *in* the context.

        .. warning::

           This test may not be portable (see :class:`tempfile.TemporaryFile`)
        """
        with self.assertRaisesRegexp(
                RuntimeError,
                "Calling `.*' while in the context is not allowed!"):
            with IOCapture(stderr=False,
                           stdout=True,
                           module=self.MODULE_NAME) as io:
                io.get_stdout()

    def test_call_to_get_stderr_are_forbidden_within_the_context(self):
        """Ensure calls to the :method:`iocapture.IOCapture.get_stderr` method
        are not allowed while *in* the context.

        .. warning::

           This test may not be portable (see :class:`tempfile.TemporaryFile`)
        """
        with self.assertRaisesRegexp(
                RuntimeError,
                "Calling `.*' while in the context is not allowed!"):
            with IOCapture(stderr=True,
                           stdout=False,
                           module=self.MODULE_NAME) as io:
                io.get_stderr()


# vim: syntax=python:sws=4:sw=4:et:
