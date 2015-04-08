# -*- coding: utf-8-unix; -*-
#
# Copyright © 2014-2015, Nicolas CANIART <nicolas@caniart.net>
#
from __future__ import print_function
from unittest import TestCase, skipIf
try:
    from unittest.mock import patch
except ImportError:
    from mock import patch
import stat
import os
from sys import version_info as VERSION_INFO, platform

from ssh_harness import BackupEditAndRestore
from ssh_harness.contexts.backupeditandrestore import _move

_Py3 = (3, ) <= VERSION_INFO
_Py34 = (3, 4) <= VERSION_INFO


def fake_rename(patcher):
    patcher.stop()
    raise OSError()


class BackupEditAndRestoreTestCase(TestCase):

    MODULE_PATH = os.path.abspath(os.path.dirname(__file__))
    # FIXTURE_PATH = os.path.sep.join([MODULE_PATH, 'fixtures', ])
    TEMP_PATH = os.path.sep.join([MODULE_PATH, 'tmp', 'backupeditandrestore'])

    _context_name = 'test_backupandedit'

    @classmethod
    def setUpClass(cls):
        # if not os.path.isdir(cls.FIXTURE_PATH):
        #     os.makedirs(cls.FIXTURE_PATH, stat.S_IRWXU)
        if not os.path.isdir(cls.TEMP_PATH):
            os.makedirs(cls.TEMP_PATH, stat.S_IRWXU)

    @classmethod
    def tearDownClass(cls):
        if os.path.isdir(cls.TEMP_PATH):
            os.rmdir(cls.TEMP_PATH)

    def setUp(self):
        self._file_content = 'Some content for the test file'
        self._suffix = 'foo-bar'
        self._new_suffix = 'new-foo-bar'
        self._existing_path = os.path.join(self.TEMP_PATH, 'dummy')
        self._existing_new_path = '.'.join([self._existing_path,
                                            self._new_suffix])
        self._existing_backup_path = '.'.join([self._existing_path,
                                               self._suffix])
        self._inexistant_path = os.path.join(self.TEMP_PATH, 'sloppy')
        self._inexistant_new_path = '.'.join([self._inexistant_path,
                                              self._new_suffix])
        self._inexistant_backup_path = '.'.join([self._inexistant_path,
                                                 self._suffix])

        self._f = None  # To reference the context created in a testcase.
        # Create a fresh new test file
        with open(self._existing_path, 'w') as f:
            f.write(self._file_content)
        if os.path.isfile(self._inexistant_path):
            os.unlink(self._inexistant_path)

    def tearDown(self):
        if self._f is not None:
            self._f.restore()

        # Remove the test files
        for i in ('existing', 'inexistant'):
            for j in ('_new', '_backup', ''):

                to_delete = getattr(self, '_{}{}_path'.format(i, j))
                if os.path.isfile(to_delete):
                    os.unlink(to_delete)
        if BackupEditAndRestore._contexts[self._context_name]:
            print("\033[1;31mBAD TEST DID NOT PICK-UP AFTER ITSELF:\033[0m {}"
                  .format(BackupEditAndRestore._contexts[self._context_name]))

    def test_attributes(self):
        self._f = BackupEditAndRestore(self._context_name,
                                       self._existing_path,
                                       suffix=self._suffix)

        self.assertEqual(self._f._new_suffix, self._new_suffix)
        self.assertEqual(self._f._new_path, self._existing_new_path)
        self.assertEqual(self._f._path, self._existing_path)
        self.assertEqual(self._f._backup_path, self._existing_backup_path)
        self.assertFalse(self._f._have_backup)
        self.assertFalse(self._f._restored)
        self._f.__exit__(None, None, None)

    # -- Checking that the file to edit is being copied if mode is
    #    a, r, U (which implies r) an w+.

    # This is the full test -- it needs to be split in bits
    def test_with_mode_a(self):
        with BackupEditAndRestore(self._context_name,
                                  self._existing_path, 'a',
                                  suffix=self._suffix) as f:
            # Is the original file still present
            self.assertTrue(os.path.isfile(self._existing_path))
            # Has a backup copy been created
            self.assertTrue(os.path.isfile(self._existing_backup_path))
            # Has a copy for edition been created ?
            self.assertTrue(os.path.isfile(self._existing_new_path))

            with open(self._existing_new_path, 'r') as chk:
                self.assertEqual(chk.read(), self._file_content)

            # append a '.' at the end of self._file_content
            f.write('.')

        # Left the context manager, the edited file must have been
        # renamed as self._existing_path.

        # self._new_path is no more
        self.assertFalse(os.path.isfile(self._existing_new_path))
        # self._existing_path still exists
        self.assertTrue(os.path.isfile(self._existing_path))
        # as well as the backup file
        self.assertTrue(os.path.isfile(self._existing_backup_path))

        # check that self._existing_path does contain the edited content
        with open(self._existing_path, 'r') as chk:
            self.assertEqual(chk.read(),
                             '{}.'.format(self._file_content))

        # check that the back-up file is not altered
        with open(self._existing_backup_path, 'r') as chk:
            self.assertEqual(chk.read(),
                             self._file_content)

        f.restore()
        self.assertFalse(os.path.isfile(self._existing_backup_path))
        self.assertEqual(os.path.isfile(self._existing_path), f._have_backup)

    def test_with_mode_a_but_inexistant_file(self):
        with BackupEditAndRestore(self._context_name,
                                  self._inexistant_path, 'w+',
                                  suffix=self._suffix) as f:
            self.assertEqual(f._new_path, self._inexistant_new_path)
            # Check that the inexistant file still isn't present
            self.assertFalse(os.path.isfile(self._inexistant_path))
            # check that there is no back-up (we had nothing to backup)
            self.assertFalse(os.path.isfile(self._inexistant_backup_path))
            # Has a copy for edition been created ?
            self.assertTrue(os.path.isfile(self._inexistant_new_path))

            # The file is brand new and cannot be a copy
            with open(self._inexistant_new_path, 'r') as chk:
                self.assertEqual(chk.read(), '')

            f.write(self._file_content)

        # check that the backup file still does not exist
        self.assertFalse(os.path.isfile(self._inexistant_backup_path))
        # check that the edition file does not exist anymore
        self.assertFalse(os.path.isfile(self._inexistant_new_path))
        # but now the file exists and can be worked with
        self.assertTrue(os.path.isfile(self._inexistant_path))

        # check that self._existing_path does contain the edited content
        with open(self._inexistant_path, 'r') as chk:
            self.assertEqual(chk.read(),
                             '{}'.format(self._file_content))

        f.restore()

        # self._new_path is no more
        self.assertFalse(os.path.isfile(self._inexistant_new_path))
        # self._existing_path still exists
        self.assertFalse(os.path.isfile(self._inexistant_path))
        # as well as the backup file
        self.assertFalse(os.path.isfile(self._inexistant_backup_path))

    # This is the full test -- it needs to be split in bits
    def test_with_mode_w(self):
        with BackupEditAndRestore(self._context_name,
                                  self._existing_path, 'w',
                                  suffix=self._suffix) as f:
            # Is the original file still present
            self.assertTrue(os.path.isfile(self._existing_path))
            # Has a backup copy been created
            self.assertTrue(os.path.isfile(self._existing_backup_path))
            # Has a copy for edition been created ?
            self.assertTrue(os.path.isfile(self._existing_new_path))

            # Mode 'w' truncates the file anyways
            with open(self._existing_new_path, 'r') as chk:
                self.assertEqual(chk.read(), '')

            # append a '.' at the end of self._file_content
            f.write('.')

        # Left the context manager, the edited file must have been
        # renamed as self._existing_path.

        # self._new_path is no more
        self.assertFalse(os.path.isfile(self._existing_new_path))
        # self._existing_path still exists
        self.assertTrue(os.path.isfile(self._existing_path))
        # as well as the backup file
        self.assertTrue(os.path.isfile(self._existing_backup_path))

        # check that self._existing_path does contain the edited content
        with open(self._existing_path, 'r') as chk:
            self.assertEqual(chk.read(), '.')

        # check that the back-up file is not altered
        with open(self._existing_backup_path, 'r') as chk:
            self.assertEqual(chk.read(),
                             self._file_content)

        f.restore()
        self.assertFalse(os.path.isfile(self._existing_backup_path))
        self.assertEqual(os.path.isfile(self._existing_path), f._have_backup)

    def test_inexistant_file_when_mode_is_w(self):
        with BackupEditAndRestore(self._context_name,
                                  self._inexistant_path,
                                  'w+',
                                  suffix=self._suffix) as f:
            self.assertEqual(f._new_path, self._inexistant_new_path)
            # Check that the inexistant file still isn't present
            self.assertFalse(os.path.isfile(self._inexistant_path))
            # check that there is no back-up (we had nothing to backup)
            self.assertFalse(os.path.isfile(self._inexistant_backup_path))
            # Has a copy for edition been created ?
            self.assertTrue(os.path.isfile(self._inexistant_new_path))

            # The file is brand new and cannot be a copy, thus it should be
            # empty.
            with open(self._inexistant_new_path, 'r') as chk:
                self.assertEqual(chk.read(), '')

            f.write(self._file_content)

        # check that the backup file still does not exist
        self.assertFalse(os.path.isfile(self._inexistant_backup_path))
        # check that the edition file does not exist anymore
        self.assertFalse(os.path.isfile(self._inexistant_new_path))
        # but now the file exists and can be worked with
        self.assertTrue(os.path.isfile(self._inexistant_path))

        # check that self._existing_path does contain the edited content
        with open(self._inexistant_path, 'r') as chk:
            self.assertEqual(chk.read(),
                             '{}'.format(self._file_content))

        f.restore()

        # self._new_path is no more
        self.assertFalse(os.path.isfile(self._inexistant_new_path))
        # self._existing_path still exists
        self.assertFalse(os.path.isfile(self._inexistant_path))
        # as well as the backup file
        self.assertFalse(os.path.isfile(self._inexistant_backup_path))

    def test_file_is_copied_when_mode_is_a(self):
        with BackupEditAndRestore(self._context_name,
                                  self._existing_path,
                                  mode='a',
                                  suffix=self._suffix) as self._f:
            # Is the original file still present
            self.assertTrue(os.path.isfile(self._existing_path))
            # Has a backup copy been created
            self.assertTrue(os.path.isfile(self._existing_backup_path))
            # Has a copy for edition been created ?
            self.assertTrue(os.path.isfile(self._existing_new_path))

            # file content is left untouched.
            with open(self._existing_path, 'r') as chk:
                self.assertEqual(chk.read(), self._file_content)
            # Backup file is the same as the original one
            with open(self._existing_backup_path, 'r') as chk:
                self.assertEqual(chk.read(), self._file_content)
            # and so is the edition file
            with open(self._existing_new_path, 'r') as chk:
                self.assertEqual(chk.read(), self._file_content)

    def test_file_is_copied_when_mode_is_rp(self):
        with BackupEditAndRestore(self._context_name,
                                  self._existing_path,
                                  mode='r+t',
                                  suffix=self._suffix) as self._f:
            # Is the original file still present
            self.assertTrue(os.path.isfile(self._existing_path))
            # Has a backup copy been created
            self.assertTrue(os.path.isfile(self._existing_backup_path))
            # Has a copy for edition been created ?
            self.assertTrue(os.path.isfile(self._existing_new_path))

            # Copied file content is the same as the original
            self.assertEqual(self._f.read(), self._file_content)

    def test_edition_file_is_properly_removed_at_exit_with_mode_rp(self):
        with BackupEditAndRestore(self._context_name,
                                  self._existing_path,
                                  'r+t',
                                  suffix=self._suffix) as self._f:
            pass
        # check that the backup file still does not exist
        self.assertTrue(os.path.isfile(self._existing_backup_path))
        # check that the edition file does not exist anymore
        self.assertFalse(os.path.isfile(self._existing_new_path))
        # but now the file exists and can be worked with
        self.assertTrue(os.path.isfile(self._existing_path))

    def test_edition_file_is_properly_removed_at_exit_with_mode_a(self):
        with BackupEditAndRestore(self._context_name,
                                  self._existing_path,
                                  'a',
                                  suffix=self._suffix) as self._f:
            pass
        # check that the backup file still does not exist
        self.assertTrue(os.path.isfile(self._existing_backup_path))
        # check that the edition file does not exist anymore
        self.assertFalse(os.path.isfile(self._existing_new_path))
        # but now the file exists and can be worked with
        self.assertTrue(os.path.isfile(self._existing_path))

    def test_file_modified_when_mode_is_rp(self):
        with BackupEditAndRestore(self._context_name,
                                  self._existing_path,
                                  'r+t',
                                  suffix=self._suffix) as self._f:
            self._f.write('.')

        with open(self._existing_path, 'r') as chk:
            self.assertEqual(chk.read(),
                             '.{}'.format(self._file_content[1:]))

    def test_file_modified_when_mode_is_a(self):
        with BackupEditAndRestore(self._context_name,
                                  self._existing_path,
                                  'a',
                                  suffix=self._suffix) as self._f:
            self._f.write('.')

        with open(self._existing_path, 'r') as chk:
            self.assertEqual(chk.read(),
                             '{}.'.format(self._file_content))

    def test_file_modified_when_mode_is_w(self):
        with BackupEditAndRestore(self._context_name,
                                  self._existing_path,
                                  'w',
                                  suffix=self._suffix) as self._f:
            self._f.write('.')

        with open(self._existing_path, 'r') as chk:
            self.assertEqual(chk.read(),
                             '.'.format(self._file_content[1:]))

    def test_file_restored_when_mode_is_rp(self):
        with BackupEditAndRestore(self._context_name,
                                  self._existing_path,
                                  'r+t',
                                  suffix=self._suffix) as f:
            pass

        f.restore()

        # self._new_path is no more
        self.assertFalse(os.path.isfile(self._existing_new_path))
        # as well as the backup file
        self.assertFalse(os.path.isfile(self._existing_backup_path))
        # self._existing_path still exists
        self.assertTrue(os.path.isfile(self._existing_path))

        with open(self._existing_path, 'r') as chk:
            self.assertEqual(chk.read(), self._file_content)

    def test_file_restored_when_mode_is_a(self):
        with BackupEditAndRestore(self._context_name,
                                  self._existing_path,
                                  'r+t',
                                  suffix=self._suffix) as f:
            pass

        f.restore()

        # self._new_path is no more
        self.assertFalse(os.path.isfile(self._existing_new_path))
        # as well as the backup file
        self.assertFalse(os.path.isfile(self._existing_backup_path))
        # self._existing_path still exists
        self.assertTrue(os.path.isfile(self._existing_path))

        with open(self._existing_path, 'r') as chk:
            self.assertEqual(chk.read(), self._file_content)

    def test_file_restored_when_mode_is_w(self):
        with BackupEditAndRestore(self._context_name,
                                  self._existing_path,
                                  'r+t',
                                  suffix=self._suffix) as f:
            pass

        f.restore()

        # self._new_path is no more
        self.assertFalse(os.path.isfile(self._existing_new_path))
        # as well as the backup file
        self.assertFalse(os.path.isfile(self._existing_backup_path))
        # self._existing_path still exists
        self.assertTrue(os.path.isfile(self._existing_path))

        with open(self._existing_path, 'r') as chk:
            self.assertEqual(chk.read(),
                             self._file_content)

    def test_inexistant_file_fails_when_mode_is_r(self):
        with self.assertRaises(ValueError):
            with BackupEditAndRestore(self._context_name,
                                      self._inexistant_path,
                                      'r',
                                      suffix=self._suffix) as self._f:
                pass

        # Well nothing happened so no file should exist.
        self.assertFalse(os.path.isfile(self._inexistant_new_path))
        self.assertFalse(os.path.isfile(self._inexistant_backup_path))
        self.assertFalse(os.path.isfile(self._inexistant_path))

    def test_inexistant_file_fails_when_mode_is_rp(self):
        with self.assertRaises(IOError):
            with BackupEditAndRestore(self._context_name,
                                      self._inexistant_path,
                                      'r+',
                                      suffix=self._suffix) as self._f:
                pass

        # Well nothing happened so no file should exist.
        self.assertFalse(os.path.isfile(self._inexistant_new_path))
        self.assertFalse(os.path.isfile(self._inexistant_backup_path))
        self.assertFalse(os.path.isfile(self._inexistant_path))

    @skipIf(_Py34, "From 3.4 on, Python no longer supports the U mode")
    def test_inexistant_file_fails_when_mode_is_U(self):
        with self.assertRaises(ValueError):
            with BackupEditAndRestore(self._context_name,
                                      self._inexistant_path,
                                      'U',
                                      suffix=self._suffix) as self._f:
                pass

        # Well nothing happened so no file should exist.
        self.assertFalse(os.path.isfile(self._inexistant_new_path))
        self.assertFalse(os.path.isfile(self._inexistant_backup_path))
        self.assertFalse(os.path.isfile(self._inexistant_path))

    @skipIf(_Py34, "From 3.4 on, Python no longer supports the U+ mode")
    def test_inexistant_file_fails_when_mode_is_Up(self):
        with self.assertRaises(IOError):
            with BackupEditAndRestore(self._context_name,
                                      self._inexistant_path,
                                      'U+',
                                      suffix=self._suffix) as self._f:
                pass

        # Well nothing happened so no file should exist.
        self.assertFalse(os.path.isfile(self._inexistant_new_path))
        self.assertFalse(os.path.isfile(self._inexistant_backup_path))
        self.assertFalse(os.path.isfile(self._inexistant_path))

    def test_file_fails_when_mode_is_r(self):
        with self.assertRaises(ValueError):
            with BackupEditAndRestore(self._context_name,
                                      self._existing_path,
                                      'r',
                                      suffix=self._suffix) as self._f:
                pass

        # Making sure no junk is left behind
        self.assertFalse(os.path.isfile(self._existing_new_path))
        # as well as the backup file
        self.assertFalse(os.path.isfile(self._existing_backup_path))
        # self._existing_path still exists
        self.assertTrue(os.path.isfile(self._existing_path))

    def test_file_fails_when_mode_is_U(self):
        with self.assertRaises(ValueError):
            with BackupEditAndRestore(self._context_name,
                                      self._existing_path,
                                      'U',
                                      suffix=self._suffix) as self._f:
                pass

        # Making sure no junk is left behind
        self.assertFalse(os.path.isfile(self._existing_new_path))
        # as well as the backup file
        self.assertFalse(os.path.isfile(self._existing_backup_path))
        # self._existing_path still exists
        self.assertTrue(os.path.isfile(self._existing_path))

    def test_recursive_use_is_forbiden(self):
        with self.assertRaises(RuntimeError):
            with BackupEditAndRestore(self._context_name,
                                      self._existing_path,
                                      'a') as self._f:
                with self._f:
                    pass

    def test_reuse_is_forbidden(self):
        with BackupEditAndRestore(self._context_name,
                                  self._existing_path,
                                  'a') as self._f:
            pass

        with self.assertRaises(RuntimeError):
            with self._f:
                pass

    def test_cannot_backup_file_twice(self):
        self.assertTrue(os.path.isfile(self._existing_path))
        with BackupEditAndRestore(self._context_name,
                                  self._existing_path,
                                  'a',
                                  suffix=self._suffix) as self._f:
            pass

        self.assertTrue(os.path.isfile(self._existing_path))
        self.assertTrue(os.path.isfile(self._existing_backup_path))
        self.assertFalse(os.path.isfile(self._existing_new_path))

        with self.assertRaisesRegexp(RuntimeError,
                                     'File already backed up!'):
            with BackupEditAndRestore(self._context_name,
                                      self._existing_path,
                                      'a'):
                pass

        # Despite having been nasty before, we want the file to still
        # be properly safe-guarded.
        self.assertTrue(os.path.isfile(self._existing_path))
        self.assertTrue(os.path.isfile(self._existing_backup_path))
        self.assertFalse(os.path.isfile(self._existing_new_path))

    @skipIf('Windows' != platform, 'Test only relevant on Windows OS')
    def test_move_auxiliary_win32(self):
        pass

    @skipIf('Windows' == platform, 'Test only relevant on non-Windows OS')
    def test_move_auxiliary_other(self):
        some_path = os.path.join(self.TEMP_PATH, 'some_path')
        with open(some_path, 'w') as f:
            f.write("some content")

        other_path = os.path.join(self.TEMP_PATH, 'other_path')
        other_content = "other content"
        with open(other_path, 'w') as f:
            f.write(other_content)

        patcher = patch('ssh_harness.contexts.backupeditandrestore.os.rename')
        mock_rename = patcher.start()
        mock_rename.side_effect = lambda src, dst: fake_rename(patcher)

        _move(other_path, some_path)

        with open(some_path, 'r') as f:
            content = f.read()

        self.assertFalse(os.path.exists(other_path))
        self.assertTrue(os.path.exists(some_path))
        self.assertEqual(content, other_content)

        os.unlink(some_path)

    def test_clear(self):
        with BackupEditAndRestore(self._context_name,
                                  self._existing_path,
                                  'r+t',
                                  suffix=self._suffix) as self._f:
            pass

        self.assertTrue(os.path.isfile(self._existing_path))
        self.assertTrue(os.path.isfile(self._existing_backup_path))
        self.assertFalse(os.path.isfile(self._existing_new_path))

        BackupEditAndRestore.clear(self._context_name,
                                   self._existing_path)

        self.assertTrue(os.path.isfile(self._existing_path))
        self.assertFalse(os.path.isfile(self._existing_backup_path))
        self.assertFalse(os.path.isfile(self._existing_new_path))

    def test_clear_context(self):
        with BackupEditAndRestore(self._context_name,
                                  self._existing_path,
                                  'w+',
                                  suffix=self._suffix):
            pass
        with BackupEditAndRestore(self._context_name,
                                  self._inexistant_path,
                                  'w+',
                                  suffix=self._suffix):
            pass

        self.assertTrue(os.path.isfile(self._existing_path))
        self.assertTrue(os.path.isfile(self._existing_backup_path))
        self.assertFalse(os.path.isfile(self._existing_new_path))
        self.assertTrue(os.path.isfile(self._inexistant_path))
        self.assertFalse(os.path.isfile(self._inexistant_backup_path))
        self.assertFalse(os.path.isfile(self._inexistant_new_path))

        BackupEditAndRestore.clear_context(self._context_name)

        self.assertTrue(os.path.isfile(self._existing_path))
        self.assertFalse(os.path.isfile(self._existing_backup_path))
        self.assertFalse(os.path.isfile(self._existing_new_path))
        self.assertFalse(os.path.isfile(self._inexistant_path))
        self.assertFalse(os.path.isfile(self._inexistant_backup_path))
        self.assertFalse(os.path.isfile(self._inexistant_new_path))

    def test_clear_context_on_non_existant_context(self):
        self.assertNotIn('some non-existant context',
                         BackupEditAndRestore._contexts)

        BackupEditAndRestore.clear_context('some non-existant context')

    def test_unregistering_file_that_had_never_been_registered_fails(self):
        with self.assertRaisesRegexp(RuntimeError,
                                     'No backup registered for the given path:'
                                     ' .*'):
            BackupEditAndRestore._unregister(self._context_name,
                                             self._existing_path,
                                             None)

    def test_unregistering_file_with_wrong_instance_fails(self):
        with BackupEditAndRestore(self._context_name,
                                  self._existing_path,
                                  'w+') as self._f:
            pass

        with self.assertRaisesRegexp(RuntimeError,
                                     'Registered and passed instances .*'):
            BackupEditAndRestore._unregister(self._context_name,
                                             self._existing_path,
                                             None)

# vim: syntax=python:sws=4:sw=4:et:
