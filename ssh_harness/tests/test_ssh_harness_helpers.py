# -*- coding: utf-8-unix; -*-
#
#  Copyright © 2015, Nicolas CANIART <nicolas@caniart.net>
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
from __future__ import print_function, unicode_literals
import os
import stat
import sys
import tempfile
import logging
from unittest import TestCase, SkipTest
try:
    from unittest.mock import patch, call, Mock
except ImportError:
    from mock import Mock, patch, call

MODULE_PATH = os.path.abspath(os.path.dirname(__file__))
FIXTURE_PATH = os.path.sep.join([MODULE_PATH, 'fixtures', ])
TEMP_PATH = os.path.sep.join([MODULE_PATH, 'tmp', ])
if not os.path.isdir(TEMP_PATH):
    os.mkdir(TEMP_PATH)

sys.path.append(os.path.join(FIXTURE_PATH, 'bin'))
import fake_ssh_keyscan

from ssh_harness.contexts import BackupEditAndRestore
from ssh_harness import BaseSshClientTestCase, _PermissionError


class SshHarness(BaseSshClientTestCase):
    """Dummy subclass

    We use inheritance to insulate the base-class from changes made here
    that could be potentially harmful for other test-suites."""

    # _errors = {}  # so it is not shared with the BaseSshClient class
    USE_AUTH_METHOD = BaseSshClientTestCase.AUTH_METHOD_PUBKEY


class SshHarnessNoop(SshHarness):

    @classmethod
    def noop(cls, *args, **kwargs):
        pass

    _preconditions = noop
    _generate_sshd_config = noop
    _generate_private_keys = noop
    _generate_keys = noop
    _generate_authzd_keys_file = noop
    _generate_environment_file = noop
    _start_sshd = noop
    _kill_sshd = noop
    _update_user_known_hosts = noop


class SshHarnessHelpersTestCase(TestCase):

    def setUp(self):
        self._unknown_program = './do-not-exists'
        self._known_program = '/bin/false'

    def tearDown(self):
        for k in list(SshHarness._errors.keys()):
            del SshHarness._errors[k]

    def test_check_auxiliary_program_success(self):
        self.assertTrue(
            SshHarness._check_auxiliary_program(self._known_program))

    def test_check_auxiliary_program_failure_without_error(self):
        self.assertFalse(
            SshHarness._check_auxiliary_program(self._unknown_program,
                                                error=False))
        self.assertNotIn(self._unknown_program,
                         SshHarness._errors)

    def test_check_auxiliary_program_failure_with_error(self):
        self.assertFalse(
            SshHarness._check_auxiliary_program(self._unknown_program,
                                                error=True))
        self.assertIn(self._unknown_program,
                      SshHarness._errors)

    def test_check_auxiliary_program_success_with_error(self):
        self.assertTrue(
            SshHarness._check_auxiliary_program(self._known_program,
                                                error=True))
        self.assertNotIn(self._known_program,
                         SshHarness._errors)


class SshHarnessCheckDirTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        if not os.path.isdir(TEMP_PATH):
            os.makedirs(TEMP_PATH, stat.S_IRWXU)
        else:
            res = os.stat(TEMP_PATH)
            if(stat.S_IRWXU > res.st_mode
               and not os.chmod(TEMP_PATH, mode=stat.S_IRWXU)):
                raise SkipTest("Permissions on directory `{}' aren't right"
                               " and I failed in attempting to fix them."
                               .format(TEMP_PATH))

    def setUp(self):
        self._temp_sub_dir = tempfile.mkdtemp(dir=TEMP_PATH,
                                              prefix='',
                                              suffix='')
        os.chmod(self._temp_sub_dir, stat.S_IRUSR | stat.S_IXUSR)

    def tearDown(self):
        os.rmdir(self._temp_sub_dir)
        for k in list(SshHarness._errors.keys()):
            del SshHarness._errors[k]  # Reset class error

    def test_check_dir_success_with_default_mode(self):
        self.assertTrue(SshHarness._check_dir(TEMP_PATH, stat.S_IRWXU))

    def test_check_dir_failure_with_default_mode(self):
        self.assertFalse(SshHarness._check_dir(self._temp_sub_dir,
                                               stat.S_IRWXU))

        error = list(SshHarness._errors.values())[0]
        self.assertRegexpMatches(error,
                                 'Insufficient permissions on directory.*')

    def test_check_dir_failure_on_directory_creation(self):
        path = os.path.join(self._temp_sub_dir,
                            'directory_I_should_not_be_able_to_create')

        self.assertFalse(SshHarness._check_dir(path))
        error = list(SshHarness._errors.keys())[0]
        self.assertRegexpMatches(
            error,
            '_skip\(exc=\[Errno 13\] Permission denied:.*\)')


class SshHarnessPreconditions(SshHarness):
    _check_auxiliary_program = Mock()
    _check_dir = Mock()
    _skip = Mock()


class SshHarnessPreconditionsTestCase(TestCase):

    def reset_mocks(self):
        # Re-create mocks 'cause reset_mock() does not reset return_value or
        # side_effect attributes and return_value is a bitch to reset (cannot
        # del, set to None, or whatever I can think of)
        SshHarnessPreconditions._check_auxiliary_program = Mock()
        SshHarnessPreconditions._check_dir = Mock()
        SshHarnessPreconditions._skip.reset_mock()

    def setUp(self):
        self.addCleanup(self.reset_mocks)

    def test__preconditions_calls__skip_if_some_preconditions_is_not_met(self):
        SshHarnessPreconditions._check_auxiliary_program.return_value = False
        SshHarnessPreconditions._check_dir.return_value = False

        SshHarnessPreconditions._preconditions()

        self.assertEqual(
            SshHarnessPreconditions._check_auxiliary_program.call_count, 4)
        self.assertEqual(
            SshHarnessPreconditions._check_dir.call_count, 4)
        SshHarnessPreconditions._skip.assert_called_once()

    def test__preconditions_fails_as_soon_as_one__check_dir_test_fails(self):
        SshHarnessPreconditions._check_auxiliary_program.return_value = False
        SshHarnessPreconditions._check_dir.side_effect = [
            bool(x) for x in range(0, 4)]

        SshHarnessPreconditions._preconditions()

        self.assertEqual(
            SshHarnessPreconditions._check_auxiliary_program.call_count, 4)
        self.assertEqual(
            SshHarnessPreconditions._check_dir.call_count, 4)
        SshHarnessPreconditions._skip.assert_called_once()

    def test__preconditions_fails_when_one__chk_aux_prog_test_fails(self):
        SshHarnessPreconditions._check_auxiliary_program.side_effect = [
            bool(x) for x in range(0, 4)]
        SshHarnessPreconditions._check_dir.return_value = False

        SshHarnessPreconditions._preconditions()

        self.assertEqual(
            SshHarnessPreconditions._check_auxiliary_program.call_count, 4)
        self.assertEqual(
            SshHarnessPreconditions._check_dir.call_count, 4)
        SshHarnessPreconditions._skip.assert_called_once()


# -----------------------------------------------------------------------------


class SshHarnessSkip(SshHarnessNoop):

    UPDATE_SSH_CONFIG = False
    _errors = {}


class SshHarnessSkipTestCase(TestCase):

    def tearDown(self):
        for k in list(SshHarness._errors.keys()):
            del SshHarness._errors[k]
        self.assertTrue(
            SshHarness._errors is BaseSshClientTestCase._errors)

    def test__skip_raises_skip_exception(self):
        SshHarness._errors['fictional_func1()'] = 'Some message'
        SshHarness._errors['fictional_func2()'] = 'Some other message'
        with self.assertRaisesRegexp(
                SkipTest,
                "One or more errors occurred while trying to setup the "
                "functional test-suite.*"):
            SshHarness._skip()


class SshHarnessSetUpClassTestCase(TestCase):

    def tearDown(self):
        for k in list(SshHarnessSkip._errors.keys()):
            del SshHarnessSkip._errors[k]
        self.assertTrue(
            SshHarness._errors is BaseSshClientTestCase._errors)
        if 'SSH_HARNESS_DEBUG' in os.environ:
            del os.environ['SSH_HARNESS_DEBUG']

    def test_setupclass_calls_skip(self):
        SshHarnessSkip._errors['fictional_func1()'] = 'Some message'
        SshHarnessSkip._errors['fictional_func2()'] = 'Some other message'
        with self.assertRaisesRegexp(
                SkipTest,
                "One or more errors occurred while trying to setup the "
                "functional test-suite.*"):
            SshHarnessSkip.setUpClass()

    def test_loglevel_set_if_environment_var_defined(self):
        os.environ['SSH_HARNESS_DEBUG'] = '1'
        with patch('ssh_harness.logger') as mock_logger:
            SshHarnessSkip.setUpClass()

        mock_logger.setLevel.assert_called_once_with(logging.DEBUG, )


# -----------------------------------------------------------------------------


class SshHarnessUpdateUserKnownHosts(SshHarness):

    UPDATE_SSH_CONFIG = False
    USE_AUTH_METHOD = (True, True, )
    SSH_KEYSCAN_BIN = os.path.join(FIXTURE_PATH, 'bin', 'fake_ssh_keyscan.py')
    _context_name = 'ssh_harness_update_user_known_hosts'
    # This path must be kept in sync with the one found in the
    # ``fake_ssh_keyscan`` script.
    _KNOWN_HOSTS_PATH = os.path.join(TEMP_PATH, 'user_known_hosts')
    _errors = dict()


class UpdateUserKnownHostTestCase(TestCase):

    def tearDown(self):
        for var in ['FAKE_SSH_KEYSCAN_QUIET', 'FAKE_SSH_KEYSCAN_FAIL']:
            if var in os.environ:
                del os.environ[var]
        BackupEditAndRestore.clear_context(
            SshHarnessUpdateUserKnownHosts._context_name)
        SshHarnessUpdateUserKnownHosts._errors = dict()

    def test__update_user_known_hosts_fails_if_no_output(self):
        os.environ['FAKE_SSH_KEYSCAN_QUIET'] = '1'
        SshHarnessUpdateUserKnownHosts._update_user_known_hosts()

        self.assertIn('_update_user_known_hosts',
                      SshHarnessUpdateUserKnownHosts._errors)
        self.assertRegexpMatches(
            SshHarnessUpdateUserKnownHosts._errors['_update_user_known_hosts'],
            'ssh-keyscan failed with status 0.*')

    def test__update_user_known_hosts_fails_if_error(self):
        os.environ['FAKE_SSH_KEYSCAN_FAIL'] = '1'
        SshHarnessUpdateUserKnownHosts._update_user_known_hosts()
        self.assertRegexpMatches(
            SshHarnessUpdateUserKnownHosts._errors['_update_user_known_hosts'],
            'ssh-keyscan failed with status 1.*')

    def test__update_user_known_hosts_success(self):
        SshHarnessUpdateUserKnownHosts._update_user_known_hosts()

        self.assertTrue(
            os.path.exists(SshHarnessUpdateUserKnownHosts._KNOWN_HOSTS_PATH))
        with open(SshHarnessUpdateUserKnownHosts._KNOWN_HOSTS_PATH, 'r') as f:
            content = f.read()
        self.assertEqual(content,
                         ''.join([fake_ssh_keyscan.FILE_CONTENT + '\n', ] * 2))


# -----------------------------------------------------------------------------


class SshHarnessUpdateSshConfig(SshHarness):

    UPDATE_SSH_CONFIG = False
    USE_AUTH_METHOD = (True, True, )
    _SSH_CONFIG_PATH = os.path.join(TEMP_PATH, 'ssh-config')
    _context_name = 'ssh_harness_update_ssh_config'


class UpdateSshConfigTestCase(TestCase):

    def setUp(self):
        self._args = SshHarnessUpdateSshConfig._gather_config()
        with open(SshHarnessUpdateSshConfig._SSH_CONFIG_PATH, 'w+'):
            pass

    def tearDown(self):
        if os.path.isfile(SshHarnessUpdateSshConfig._SSH_CONFIG_PATH):
            os.unlink(SshHarnessUpdateSshConfig._SSH_CONFIG_PATH)

    def test_update_ssh_config_when_disabled(self):
        SshHarnessUpdateSshConfig._update_ssh_config(self._args)

    def test_update_ssh_config_when_enabled(self):
        SshHarnessUpdateSshConfig.UPDATE_SSH_CONFIG = True
        SshHarnessUpdateSshConfig._update_ssh_config(self._args)

        self.assertTrue(
            os.path.isfile(SshHarnessUpdateSshConfig._SSH_CONFIG_PATH))

        with open(SshHarnessUpdateSshConfig._SSH_CONFIG_PATH, 'r') as f:
            self._args.update({'blanks': ' ' * 8})
            line_count = 0
            for line in f:
                self.assertRegexpMatches(line,
                                         '^(Host {ssh_config_host_name}'
                                         '|{blanks}HostName {address}'
                                         '|{blanks}Port {port}'
                                         '|{blanks}IdentityFile {identity})?$'
                                         .format(**self._args))
                line_count += 1

        self.assertEqual(5, line_count)
        BackupEditAndRestore.clear_context(
            SshHarnessUpdateSshConfig._context_name)


# -----------------------------------------------------------------------------


class SshHarnessEnv(SshHarness):

    SSH_ENVIRONMENT_FILE = True
    SSH_ENVIRONMENT = {
        'VARIABLE1': 'VALUE1',
        'VARIABLE2': 'VALUE2',
        }
    _SSH_ENVIRONMENT_PATH = os.path.join(TEMP_PATH,
                                         'environment')
    _context_name = 'ssh_harness_environment'


class SshHarnessEnvironmentTestCase(TestCase):

    def test_create_environment_file(self):
        SshHarnessEnv._generate_environment_file()

        expected_content = '{}\n'.format(
            '\n'.join(['{}={}'.format(k, v)
                       for k, v in SshHarnessEnv.SSH_ENVIRONMENT.items()]))
        self.assertTrue(
            os.path.isfile(SshHarnessEnv._SSH_ENVIRONMENT_PATH))
        with open(SshHarnessEnv._SSH_ENVIRONMENT_PATH, 'r') as f:
            self.assertEqual(f.read(), expected_content)

        BackupEditAndRestore.clear_context(SshHarnessEnv._context_name)

    def test_create_environment_file_when_disabled(self):
        SshHarnessEnv.SSH_ENVIRONMENT_FILE = False
        SshHarnessEnv._generate_environment_file()

        self.assertFalse(
            os.path.isfile(SshHarnessEnv._SSH_ENVIRONMENT_PATH))


# -----------------------------------------------------------------------------


class SshHarnessAuthzdKeys(SshHarness):

    AUTHORIZED_KEY_OPTIONS = 'from="127.0.0.1"'
    AUTHORIZED_KEYS_PATH = os.path.join(TEMP_PATH, 'autorized_keys')
    SSH_ENVIRONMENT = {
        'VARIABLE1': 'VALUE1',
        'VARIABLE2': 'VALUE2',
        }
    USER_RSA_KEY_PATH = os.path.join(TEMP_PATH, 'id_rsa')


class SshHarnessAuthzdKeysTestCase(TestCase):

    def setUp(self):
        self._pubkey_data = 'Base64 Key Data'
        self._pubkey = '{}.pub'.format(SshHarnessAuthzdKeys.USER_RSA_KEY_PATH)
        self._options = SshHarnessAuthzdKeys.AUTHORIZED_KEY_OPTIONS
        self._env = SshHarnessAuthzdKeys.SSH_ENVIRONMENT
        with open(self._pubkey, 'w+') as f:
            f.write(self._pubkey_data)

    def tearDown(self):
        os.unlink(self._pubkey)
        os.unlink(SshHarnessAuthzdKeys.AUTHORIZED_KEYS_PATH)
        SshHarnessAuthzdKeys.AUTHORIZED_KEY_OPTIONS = self._options
        SshHarnessAuthzdKeys.SSH_ENVIRONMENT = self._env

    def test__generate_authzd_keys_file_with_options_and_env(self):
        expected_content = "{},{} {}\n".format(
            SshHarnessAuthzdKeys.AUTHORIZED_KEY_OPTIONS,
            ','.join([
                'environment="{}={}"'.format(k, v)
                for k, v in SshHarnessAuthzdKeys.SSH_ENVIRONMENT.items()]),
            self._pubkey_data)

        SshHarnessAuthzdKeys._generate_authzd_keys_file()

        self.assertTrue(
            os.path.isfile(SshHarnessAuthzdKeys.AUTHORIZED_KEYS_PATH))

        with open(SshHarnessAuthzdKeys.AUTHORIZED_KEYS_PATH, 'r') as f:
            content = f.read()
        self.assertEqual(content, expected_content)

    def test__generate_authz_keys_file_with_env_without_options(self):
        SshHarnessAuthzdKeys.AUTHORIZED_KEY_OPTIONS = None
        expected_content = "{} {}\n".format(
            ','.join([
                'environment="{}={}"'.format(k, v)
                for k, v in SshHarnessAuthzdKeys.SSH_ENVIRONMENT.items()]),
            self._pubkey_data)

        SshHarnessAuthzdKeys._generate_authzd_keys_file()

        self.assertTrue(
            os.path.isfile(SshHarnessAuthzdKeys.AUTHORIZED_KEYS_PATH))

        with open(SshHarnessAuthzdKeys.AUTHORIZED_KEYS_PATH, 'r') as f:
            content = f.read()
        self.assertEqual(content, expected_content)

    def test__generate_authz_keys_file_with_options_without_env(self):
        SshHarnessAuthzdKeys.AUTHORIZED_KEY_OPTIONS = None
        expected_content = "{} {}\n".format(
            ','.join([
                'environment="{}={}"'.format(k, v)
                for k, v in SshHarnessAuthzdKeys.SSH_ENVIRONMENT.items()]),
            self._pubkey_data)

        SshHarnessAuthzdKeys._generate_authzd_keys_file()

        self.assertTrue(
            os.path.isfile(SshHarnessAuthzdKeys.AUTHORIZED_KEYS_PATH))

        with open(SshHarnessAuthzdKeys.AUTHORIZED_KEYS_PATH, 'r') as f:
            content = f.read()
        self.assertEqual(content, expected_content)

    def test__generate_authz_keys_file_without_env_or_options(self):
        SshHarnessAuthzdKeys.AUTHORIZED_KEY_OPTIONS = None
        SshHarnessAuthzdKeys.SSH_ENVIRONMENT = None
        expected_content = '{}\n'.format(self._pubkey_data)

        SshHarnessAuthzdKeys._generate_authzd_keys_file()

        self.assertTrue(
            os.path.isfile(SshHarnessAuthzdKeys.AUTHORIZED_KEYS_PATH))

        with open(SshHarnessAuthzdKeys.AUTHORIZED_KEYS_PATH, 'r') as f:
            content = f.read()
        self.assertEqual(content, expected_content)


# -----------------------------------------------------------------------------


class SshHarnessGenerateKeys(SshHarness):

    _FILES = SshHarness._FILES.copy()
    # USE_AUTH_METHOD = SshHarness.AUTH_METHOD_PUBKEY
    FIXTURE_PATH = os.path.join(
        os.path.abspath(os.getcwd()), 'tests', 'fixtures', 'sshd')


class SshHarnessGenerateKeysTestCase(TestCase):

    def setUp(self):
        # To prevent damaging the class attribute
        self._FILES = SshHarnessGenerateKeys._FILES.copy()
        SshHarnessGenerateKeys._gather_config()
        # We just need to generate one.
        del SshHarnessGenerateKeys._FILES['USER_RSA_KEY']
        del SshHarnessGenerateKeys._FILES['HOST_RSA_KEY']
        del SshHarnessGenerateKeys._FILES['HOST_ECDSA_KEY']
        self.pubkey = '{}.pub'.format(SshHarnessGenerateKeys.HOST_DSA_KEY_PATH)

    def tearDown(self):
        SshHarnessGenerateKeys._FILES = self._FILES
        SshHarnessGenerateKeys.SSH_KEYGEN_BIN = SshHarness.SSH_KEYGEN_BIN
        if os.path.isfile(self.pubkey):
            os.unlink(self.pubkey)
        if os.path.isfile(SshHarnessGenerateKeys.HOST_DSA_KEY_PATH):
            os.unlink(SshHarnessGenerateKeys.HOST_DSA_KEY_PATH)

    def test_generate_keys_success(self):
        SshHarnessGenerateKeys._generate_keys()

        self.assertTrue(
            os.path.isfile(SshHarnessGenerateKeys.HOST_DSA_KEY_PATH))
        self.assertTrue(
            os.path.isfile(self.pubkey))
        with open(self.pubkey, 'r') as f:
            content = f.read()
        self.assertRegexpMatches(content,
                                 '^ssh-dss AAAA.*\*DO NOT DISSEMINATE\*$')

    def test_generate_keys_failure(self):
        SshHarnessGenerateKeys.SSH_KEYGEN_BIN = '/bin/false'
        with self.assertRaises(RuntimeError):
            SshHarnessGenerateKeys._generate_keys()

        self.assertFalse(
            os.path.isfile(SshHarnessGenerateKeys.HOST_DSA_KEY_PATH))
        self.assertFalse(
            os.path.isfile(self.pubkey))

    def test_generate_keys_removes_existing_keys(self):
        with open(SshHarnessGenerateKeys.HOST_DSA_KEY_PATH, 'w') as f:
            f.write('Some data that does not look like a SSH key')
            SshHarnessGenerateKeys._generate_keys()

        self.assertTrue(
            os.path.isfile(SshHarnessGenerateKeys.HOST_DSA_KEY_PATH))
        self.assertTrue(
            os.path.isfile(self.pubkey))
        with open(self.pubkey, 'r') as f:
            content = f.read()
        self.assertRegexpMatches(content,
                                 '^ssh-dss AAAA.*\*DO NOT DISSEMINATE\*$')


# -----------------------------------------------------------------------------


class SshHarnessSshd(SshHarness):

    # Copied because we will mess with it in the test-suite below.
    _FILES = SshHarness._FILES.copy()
    # Override some defaults.
    SSHD_BIN = '/bin/echo'
    USE_AUTH_METHOD = (True, True, )  # Necessary


class SshHarnessSshdTestCase(TestCase):

    def setUp(self):
        # We remove the user RSA key file default because we don't want it to
        # be actually generated.
        self._args = SshHarnessSshd._gather_config()
        del SshHarnessSshd._FILES['USER_RSA_KEY']
        SshHarnessSshd._generate_keys()

        SshHarnessSshd._generate_sshd_config(self._args)

    def tearDown(self):
        SshHarnessSshd._FILES['USER_RSA_KEY'] = 'id_rsa'
        SshHarnessSshd.SSHD_BIN = '/bin/echo'
        SshHarnessSshd.tearDownClass()
        for k in list(SshHarnessSshd._errors.keys()):
            del SshHarness._errors[k]

    def test_start_sshd_failure(self):
        with self.assertRaises(SkipTest):
            SshHarnessSshd._start_sshd()

        self.assertIn(SshHarnessSshd.SSHD_BIN, SshHarnessSshd._errors)
        self.assertIs(SshHarnessSshd._SSHD, None)

    def test_start_sshd_success(self):
        # Use the real SSHD
        SshHarnessSshd.SSHD_BIN = SshHarness.SSHD_BIN

        SshHarnessSshd._start_sshd()

        self.assertNotIn(SshHarnessSshd.SSHD_BIN, SshHarnessSshd._errors)
        self.assertIsNot(SshHarnessSshd._SSHD, None)


# -----------------------------------------------------------------------------


class DeleteFileTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.RO_TEMP_SUB_DIR = tempfile.mkdtemp(dir=TEMP_PATH,
                                               prefix='',
                                               suffix='')
        cls.UNDELETABLE_FILE = os.path.join(cls.RO_TEMP_SUB_DIR,
                                            'undeletable')
        with open(cls.UNDELETABLE_FILE, 'w+'):
            pass
        os.chmod(cls.RO_TEMP_SUB_DIR, stat.S_IRUSR | stat.S_IXUSR)

    @classmethod
    def tearDownClass(cls):
        os.chmod(cls.RO_TEMP_SUB_DIR, stat.S_IRWXU)
        os.unlink(cls.UNDELETABLE_FILE)
        os.rmdir(cls.RO_TEMP_SUB_DIR)

    def test_delete_file_on_non_existant_file(self):
        SshHarness._delete_file(
            os.path.join(TEMP_PATH, 'some_file_that_should_not_exist'))

    def test_delete_file_on_undeletable_file_ro_parent_dir(self):
        SshHarness._delete_file(self.__class__.UNDELETABLE_FILE)

    def test_delete_file_succes(self):
        with tempfile.NamedTemporaryFile(delete=False,
                                         dir=TEMP_PATH,
                                         suffix='',
                                         prefix='') as f:
            pass

        self.assertTrue(os.path.exists(f.name))
        SshHarness._delete_file(f.name)
        self.assertFalse(os.path.exists(f.name))


# -----------------------------------------------------------------------------


class SshHarnessPermissions(SshHarness):

    SSH_BASEDIR = os.path.join(TEMP_PATH, 'subdir', 'subsubdir')
    # New list, because it is mutated by the __protect_private_keys() method.
    _NEED_CHMOD = []


class PermissionManagementTestCase(TestCase):

    def setUp(self):
        self._mode = 504
        self._mode_string = SshHarnessPermissions._mode2string(self._mode)
        if not os.path.isdir(SshHarnessPermissions.SSH_BASEDIR):
            os.makedirs(SshHarnessPermissions.SSH_BASEDIR,
                        mode=self._mode)
        bits = SshHarnessPermissions.SSH_BASEDIR.split(os.sep)
        self._subsubdir = SshHarnessPermissions.SSH_BASEDIR
        self._subdir = os.sep.join(bits[:-1])
        # The following in case for some reason the directories were hanging
        # around (from a failed previous run...)
        os.chmod(self._subsubdir, 504)
        os.chmod(self._subdir, 504)

    def tearDown(self):
        if os.path.isdir(self._subsubdir):
            os.rmdir(self._subsubdir)
        if os.path.isdir(self._subdir):
            os.rmdir(self._subdir)
        SshHarnessPermissions._NEED_CHMOD = []
        SshHarnessPermissions._HAVE_SUDO = False
        SshHarnessPermissions._errors = {}

    def test__protect_private_keys(self):
        SshHarnessPermissions._protect_private_keys()

        sdir_mode = stat.S_IMODE(os.stat(self._subdir).st_mode)
        self.assertEqual(sdir_mode & SshHarnessPermissions._MODE_MASK,
                         stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)
        ssdir_mode = stat.S_IMODE(os.stat(self._subsubdir).st_mode)
        self.assertEqual(ssdir_mode & SshHarnessPermissions._MODE_MASK,
                         stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)
        # Depending on the platform
        self.assertTrue(2 <= len(SshHarnessPermissions._NEED_CHMOD))
        self.assertIn((self._subdir, 504),
                      SshHarnessPermissions._NEED_CHMOD)
        self.assertIn((self._subsubdir, 504),
                      SshHarnessPermissions._NEED_CHMOD)

    def test__restore_modes_when_chmod_succeeds(self):
        SshHarnessPermissions._NEED_CHMOD.append((self._subdir, 504, ))
        SshHarnessPermissions._NEED_CHMOD.append((self._subsubdir, 504, ))
        SshHarnessPermissions._restore_modes()

        self.assertEqual(0, len(SshHarnessPermissions._NEED_CHMOD))

    def test__restore_modes_when_chmod_raises_permission_error(self):
        SshHarnessPermissions._HAVE_SUDO = True
        SshHarnessPermissions._NEED_CHMOD.append((self._subdir, 504, ))
        SshHarnessPermissions._NEED_CHMOD.append((self._subsubdir, 504, ))

        with patch('subprocess.call', return_value=0) as call_mock:
            with patch('os.chmod') as chmod_mock:
                chmod_mock.side_effect = _PermissionError()
                SshHarnessPermissions._restore_modes()

        chmod_mock.assert_has_calls([
            call(self._subsubdir, self._mode, ),
            call(self._subdir, self._mode, ),
            ])
        call_mock.assert_has_calls([
            call([
                'sudo', '-n', 'chmod', self._mode_string, self._subsubdir, ]),
            call([
                'sudo', '-n', 'chmod', self._mode_string, self._subdir, ]),
            ])

    def test__restore_modes_does_not_mind_if_need_chmod_empty(self):
        self.tearDown()
        with patch('os.chmod') as chmod_mock:
            SshHarnessPermissions._restore_modes()

        self.assertFalse(chmod_mock.called)


# -----------------------------------------------------------------------------


class DebugTestCase(TestCase):

    def setUp(self):
        self._debug = 'PYTHON_DEBUG'  # Which variable tells us we are in debug
        self._debug_value = None
        self._has_debug = self._debug in os.environ
        if self._has_debug is True:  # Save env. var. value for restoration
            self._debug_value = os.environ[self._debug]
        self.addCleanup(self._restore_env)
        self._client = Mock()

    def _ensure_no_debug(self):
        if self._has_debug:
            del os.environ[self._debug]

    def _ensure_debug(self):
        if not self._has_debug:
            os.environ[self._debug] = '1'

    def _restore_env(self):
        if not self._has_debug:
            if self._debug in os.environ:
                del os.environ[self._debug]
        else:
            if self._debug not in os.environ:
                os.environ[self._debug] = self._debug_value

    def test__debug_when_disabled(self):
        self._ensure_no_debug()

        with patch('ssh_harness.logger') as logger_mock:
            SshHarness._debug('a', 'b', None)

        self.assertEqual(logger_mock.debug.call_count, 0)

    def test__debug_when_enabled(self):
        self._ensure_debug()

        with patch('ssh_harness.logger') as logger_mock:
            SshHarness._debug('a', 'b', Mock())

        self.assertEqual(logger_mock.debug.call_count, 1)

# vim: syntax=python:sws=4:sw=4:et:
