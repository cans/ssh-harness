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
from __future__ import print_function
import os
from stat import S_IRUSR, S_IXUSR
from unittest import TestCase
import warnings

from ssh_harness.contexts import InThrowableTempDir

MODULE_PATH = os.path.abspath(os.path.dirname(__file__))
TEMP_PATH = os.path.join(MODULE_PATH, 'tmp', 'inthrowabletempdir_tests_dir')
"""Base location for any temporary file created by the test-suite.

.. note::

   The location <MODULE_PATH>/tmp/ is our *standard* location for writing
   files on disk during test runs. Hence that directory may have already
   been created by another test-case, when this one starts running.

   Thus *intentionally* use a sub-directory of our standard location
   because we want to force at least one instance of the
   :class:`InThrowableTempDir` class to have to create that sub-directory
   at least once.
"""


class InThrowableTempDirTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        if os.path.exists(TEMP_PATH):
            os.rmdir(TEMP_PATH)  # See note on TEMP_PATH

        cls.SUITE_CWD = os.getcwd()
        cls.RO_DIR = os.path.join(os.path.dirname(TEMP_PATH), 'ro_dir')
        os.makedirs(cls.RO_DIR)
        os.chmod(cls.RO_DIR, S_IRUSR | S_IXUSR)

    @classmethod
    def tearDownClass(cls):
        os.rmdir(cls.RO_DIR)
        os.rmdir(TEMP_PATH)

    def setUp(self):
        self.CASE_CWD = os.getcwd()
        self.assertEqual(self.CASE_CWD, self.__class__.SUITE_CWD)

    def test_in_throwable_temp_dir_success(self):

        with InThrowableTempDir(dir=TEMP_PATH) as ittd:
            basename = os.path.basename(ittd.path)

            self.assertTrue(ittd.path.startswith(TEMP_PATH))
            self.assertTrue(basename.startswith('throw-'))
            self.assertNotEqual(ittd.path, self.CASE_CWD)
            self.assertEqual(ittd.old_path, self.CASE_CWD)

        self.assertEqual(ittd.old_path, self.CASE_CWD)
        self.assertFalse(os.path.exists(ittd.path))

    def test_in_throwable_temp_dir_applies_suffix(self):
        suffix = '-test-suffix'
        with InThrowableTempDir(dir=TEMP_PATH, suffix=suffix) as ittd:

            self.assertTrue(ittd.path.endswith(suffix))
            self.assertTrue(ittd.path.startswith(TEMP_PATH))

        self.assertEqual(ittd.old_path, self.CASE_CWD)
        self.assertFalse(os.path.exists(ittd.path))

    def test_in_throwable_temp_dir_applies_prefix(self):
        prefix = 'test-prefix-'
        with InThrowableTempDir(dir=TEMP_PATH, prefix=prefix) as ittd:
            basename = os.path.basename(ittd.path)

            self.assertTrue(basename.startswith(prefix))
            self.assertTrue(ittd.path.startswith(TEMP_PATH))

        self.assertEqual(ittd.old_path, self.CASE_CWD)
        self.assertFalse(os.path.exists(ittd.path))

    def test_in_throwable_temp_dir_cleanup_after_exception(self):
        with self.assertRaises(Exception):
            with InThrowableTempDir(dir=TEMP_PATH) as ittd:
                raise Exception("Whatever")

        self.assertEqual(ittd.old_path, self.CASE_CWD)
        self.assertFalse(os.path.exists(ittd.path))

    def test_in_throwable_temp_dir_failure(self):
        with self.assertRaises(OSError):
            with InThrowableTempDir(dir=self.__class__.RO_DIR):
                pass

    def test_in_throwable_temp_dir_recursion(self):
        with warnings.catch_warnings(record=True) as w:
            with InThrowableTempDir(dir=TEMP_PATH) as ittd:
                with ittd:
                    pass

        self.assertEqual(len(w), 1)
        self.assertEqual(w[-1].category, UserWarning)
        self.assertFalse(os.path.exists(ittd.path))
