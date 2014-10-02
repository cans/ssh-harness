# -*- coding: utf-8-unix; -*-
#
#  Copyright © 2014, Nicolas CANIART <nicolas@caniart.net>
#
#  This file is part of vs-ssh.
#
#  vcs-ssh is free software: you can redistribute it and/or modify
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
from __future__ import print_function
from unittest import TestCase, SkipTest
import errno
import os
import shutil
import signal
import stat
import subprocess
import traceback
import time
import pwd
from locale import getpreferredencoding


__ALL__ = [
    'BackupEditAndRestore',
    'PubKeyAuthSshClientTestCase',
    'PasswdAuthSshClientTestCase',
    ]

_ENCODING = getpreferredencoding(do_setlocale=False)


class BackupEditAndRestore(object):
    """Open a file for edition but creates a backup copy first.

    :param str path: the path to the target file.
    :param str suffix: the suffix to append the name of the file to create
        its backup copy (default is 'backup').
    :param str mode: the mode in which open the file (see :py:func:`open`)

    All keyword arguments accepted by the :py:func:`open` function are
    accepted.

    This context manager tryes to make the changes to the file appear atomic.
    To that end as well as creating a backup copy, it create an *edition* copy
    of the target file.
    When entering the context the file being modified is in fact not the target
    file but its *edition-copy*
    When the contex is exited the *edition-file* replaces the target file
    (atomically if the OS platform supports it, i.e. atomicity is guaranteed
    on POSIX system).

    You need to keep a reference to the context manager up to the time
    you want to restore the file, which is achieve by calling its
    :py:meth:`restore` method.

    .. note::

       The mode 'r' is prohibited here are it makes no sense to backup
       a file to do nothing with it.
    """

    _SUFFIX = 'backup'

    def _move(self, src, dst):
        """Wrapper around :py:func:`os.rename` that handles some issues on
        platform which do not have an atomic rename."""
        try:
            os.rename(src, dst)
        except OSError:
            try:
                # For windows.
                os.remove(dst)
                os.rename(src, dst)
            except OSError:
                pass

    def __init__(self, path, mode='a', suffix=None, **kwargs):
        check_mode = (mode * 1).replace('U', 'r').replace('rr', 'r')
        if 'r' == check_mode[0] and '+' not in check_mode:
            raise ValueError('Wrong file opening mode: {}'.format(mode))
        self._path = path
        self._suffix = suffix or self.__class__._SUFFIX
        self._new_suffix = 'new-{}'.format(self._suffix)

        self._new_path = '{}.{}'.format(self._path, self._new_suffix)
        self._backup_path = '{}.{}'.format(self._path, self._suffix)

        # Some flags used to know where we're at.
        self._entered = False
        self._have_backup = None
        self._restored = False

        # Users expects some content in the file, so we copy the original one.
        if mode[0] in ['a', 'r', 'U']:
            # Cannot copy, unless the file exists:
            if os.path.isfile(self._path):
                shutil.copy(self._path, self._new_path)

        kwargs.update({'mode': mode})  # Default mode is 'a'
        # Output is redirected to the new file
        self._f = open(self._new_path, **kwargs)
        # super(BackupEditAndRestore, self).__init__(self._new_path, **kwargs)

    def __enter__(self):
        if self._entered is True:
            raise RuntimeError(
                "You cannot re-use a {} context manager (recursivelly or "
                "otherwise)".format(self.__class__.__name__))
        self._entered = True
        self._have_backup = False
        self._f.__enter__()
        # super(BackupEditAndRestore, self).__enter__()

        if os.path.isfile(self._path):
            shutil.copy(self._path, self._backup_path)
            self._have_backup = True
        return self

    def __getattr__(self, name):
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            return object.__getattribute__(self._f, name)

    def __exit__(self, *args):
        # Closes self._new_path (required before moving it)
        res = self._f.__exit__(*args)
        # res = super(BackupEditAndRestore, self).__exit__(*args)

        # Replace the original file with the one that has been edited.
        self._move(self._new_path, self._path)
        return res

    def restore(self):
        """Restores the file as it were before:

        If it did not exist then it is removed, otherwise its back-up
        copy is used to restore it in its previous state."""
        if self._restored is True:
            # TODO raise an exception.
            return
        self._restored = True

        if self._have_backup is True:
            self._move(self._backup_path, self._path)
        else:
            os.unlink(self._path)


class BaseSshClientTestCase(TestCase):
    """Base class for several ssh client test cases classes.

    ==Introduction==

    This class contains most of the machinery required to tests programs
    that require a SSH connections. It takes care of setting-up, starting,
    stopping and cleaning up after your tests are done.

    Setting-up means generating:

    - host key pairs (RSA, DSA and ECDSA)
    - a configuration file

    for the SSH daemon to be started. As well as:

    - a key pair
    - an authorized_keys file
    - adds an entry for the new home ~/.ssh_config file

    for the current user

    All those data are, by default written and stored in a
    'tests/fixtures/sshd' directory within the working directory of the
    test runner that runs the test. This can be changed by overriding
    the ``FIXTURE_PATH`` class attribute of the test case.

    .. example::

       Assuming you work in an environment where you run your test from
       the base directory of your project, i.e. somewhat like this::

         user@hsot: workdir$ pwd
         /path/to/workdir
         user@host: workdir$ ls
         module1/       module2/        setup.py        tests/
         scripts/
         user@host: workdir$ python -m tests
         ...
         user@host: workdir$ python-coverage run -m tests \
             --sources=module1,module2
         ...
         user@host: workdir$ python-coverage html
         ...

       Then the files necessary to run the SSH daemon are stored in the
        ``/path/to/workdir/tests/fixtures/sshd``  directory.

    Once the SSH daemon has started we update the current user's
    ``~/.ssh/known_hosts`` file (see :man:`ssh-keyscan`) so that the
    tests are not bothered by the host key validation prompt.

    Once all this is done, the tests start being executed.

    .. note::

       All tests belonging to a class derived from this one will see their
       tests run against the same SSH daemon instance, it is not restarted
       between two tests.


    After all your tests have ran, all the above generated files are removed
    and your ``~/.ssh/known_hosts`` file is restored to its previous state
    (to avoid having tons of useless host key in it, since we through all
    those keys away).


    ==Configuration options==

    Lots of parameters can be configured:

    ===Network parameters===

    - ``BIND_ADDRESS``: the address the daemon will listen to. The default is
      the loopback address (``127.0.0.1``) for obvious security and test
      insulation reasons.
    - ``PORT``: the TCP port the daemon will listen to. The default is 2200.

    ===Auxiliary programs===

    Obviously OpenSSH is required for this test harness to work. But also
    :man:`ssh-keygen` and :man:`ssh-keyscan` which are standard tools
    included in the OpenSSH distribution. Depending on your distribution they
    might be installed in different places.

    - ``SSHD_BIN``: set the path to the OpenSSH sshd daemon. The default is
      ``/usr/sbin/sshd`` as installed on Debian systems.
    - ``SSH_KEYGEN_BIN``: set the path to ``ssh-keygen``. The default path
      is ``/usr/bin/ssh-keygen``
    - ``SSH_KEYSCAN_BIN``: set the path to ``ssh-keyscan``. The default path
      is ``/usr/bin/ssh-keyscan``.

    ===Authorized keys options===

    As already told, this test harness generates a ``authorized_keys`` file
    for you that contains the user public key generated during setup. Such
    a file may contain options in front of the public key to further configure
    or restrict the connection. You can specify such options by setting
    the ``AUTHORIZED_KEY_OPTIONS`` class attribute of your test case. Its
    value must be a string that contain valid options (the string you provide
    is not validated).

    ===Environment variables===

    You ask SSHD to set certain environment variables for you upon connection.
    To specify those you need to override the ``SSH_ENVIRONMENT`` class
    attribute. It is a dictionary which keys are the names of the environment
    variables to set and values will be the value of the environment variable
    value.

    By default the dictionary is empty, and use of environment variables is
    disabled in SSHD configuration. Adding one or more key/value pairs to the
    dictionnary implicitly enables their use.


    ===Some notes about SSHD configuration===

    There are options that very important for the successfull run of the
    test written using this class. Disabling or enabling either of them will
    most likely make your tests fail:

    :IgnoreUserKnownHosts:
        You should never enable this option (set it to ``yes``). Indeed this
        class uses the ``~/.ssh/known_hosts`` file to prevent the host key
        validation prompt to show up during your tests.
        If you run your tests uninteractively, e.g. on a CI machine, your
        tests will fail as they will timeout, waiting someone to validate
        the host key received from the server, which noone can do.

    :UseLogin:
        You should never enable this option (set it to ``yes``). Running login
        requires root privileges, which you surely are not as
        *noone should never ever* run a test suite as root.

    .. todo::

       - Improve reporting problems internal to this testcase class. As most
         of the work takes place in the setUpClass/tearDownClass methods,
         failures happening here are prone to messing things up. Work is needed
         to make this far more bullet proof.

       - Having OpenSSH daemonizing itself makes reliably monitor that is does
         not crash, fails to start, and such quite difficult...
         Assuming it is a quite proven soft, we could monitor its pidfile
         with something like iNotify...

       - We good offer an option to force server restarts in between tests.
         Not sure if it would be easy to make it relayable on a moderately
         loaded machine.

       - Generate only one ECDSA host key (instead of ECDSA+DSA+RSA) to lower
         the start-up time treshold.

       - Chroot the connection to the SSH daemon within the project directory
         (i.e. ``/path/to/workdir`` to follow-up with the above example).

       - Provide means set autorized key options on a per-test basis.

       - What about the SFTP subsystem ? (Should be disabled by default)
    """

    MODULE_PATH = os.path.abspath(os.path.dirname(__file__))
    FIXTURE_PATH = os.path.sep.join([
        os.path.abspath(os.getcwd()), 'tests', 'fixtures', 'sshd', ])

    AUTH_METHOD_PASSWORD = (True, False, )
    AUTH_METHOD_PUBKEY = (False, True, )
    PORT = 2200
    BIND_ADDRESS = '127.0.0.1'

    USE_AUTH_METHOD = None

    SSHD_BIN = '/usr/sbin/sshd'
    SSH_KEYSCAN_BIN = '/usr/bin/ssh-keyscan'
    SSH_KEYGEN_BIN = '/usr/bin/ssh-keygen'
    SSH_CONFIG_HOST_NAME = 'test-harness'
    SSH_ENVIRONMENT = {}
    SSH_ENVIRONMENT_FILE = False
    UPDATE_SSH_CONFIG = True

    AUTHORIZED_KEY_OPTIONS = None

    _errors = {}
    """Collects the errors that may happen during the fairly complex
    setUpClass() method. So that the test-cases can be skipped and
    problems reported properly."""

    _FILES = {
        'HOST_ECDSA_KEY': 'host_ssh_ecdsa_key',
        'HOST_DSA_KEY': 'host_ssh_dsa_key',
        'HOST_RSA_KEY': 'host_ssh_rsa_key',
        'USER_RSA_KEY': 'id_rsa',
        'AUTHORIZED_KEYS': 'authorized_keys',
        'SSHD_CONFIG': 'sshd_config',
        'SSHD_PIDFILE': 'sshd.pid',
        }
    _MODE_MASK = (stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP
                  | stat.S_IROTH | stat.S_IXOTH | stat.S_ISVTX)
    _BIN_MASK = (stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP
                 | stat.S_IROTH | stat.S_IXOTH)
    """Mode mask to check the mode of the parent directories of the one
    the contains the key. The most permission the can have is this:
    rwxr-xr-x (0755) other wise some other than the owner of the key may
    ). I am not yet clear on the requirements of the Set-UID, Set-GID,
    Sticky-bit, etc.
    """
    _NEED_CHMOD = []
    """Collects the paths of the directories on the path to the private keys
    that need to be chmod-ed before running the tests to they can later be
    restored.
    """

    _NEED_TO_BE_RESTORED = []

    _KEY_FILES_MODE = 0x00000000 | stat.S_IRUSR
    """Access mode that is set on files containing private keys."""

    _BITS = {
        'dsa': '1024',
        'rsa': '768',
        'ecdsa': '256',
        }
    """The sizes of the key to ask with respect to their type (we purposely
    request the weakest key sizes possible to not slow the test cases too
    much."""

    _HAVE_SSH_CONFIG = None
    _HAVE_KNOWN_HOST = None
    _HAVE_SSH_ENVIRONMENT = None
    _HAVE_KNOWN_HOSTS = None

    _AUTH_METHODS = ('password_auth', 'pubkey_auth', )
    _KNOWN_HOSTS_PATH = os.path.expanduser('~/.ssh/known_hosts')
    _SSH_ENVIRONMENT_PATH = os.path.expanduser('~/.ssh/environment')
    _SSH_CONFIG_PATH = os.path.expanduser('~/.ssh/config')
    _SSHD = None
    """Handle on the SSH daemon process."""

    _SSHD_CONFIG = '''# ssh_harness generated configuration file
Port {port}
ListenAddress {address}
Protocol 2
HostKey {host_rsa_key_path}
HostKey {host_dsa_key_path}
HostKey {host_ecdsa_key_path}
#Privilege Separation is turned on for security (useful when run as non-root ?)
UsePrivilegeSeparation yes

KeyRegenerationInterval 3600
ServerKeyBits 1024

SyslogFacility AUTH
LogLevel VERBOSE

PidFile {sshd_pidfile_path}
LoginGraceTime 120
PermitRootLogin yes
StrictModes yes

RSAAuthentication yes
PubkeyAuthentication {pubkey_auth}
AuthorizedKeysFile	{authorized_keys_path}
PermitUserEnvironment {permit_environment}

IgnoreRhosts yes
RhostsRSAAuthentication no
HostbasedAuthentication no

PermitEmptyPasswords no
ChallengeResponseAuthentication no
PasswordAuthentication {password_auth}

# Kerberos options
#KerberosAuthentication no
#KerberosGetAFSToken no
#KerberosOrLocalPasswd yes
#KerberosTicketCleanup yes

# GSSAPI options
GSSAPIAuthentication no
GSSAPICleanupCredentials yes
GSSAPIKeyExchange yes
GSSAPIStoreCredentialsOnRekey yes

X11Forwarding yes
X11DisplayOffset 10
PrintMotd no
PrintLastLog no
TCPKeepAlive yes
Banner none
AcceptEnv LANG LC_*

# Subsystem sftp /usr/lib/openssh/sftp-server

UsePAM yes
'''

    @classmethod
    def _skip(cls):
        # Be civil, clean-up anyways.
        cls.tearDownClass()

        # TODO build a nice message with errors' content
        reason = 'One or more errors occurred while trying to setup the' \
            ' functional test-suite:\n'
        for func, msg in cls._errors.items():
            reason += ' - {}\n'.format(func)
            for line in msg.splitlines():
                reason += '    {}'.format(line)
        # Skip.
        raise SkipTest(reason)

    @classmethod
    def _guess_key_type(cls, name):
        if 'ECDSA' in name:
            return 'ecdsa'
        elif 'DSA' in name:
            return 'dsa'
        else:
            return 'rsa'

    @classmethod
    def _exc2error(cls, exc):
        if exc is not None:
            cls._errors['_skip(exc={})'.format(exc)] = \
                traceback.format_exc()

    @classmethod
    def _check_auxiliary_program(cls, path, error=True):
        if not os.path.isfile(path):
            if error:
                cls._errors[path] = 'Program not found.'
            return False

        res = os.access(path, os.R_OK | os.X_OK)
        if res is False and error is True:
            cls._errors[path] =     \
                "Program `{}' is not executable, its mode is {},"         \
                " expected {}".format(
                    cls._mode2string(stat.S_IMODE(res.st_mode)),
                    cls._mode2string(stat.S_IMODE(cls._BIN_MASK)))
        return res

    @classmethod
    def _check_dir(cls, path, mode):
        if not os.path.isdir(path):
            try:
                os.makedirs(path, mode)
            except Exception as e:
                cls._exc2error(exc=e)
                return False

        # Ok we got the directory, but since the mask passed to chmod is
        # umask-ed we may not have the right permissions. So we must check
        # them anyway.

        # Do we have the required permission
        res = os.stat(path)
        if mode != (res.st_mode & mode):
            cls._errors['_check_dir({}, {})'.format(path, mode)] = \
                "Unsufficient permissions on directory `{}': need" \
                " {} but got {}.".format(
                    path,
                    cls._mode2string(mode),
                    cls._mode2string(stat.S_IMODE(res.st_mode)))
            return False
        return True

    @classmethod
    def _add_file_to_restore(cls, file):
        """Add a file to the list of those to be restore at the end of the
        tests."""
        cls._NEED_TO_BE_RESTORED.append(file)

    @classmethod
    def _delete_file(cls, file):
        if os.path.isfile(file) is True:
            os.unlink(file)

    @classmethod
    def _generate_keys(cls):
        # Generate the required keys.
        for f in [x for x in cls._FILES.keys() if(x.startswith('HOST_')
                                                  or x.startswith('USER_'))]:
            key_type = cls._guess_key_type(f)
            key_file = getattr(cls, '{}_PATH'.format(f))

            if os.path.isfile(key_file):
                os.unlink(key_file)
            try:
                process = subprocess.Popen(
                    ['ssh-keygen', '-t', key_type, '-b', cls._BITS[key_type],
                     '-N', '', '-f', key_file, '-C',
                     'Weak key generated for test purposes only '
                     '*DO NOT DISSEMINATE*'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE)
                process.communicate()
            except subprocess.CalledProcessError:
                raise Exception('ssh-keygen failed with exit-status {} output:'
                                '\n==STDOUT==\n"{}"\n==STDERR==\n{}'
                                .format(process.returncode,
                                        process.stdout.read(),
                                        process.stderr.read()))
            else:
                if 0 != process.returncode:
                    raise Exception('ssh-keygen failed with exit-status {} '
                                    'output:\n==STDOUT==\n"{}"\n==STDERR==\n{}'
                                    .format(process.returncode,
                                            process.stdout.read(),
                                            process.stderr.read()))
                else:
                    os.chmod(key_file, cls._KEY_FILES_MODE)

    @classmethod
    def _generate_environment_file(cls):
        if cls.SSH_ENVIRONMENT_FILE is False:
            return
        with BackupEditAndRestore(cls.SSH_ENVIRONMENT_PATH, 'w+t') as f:
            for k, v in cls.SSH_ENVIRONMENT.items():
                print("{}={}".format(k, v), file=f)

        cls._add_file_to_restore(f)

    @classmethod
    def _generate_authzd_keys_file(cls):
        # Generate the authorized_key file with the newly created key in it.
        with open(cls.AUTHORIZED_KEYS_PATH, 'wt') as authzd_file:
            with open('{}.pub'.format(cls.USER_RSA_KEY_PATH), 'r') as user_key:
                key = user_key.read()
            if cls.SSH_ENVIRONMENT and cls.SSH_ENVIRONMENT_FILE is False:
                env = ','.join([
                    'environment="{}={}"'.format(*x)
                    for x in cls.SSH_ENVIRONMENT.items()])
                if cls.AUTHORIZED_KEY_OPTIONS is not None:
                    cls.AUTHORIZED_KEY_OPTIONS += ',' + env
                else:
                    cls.AUTHORIZED_KEY_OPTIONS = env
            if cls.AUTHORIZED_KEY_OPTIONS is not None:
                authzd_file.write("{} ".format(cls.AUTHORIZED_KEY_OPTIONS))
            authzd_file.write("{}\n".format(key))

    @classmethod
    def _generate_sshd_config(cls, args):
        with open(cls.SSHD_CONFIG_PATH, 'wt') as f:
            f.write(cls._SSHD_CONFIG.format(**args))

    @classmethod
    def _gather_config(cls):
        args = {}

        # Fill up the dictionnary with all the file paths required by the
        # daemon configuration file.
        for k, v in cls._FILES.items():
            attrname = '{}_PATH'.format(k)
            argname = '{}_path'.format(k.lower())
            if not hasattr(cls, attrname):
                setattr(cls, attrname, os.path.join(cls.FIXTURE_PATH, v))
                args.update({argname:  getattr(cls, attrname), })

        # Set the TCP port and IP address the daemon will listen to.
        args.update({'port': cls.PORT,
                     'address': cls.BIND_ADDRESS,
                     })
        # Sets some options used to update the current user's ~/.ssh/config
        # file.
        args.update({'ssh_config_host_name': cls.SSH_CONFIG_HOST_NAME,
                     'identity': cls.USER_RSA_KEY_PATH,
                     })

        # En- or disables PublicKey and Password authentication methods.
        args.update(dict(zip(
            cls._AUTH_METHODS,
            ['yes' if x is True else 'no' for x in cls.USE_AUTH_METHOD])))

        args.update({
            'permit_environment': 'yes' if cls.SSH_ENVIRONMENT else 'no', })
        return args

    @classmethod
    def _start_sshd(cls):
        # Start the SSH daemon
        cls._SSHD = subprocess.Popen([
            '/usr/sbin/sshd', '-D', '-4', '-f', cls.SSHD_CONFIG_PATH])

        # This is silly, but simple enough and works apparently
        rounds = 0
        while not os.path.isfile(cls.SSHD_PIDFILE_PATH) and 5 > rounds:
            time.sleep(1)
            rounds += 1
        if rounds >= 5:
            self._errors['ssh daemon'] = 'Not starting or crashing at startup.'
            self._skip()

    @classmethod
    def _kill_sshd(cls):
        cls._SSHD.terminate()
        return cls._SSHD.poll()

    @classmethod
    def _update_ssh_config(cls, args):
        if cls.UPDATE_SSH_CONFIG is False:
            return

        with BackupEditAndRestore(cls._SSH_CONFIG_PATH, 'a') as user_config:
            user_config.write('''
Host {ssh_config_host_name}
        HostName {address}
        Port {port}
        IdentityFile {identity}
'''.format(**args))
        cls._add_file_to_restore(user_config)

    @classmethod
    def _update_user_known_hosts(cls):
        """Updates the user's `~/.ssh/known_hosts' file to prevent being
        prompted to validate the server's host key.
        """
        with BackupEditAndRestore(cls._KNOWN_HOSTS_PATH, 'a') as known_hosts:
            keyscanner = subprocess.Popen([
                'ssh-keyscan', '-H4', '-p', str(cls.PORT),
                cls.BIND_ADDRESS, ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            (out, errout) = keyscanner.communicate()

            # We check the length of `out` because in case of connection
            # failure, ssh-keyscan still exit with 0, but spits nothing.
            if 0 != keyscanner.returncode or 0 == len(out):
                cls._errors['_update_user_know_hosts'] = (
                    'ssh-keyscan failed with status {}: {}\nOutput: {}'
                    .format(keyscanner.returncode,
                            errout.decode(known_hosts.encoding),
                            out.decode(known_hosts.encoding or _ENCODING)))
            else:
                # Seems we got what we need, save it.
                known_hosts.write(
                    out.decode(known_hosts.encoding or _ENCODING))
        cls._add_file_to_restore(known_hosts)

    @classmethod
    def _mode2string(cls, mode):
        """Converts a integer into a string containing its value encoded
        in octal."""
        # Python 3 octal notation is 0o<digit> WTF !!
        return oct(mode).replace('o', '')

    @classmethod
    def _protect_private_keys(cls):
        """Changes the modes of the directories along the patht to the
        directory that contains the server and user private keys.
        Any directory not belonging to the keys owner must belong to root
        and not be group nor other-writable (to prevent hijacking the users
        private-key by replacing one of its parent directory by another one
        containing offensive keys).
        """
        path = cls.FIXTURE_PATH
        while '/' != path:
            res = os.stat(path)
            mode = stat.S_IMODE(res.st_mode)
            if 0 < (mode & ~cls._MODE_MASK):
                cls._NEED_CHMOD.append((path, mode, ))
                subprocess.call([
                    'sudo',
                    'chmod',
                    cls._mode2string(mode & cls._MODE_MASK),
                    path,
                    ])
            path = os.path.dirname(path)

    @classmethod
    def _restore_modes(cls):
        """Restores the directories which mode we changed to protect the
        private keys to their previous modes.
        (see ::``)"""
        for directory, mode in cls._NEED_CHMOD:
            subprocess.call([
                'sudo', 'chmod', cls._mode2string(mode), directory,
                ])

    @classmethod
    def _preconditions(cls):
        """Checks that some files or directory that commonly are missing or
        do not have the appropriate permssions are indeed present.

        If it is not possible to have these preconditions met, all the test
        cases defined by the class are skipped."""
        res = pwd.getpwuid(os.getuid())
        # Always use:
        #     pc_met = <condition> and pc_met
        # That way we preserve the truth value of pc_met and we can report as
        # many problems as we can at once.
        pc_met = cls._check_dir(res.pw_dir, stat.S_IRWXU)
        pc_met = cls._check_dir(os.path.dirname(cls._SSH_CONFIG_PATH),
                                stat.S_IRWXU) and pc_met
        pc_met = cls._check_dir(os.getcwd(), stat.S_IRWXU) and pc_met
        pc_met = cls._check_dir(cls.FIXTURE_PATH, stat.S_IRWXU) and pc_met
        pc_met = cls._check_auxiliary_program(cls.SSHD_BIN) and pc_met
        pc_met = cls._check_auxiliary_program(cls.SSH_KEYSCAN_BIN) and pc_met
        pc_met = cls._check_auxiliary_program(cls.SSH_KEYGEN_BIN) and pc_met
        if not pc_met:
            cls._skip()

    @classmethod
    def setUpClass(cls):
        """Sets up the environment to start-up an SSH daemon and access it.

        This functions keep thing at a high level calling a method for each
        required step.
        """
        args = cls._gather_config()
        cls._preconditions()  # May raise skip
        cls._generate_sshd_config(args)
        cls._protect_private_keys()
        cls._generate_keys()
        cls._generate_authzd_keys_file()
        cls._generate_environment_file()
        cls._start_sshd()

        if cls.UPDATE_SSH_CONFIG is True:
            cls._update_ssh_config(args)

        # We use ssh-keyscan and thus need SSHD to be up and running.
        cls._update_user_known_hosts()

        if cls._errors:
            cls._skip()

    @classmethod
    def tearDownClass(cls):
        # If the server was started.
        if cls._SSHD is not None:
            cls._kill_sshd()

        for f in cls._FILES.keys():
            file = getattr(cls, '{}_PATH'.format(f))
            if file.endswith('.pid'):
                continue  # sshd.pid is normally by sshd when it exits.
            cls._delete_file(file)
            if f.endswith('_KEY'):
                # Don't forget to remove the public key as well as the
                # private ones.
                file = '{}.pub'.format(getattr(cls, '{}_PATH'.format(f)))
                cls._delete_file(file)

        for backup in cls._NEED_TO_BE_RESTORED:
            backup.restore()

        # Now that we destroyed all keys we can restore the modes of the
        # directories that were along their path.
        cls._restore_modes()


class PubKeyAuthSshClientTestCase(BaseSshClientTestCase):

    USE_AUTH_METHOD = BaseSshClientTestCase.AUTH_METHOD_PUBKEY


class PasswdAuthSshClientTestCase(BaseSshClientTestCase):

    USE_AUTH_METHOD = BaseSshClientTestCase.AUTH_METHOD_PASSWORD


# vim: syntax=python:sws=4:sw=4:et:
