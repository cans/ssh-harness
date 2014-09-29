# -*- coding: utf-8-unix; -*-
#
# Copyright © 2014, Nicolas CANIART <nicolas@caniart.net>
#
from __future__ import print_function
from unittest import TestCase, SkipTest
import errno
import os
import shutil
import signal
import stat
import subprocess
import sys
import traceback
import pwd


class BackupEditAndRestore(file):

    _SUFFIX = 'backup'

    def _move(self, src, dst):
        try:
            os.rename(src, dst)
        except OSError as e:
            try:
                # For windows.
                os.remove(dst)
                os.rename(src, dst)
            except OSError:
                pass
        os

    def __init__(self, path, mode='a', suffix=None, **kwargs):
        """Open a file for edition but creates a backup copy first.

        :param str suffix: the suffix to append the name of the file to create
            its backup copy (default is 'backup').

        .. note::

           As this is meant to edit existing file, the 'x' mode makes no
           sense here and is prohibited. Modes that don't authorize
           modifying the file are prohibited as well.
        """
        check_mode = (mode * 1).replace('U', 'r').replace('rr', 'r')
        if 'x' in check_mode:
            raise ValueError(
                "Use of 'x' in mode is non-sensical: why ask to backup a file "
                "you don't want to exist in the first place ?")
        if 'r' == check_mode[0] and '+' not in check_mode:
            raise ValueError('Wrong file opening mode: {}'.format(mode))
        self._path = path
        self._suffix = suffix or self.__class__._SUFFIX
        self._new_suffix = 'new-{}'.format(self._suffix)

        self._new_path = '{}.{}'.format(self._path, self._new_suffix)
        self._backup_path = '{}.{}'.format(self._path, self._suffix)
        self._have_backup = None
        self._restored = False

        # Users expects some content in the file, so we copy the original one.
        if mode[0] in ['a', 'r', 'U']:
            # Cannot copy, unless the file exists:
            if os.path.isfile(self._path):
                shutil.copy(self._path, self._new_path)

        kwargs.update({'mode': mode})  # Default mode is 'r'
        # Output is redirected to the new file
        super(BackupEditAndRestore, self).__init__(self._new_path, **kwargs)

    def __enter__(self):
        self._have_backup = False
        if os.path.isfile(self._path):
            shutil.copy(self._path, self._backup_path)
            self._have_backup = True
        return self

    def __exit__(self, *args):
         # Closes self._new_path (required before moving it)
        res = super(BackupEditAndRestore, self).__exit__(*args)

        # Put the original file 
        self._move(self._new_path, self._path)
        return res

    def restore(self):
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
         user@host: workdir$ python-coverage run -m tests --sources=module1,module2
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

    .. todo::

       - Improve reporting problems internal to this testcase class. As most
         of the work takes place in the setUpClass/tearDownClass methods,
         failures happening here are prone to messing things up. Work is needed
         to make this far more bullet proof.

       - Having OpenSSH daemonizing itself, makes reliably monitor that is does
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

       - What about the SFTP subsystem ? (Should be disable by default)

       - Append some random ascii bytes to the SSH_CONFIG_{OPEN,CLOSE}_TAG
         values so that tests can be nested or ran concurrently (there surely
         is more to do to achieve that but it is still one required bit).
    """

    try:
        MODULE_PATH = os.path.abspath(os.path.dirname(__file__))
    except (AttributeError, NameError):
        MODULE_PATH = os.path.abspath(os.path.dirname(__source__))
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
    _SSH_CONFIG_OPEN_TAG = '# BEGIN TEST-HARNES CONFIG'
    _SSH_CONFIG_CLOSE_TAG = '# END TEST-HARNES CONFIG'
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
# IgnoreUserKnownHosts yes <Never enable this or you will not be able to connect>

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
#UseLogin no <Default, but would not work otherwise running login requires to be root>
Banner none
AcceptEnv LANG LC_*

Subsystem sftp /usr/lib/openssh/sftp-server

UsePAM yes
'''

    @classmethod
    def _skip(cls, exc=None):
        if exc is not None:
            cls._errors['_skip(exc={})'.format(exc)] = \
                traceback.format_exc()

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
    def _check_dir(cls, path, mode):
        if not os.path.isdir(path):
            try:
                os.makedirs(path, mode)
            except Exception as e:
                cls._skip(exc=e)
        else:
            # Do we have the required permission
            res = os.stat(path)
            if mode != (res.st_mode & mode):
                cls._errors['_check_dir({}, {})'.format(path, mode)] = \
                    "Unsufficient permissions on directory `{}': need" \
                    " {} but got {}.".format(
                        path,
                        cls._mode2string(mode),
                        cls._mode2string(stat.S_IMODE(res.st_mode)))
                cls._skip()
        return True

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
                    ['ssh-keygen', '-t', key_type, '-b', cls._BITS[key_type], '-N',
                     '', '-f', key_file, '-C',
                     'Weak key generated for test purposes only '
                     '*DO NOT DISSEMINATE*'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE)
                process.communicate()
            except subprocess.CalledProcessError:
                raise Exception('ssh-keygen failed with exit-status {} output:\n==STDOUT==\n"{}"\n==STDERR==\n{}'.format(
                        process.returncode, process.stdout.read(), process.stderr.read()))
            else:
                if 0 != process.returncode:
                    raise Exception('ssh-keygen failed with exit-status {} output:\n==STDOUT==\n"{}"\n==STDERR==\n{}'.format(
                        process.returncode, process.stdout.read(), process.stderr.read()))
                else:
                    os.chmod(key_file, cls._KEY_FILES_MODE)

    @classmethod
    def _get_paths(cls, path):
        new_path = '{}.test-harness'.format(regular_path)
        backup_path = '{}.test-harness-backup'.format(regular_path)
        return new_path, backup_path

    @classmethod
    def _generate_environment_file(cls):
        if cls.SSH_ENVIRONMENT_FILE is False:
            return
        new_path, backup_path = cls._get_path(path)

        with BackupAndEdit(new_path, 'w+') as f:
            for k, v in cls.SSH_ENVIRONMENT.items():
                print("{}={}".format(k, v), file=f)

            cls._to_resore.append(f)

    @classmethod
    def _backup_file(cls, filename):
        have_attr = '_HAVE_{}'.format(filename)
        path_attr = '_{}_PATH'.format(filename)
        path = getattr(cls, path_attr, None)
        if path is None:
            cls._errors['restore_file({})'.format(filename)] = \
                'Cannot restore file which path attribute is not set: {}' \
                .format(attr)
            cls._skip()
        new_path, backup_path = cls._get_paths(path)

        if os.path.isfile(path):
            shutil.copy(regular_path, backup_path)
        os.mv(new_path, regular_path)


    @classmethod
    def _restore_environment_file(cls):
        with open(new_path) as f:
            for k, v in cls.SSH_ENVIRONMENT.items():
                print("{}={}".format(k, v), file=f)
        cls._restore_file('SSH_ENVIRONMENT')

    @classmethod
    def _generate_authzd_keys_file(cls):
        # Generate the authorized_key file with the newly created key in it.
        with open(cls.AUTHORIZED_KEYS_PATH, 'w') as authzd_file:
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
        with open(cls.SSHD_CONFIG_PATH, 'w') as f:
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
                     'ssh_config_open_tag': cls._SSH_CONFIG_OPEN_TAG,
                     'ssh_config_close_tag': cls._SSH_CONFIG_CLOSE_TAG,
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
        cls._SSHD = subprocess.call([
            '/usr/sbin/sshd', '-4', '-f', cls.SSHD_CONFIG_PATH])
        assert 0 == cls._SSHD

    @classmethod
    def _update_ssh_config(cls, args):
        cls._HAVE_SSH_CONFIG = False
        if cls.UPDATE_SSH_CONFIG is False:
            return
        # cls._check_dir(cls._SSH_CONFIG_PATH, stat.S_IRWXU)
        with open(cls._SSH_CONFIG_PATH, 'a') as user_config:
            cls._HAVE_SSH_CONFIG = True
            user_config.write('''{ssh_config_open_tag}
Host {ssh_config_host_name}
        HostName {address}
        Port {port}
        IdentityFile {identity}
{ssh_config_close_tag}
'''.format(**args))

    @classmethod
    def _restore_ssh_config(cls):

        restored_path = '{}.cleaned'.format(cls._SSH_CONFIG_PATH)
        with open(restored_path, 'w+') as restored:
            skip = False
            with open(cls._SSH_CONFIG_PATH, 'r') as modified:
                for line in modified:
                    stripped_line = line.strip()
                    if cls._SSH_CONFIG_OPEN_TAG == stripped_line:
                        skip = True

                    if skip is False:
                        restored.write(line)

                    if cls._SSH_CONFIG_CLOSE_TAG == stripped_line:
                        skip = False

    @classmethod
    def _update_user_known_hosts(cls):
        """Updates the user's `~/.ssh/known_hosts' file to prevent to be
        prompted to validate the server's host key.

        The original file is backed-up so it can be restored upon tests
        completion.
        """

        # Back-up the previous file, if it exists, for later restoration.
        if os.path.isfile(cls._KNOWN_HOSTS_PATH):
            cls._HAVE_KNOWN_HOSTS = True
            shutil.copyfile(cls._KNOWN_HOSTS_PATH,
                            '{}.back'.format(cls._KNOWN_HOSTS_PATH))

        # Use ssh-keyscan to pull the servers keys and add them to the file.
        with open(cls._KNOWN_HOSTS_PATH, 'a') as known_hosts:
            keyscanner = subprocess.Popen([
                'ssh-keyscan', '-H4', '-p', str(cls.PORT),
                cls.BIND_ADDRESS, ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            (out, errout) = keyscanner.communicate()

            # We check the length of `out` because in case of connection
            # failure, ssh-keyscan still exit with 0, but spits nothing.
            if (0 != keyscanner.returncode
                or 0 == len(out)):
                cls._errors['_update_user_know_hosts'] = ( 
                    'ssh-keyscan failed with status {}: {}\nOutput: {}'
                    .format(keyscanner.returncode,
                            errout.decode('utf-8'),
                            out.decode('utf-8')))
            else:
                # Seems we got what we need, save it.
                known_hosts.write(out)

    @classmethod
    def _restore_file(cls, filename):
        attr = '_{}_PATH'.format(filename)
        path = getattr(cls, '_{}_PATH'.format(filename), None)
        if path is None:
            cls._errors['restore_file({})'.format(filename)] = \
                'Cannot restore file which path attribute is not set: {}' \
                .format(attr)

        have_path = getattr(cls, '_HAVE_{}'.format(filename), False)
        if have_path is None:
            return  # We never delt with this file during setup so we skip it.

        if have_path is True:
            # Restore backed-up ~/.ssh/known_hosts file.
            backup = '{}.back'.format(path)
            if os.path.isfile(backup):
                shutil.move(backup, path)
        else:
            # Or remove it if the file did not exists before.
            if os.path.isfile(path):
                os.unlink(path)
            # Ignore uncreated file might be because of a previous error.

    @classmethod
    def _restore_user_known_hosts(cls):
        cls._restore_file('KNOWN_HOSTS')

    @classmethod
    def _restore_ssh_config(cls):
        cls._restore_file('SSH_CONFIG')

    @classmethod
    def _mode2string(cls, mode):
        # Python 3 octal notation is 0o<digit> WTF !!
        return oct(mode).replace('o', '')

    @classmethod
    def _protect_private_keys(cls):
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
        for directory, mode in cls._NEED_CHMOD:
            subprocess.call([
                'sudo', 'chmod', cls._mode2string(mode), directory,
                ])

    @classmethod
    def _preconditions(cls):
        res = pwd.getpwuid(os.getuid())
        cls._check_dir(res.pw_dir, stat.S_IRWXU)
        cls._check_dir(os.path.dirname(cls._SSH_CONFIG_PATH), stat.S_IRWXU)
        cls._check_dir(os.getcwd(), stat.S_IRWXU)
        cls._check_dir(cls.FIXTURE_PATH, stat.S_IRWXU)

    @classmethod
    def setUpClass(cls):
        args = cls._gather_config()
        cls._preconditions()
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
        cls._restore_user_known_hosts()

        # If the server was started.
        if hasattr(cls, 'SSHD_PIDFILE_PATH'):
            try:
                with open(cls.SSHD_PIDFILE_PATH, 'r') as pidfile:
                    daemon_pid = int(pidfile.read())
                os.kill(daemon_pid, signal.SIGTERM)
            except IOError as e:
                if errno.ENOENT == e.errno:
                    # Assuming server died (which is not ok... but for now)
                    pass
                else:
                    raise

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

        # Now that we destroyed all keys we can restore the modes of the
        # directories that were along their path.
        cls._restore_modes()

        if cls.UPDATE_SSH_CONFIG is True:
            cls._restore_ssh_config()


class PubKeyAuthSshClientTestCase(BaseSshClientTestCase):

    USE_AUTH_METHOD = BaseSshClientTestCase.AUTH_METHOD_PUBKEY


class PasswdAuthSshClientTestCase(BaseSshClientTestCase):

    USE_AUTH_METHOD = BaseSshClientTestCase.AUTH_METHOD_PASSWORD


# vim: syntax=python:sws=4:sw=4:et:
