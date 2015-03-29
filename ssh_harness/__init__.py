# -*- coding: utf-8-unix; -*-
#
#  Copyright © 2014-2015, Nicolas CANIART <nicolas@caniart.net>
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
from unittest import TestCase, SkipTest
from gettext import lgettext as _
import logging
from logging.handlers import RotatingFileHandler
import os
import stat
import subprocess
import sys
import traceback
import time
import pwd
import warnings
from locale import getpreferredencoding

from .contexts import BackupEditAndRestore

__ALL__ = [
    'PubKeyAuthSshClientTestCase',
    'PasswdAuthSshClientTestCase',
    ]

_ENCODING = getpreferredencoding(do_setlocale=False)

logger = logging.getLogger('ssh-harness')
handler = RotatingFileHandler(os.path.join(os.getcwd(),
                                           'ssh-harness.log'),
                              backupCount=1,
                              delay=True)
handler.setFormatter(
    logging.Formatter(
        '%(asctime)s %(name)s[%(process)s]: %(message)s'))
logger.addHandler(handler)
if os.path.exists(handler.baseFilename):
    handler.doRollover()


# BEGIN TO BE REMOVED

# Deal with the varying expectation of the methods of the various
# StringIO implementations. Used as follows, they can accept str arguments
# both under Python 2 and Python 3 (Py2 io.String only accepts unicode args).
if (3, 0, 0, ) > sys.version_info:
    from StringIO import StringIO
    _PermissionError = OSError
else:
    from io import StringIO
    _PermissionError = PermissionError
import string


def hexdump(buf, file=sys.stdout, encoding='utf-8'):
    """Prints the content of a buffer as the :manpage:`hd(1)` command would.

    :param buf: the bytes, string, or unicode instance to be printed.
    :param file: a file-like object, in which write the output.
    :param file: encoding to use, buf is not a :py:type:`bytes` and it must
        be encoded.
    :returns: an :py:type:`int`, the number of bytes read from buffer.

    .. note::

       If :param:`buf` is of type bytes then assertion::

           len(buf) == hexdump(buf)

       should hold whatever version of python used, otherwise it may not.
    """
    global _EOL
    octets = ''
    i = 0

    if not isinstance(buf, bytes):
        # Py2/Py3 compatibility Py2 -> buf becomes unicode
        #                       Py3 -> buf becomes str
        buf = bytes(buf.encode(encoding))

    # TODO: enumerate will not return bytes but strings of one character
    # (each of which can be encoded by multiple bytes)
    for i, byte in enumerate(buf):
        if not isinstance(byte, int):
            byte = ord(byte)
        if 0 == i % 8 and not (0 == i % 16 or i == 0):
            file.write(' ')
            octets += ' '

        if 0 == i % 16:
            if i > 0:
                file.write(' |{}|\n'.format(octets))
            octets = ''
            file.write('{:08x}  '.format(i))
        file.write('{:02x} '.format(byte))
        octets += chr(byte) if 32 <= byte < 127 else '.'

    if i > 0 and '' != octets:
        if 7 == i % 8:
            file.write(' ')
        remainder = i % 16 + 1
        file.write(' ' * (((16 - remainder) * 3) + (2 - int(len(octets)/8))))
        file.write('|{}|\n'.format(octets))
        i += 1
    file.write(u'{:08x}\n'.format(i))
    return i


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
    the ``SSH_BASEDIR`` class attribute of the test case.

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

       - We could offer an option to force server restarts in between tests.
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
    SSH_BASEDIR = os.path.join(
        os.path.abspath(os.getcwd()), 'tests', 'tmp', 'sshd')

    AUTH_METHOD_PASSWORD = (True, False, )
    AUTH_METHOD_PUBKEY = (False, True, )
    AUTH_METHOD_ANY = (True, True, )
    PORT = 2200
    BIND_ADDRESS = 'localhost'

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
    _OLD_LANG = None

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

GSSAPIAuthentication no

X11Forwarding yes
X11DisplayOffset 10
PrintMotd no
PrintLastLog no
TCPKeepAlive yes
Banner none
AcceptEnv LANG LC_*

# Subsystem sftp /usr/lib/openssh/sftp-server
# *DO NOT* use: may prevent SSHD from opening a session.
UsePAM no
'''
    _context_name = 'ssh_harness'

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
                reason += '    {}\n'.format(line)
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
    def _check_auxiliary_program(cls, path, error=True):
        if not os.path.isfile(path):
            if error:
                cls._errors[path] = 'Program not found.'
            return False

        res = os.access(path, os.R_OK | os.X_OK)
        if res is False and error is True:
            cls._errors[path] = ("Program `{}' is not executable, its mode"
                                 " is {}, expected {}"
                                 .format(
                                     cls._mode2string(
                                         stat.S_IMODE(res.st_mode)),
                                     cls._mode2string(
                                         stat.S_IMODE(cls._BIN_MASK))))
        return res

    @classmethod
    def _check_dir(cls, path, mode=None):
        if mode is None:
            mode = stat.S_IRWXU
        if not os.path.isdir(path):
            try:
                os.makedirs(path, mode)
            except OSError as e:
                cls._errors['_skip(exc={})'.format(e)] = \
                    traceback.format_exc()
                return False

        # Ok we got the directory, but since the mask passed to chmod is
        # umask-ed we may not have the right permissions. So we must check
        # them anyway.

        # Do we have the required permission
        res = os.stat(path)
        if mode != (res.st_mode & mode):
            cls._errors['_check_dir({}, {})'.format(path, mode)] = \
                "Insufficient permissions on directory `{}': need" \
                " {} but got {}.".format(
                    path,
                    cls._mode2string(mode),
                    cls._mode2string(stat.S_IMODE(res.st_mode)))
            return False
        return True

    @classmethod
    def _delete_file(cls, file):
        logger.debug(_("Cleaning up file `{}'").format(file))
        if os.path.isfile(file) is True:
            try:
                os.unlink(file)
                logger.debug("File `{}' removed.".format(file))
            except Exception as e:
                logger.exception(e)
        else:
            logger.debug(_("Path `{}' does not designate a file.")
                         .format(file))

    @classmethod
    def _generate_keys(cls):
        # Generate the required keys.
        for f in [x for x in cls._FILES.keys() if(x.startswith('HOST_')
                                                  or x.startswith('USER_'))]:
            key_type = cls._guess_key_type(f)
            key_file = getattr(cls, '{}_PATH'.format(f))

            if os.path.isfile(key_file):
                os.unlink(key_file)
            returncode, out, err = cls.runCommand([
                cls.SSH_KEYGEN_BIN,
                '-t', key_type,
                '-b', cls._BITS[key_type],
                '-N', '', '-f', key_file,
                '-C',
                'Weak key generated for test purposes only '
                '*DO NOT DISSEMINATE*'
                ])

            if 0 != returncode:
                raise RuntimeError('ssh-keygen failed with exit-status {} '
                                   'output:\n==STDOUT==\n{}\n==STDERR==\n{}'
                                   .format(returncode, out, err))
            else:
                os.chmod(key_file, cls._KEY_FILES_MODE)

    @classmethod
    def _generate_environment_file(cls):
        if cls.SSH_ENVIRONMENT_FILE is False:
            return
        with BackupEditAndRestore(cls._context_name,
                                  cls._SSH_ENVIRONMENT_PATH,
                                  'w+t') as f:
            for k, v in cls.SSH_ENVIRONMENT.items():
                print("{}={}".format(k, v), file=f)

    @classmethod
    def _generate_authzd_keys_file(cls):
        # Generate the authorized_key file with the newly created key in it.
        logger.debug("Creating the user's authorized_keys file.")
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
                authzd_file.write(cls.AUTHORIZED_KEY_OPTIONS)
                authzd_file.write(' ')

            authzd_file.write(key)
            authzd_file.write('\n')
            logger.debug("{} {}".format(cls.AUTHORIZED_KEY_OPTIONS, key))

        logger.debug("=" * 60)

    @classmethod
    def _generate_sshd_config(cls, args):
        with open(cls.SSHD_CONFIG_PATH, 'wt') as f:
            content = cls._SSHD_CONFIG.format(**args)
            logger.debug(content)
            f.write(content)

    @classmethod
    def _gather_config(cls):
        args = {}

        # Fill up the dictionnary with all the file paths required by the
        # daemon configuration file.
        for k, v in cls._FILES.items():
            attrname = '{}_PATH'.format(k)
            argname = '{}_path'.format(k.lower())
            if not hasattr(cls, attrname):
                setattr(cls, attrname, os.path.join(cls.SSH_BASEDIR, v))
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
        sshd_startup_command = [
            cls.SSHD_BIN, '-D', '-4', '-f', cls.SSHD_CONFIG_PATH,
            ]
        logger.debug('Starting SSH Deamon with command `{}'
                     .format(sshd_startup_command))
        # Start the SSH daemon
        cls._SSHD = subprocess.Popen(sshd_startup_command,
                                     stdout=subprocess.PIPE)

        # This is silly, but simple enough and works apparently
        for round in range(0, 6):
            if not os.path.isfile(cls.SSHD_PIDFILE_PATH):
                time.sleep(1)
            else:
                break
        if round >= 5:
            cls._kill_sshd()
            cls._SSHD = None
            cls._errors[cls.SSHD_BIN] = 'Not starting or crashing at startup.'
            cls._skip()

    @classmethod
    def _kill_sshd(cls):
        cls._SSHD.terminate()
        return cls._SSHD.poll()

    @classmethod
    def _update_ssh_config(cls, args):
        if cls.UPDATE_SSH_CONFIG is False:
            return

        with BackupEditAndRestore(cls._context_name,
                                  cls._SSH_CONFIG_PATH,
                                  'a') as user_config:
            user_config.write('''
Host {ssh_config_host_name}
        HostName {address}
        Port {port}
        IdentityFile {identity}
'''.format(**args))

    @classmethod
    def _update_user_known_hosts(cls):
        """Updates the user's *known hosts* file to prevent being
        prompted to validate the server's host key.

        .. note::

            The path to this file can be configured through the classes
            :py:attr:`BaseSshClientTestCase._KNOWN_HOSTS_PATH` attribute.
            It defaults to `~/.ssh/known_hosts`
        """
        failures = []
        with BackupEditAndRestore(cls._context_name,
                                  cls._KNOWN_HOSTS_PATH,
                                  'a') as known_hosts:
            # we need to split IPv4 and IPv6 host key discovery because
            # :manpage:`ssh-keyscan(1)` fails if either fail.
            for ip_version in ['-4', '-6', ]:
                returncode, out, err = cls.runCommand([
                    cls.SSH_KEYSCAN_BIN, '-H', ip_version, '-p', str(cls.PORT),
                    '-t', 'dsa,rsa,ecdsa', cls.BIND_ADDRESS, ])

                # We check the length of `out` because in case of connection
                # failure, ssh-keyscan still exit with 0, but spits nothing.
                if 0 != returncode or 0 == len(out):
                    logger.debug("Failed to update {} for IPv{}:\n==stderr=="
                                 "\n{}\n==stdout==\n{}\n=========="
                                 .format(cls._KNOWN_HOSTS_PATH,
                                         ip_version[1],
                                         err,
                                         out))
                    failures.append((out, err))
                else:
                    # Seems we got what we need, save it.
                    logger.debug(
                        "Appending new IPv{} host(s) public keys to {}:\n{}"
                        .format(ip_version[1], cls._KNOWN_HOSTS_PATH, out))
                    known_hosts.write(out)
        # Only report an error if both IPv4 and IPv6 scan failed
        if len(failures) == 2:
            cls._errors['_update_user_known_hosts'] = (
                'ssh-keyscan failed with status {}: {}\nOutput: {}'
                .format(returncode, err, out))  # keyscanner.

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
        path = cls.SSH_BASEDIR
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
            logger.debug(_("Restoring permissions on `{}' to {}.")
                         .format(directory, oct(mode)))
            try:
                os.chmod(directory, mode)
            except _PermissionError:
                subprocess.call([
                    'sudo', 'chmod', cls._mode2string(mode), directory,
                ])
            else:
                logger.warning(_("Could not restore mode of `{}' to {}.")
                               .format(directory, oct(mode)))

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
        pc_met = cls._check_dir(res.pw_dir)
        pc_met = cls._check_dir(os.path.dirname(cls._SSH_CONFIG_PATH)) \
            and pc_met
        pc_met = cls._check_dir(os.getcwd()) and pc_met
        pc_met = cls._check_dir(cls.SSH_BASEDIR) and pc_met
        pc_met = cls._check_auxiliary_program(cls.SSHD_BIN) and pc_met
        pc_met = cls._check_auxiliary_program(cls.SSH_KEYSCAN_BIN) and pc_met
        pc_met = cls._check_auxiliary_program(cls.SSH_KEYGEN_BIN) and pc_met
        if not pc_met:
            cls._skip()

    @classmethod
    def _debug(cls, out, err, client):
        if os.getenv("PYTHON_DEBUG"):
            hexerr = StringIO()
            hexout = StringIO()
            hexdump(err, file=hexerr)
            hexdump(out, file=hexout)

            logger.debug("Test `{test}' ended with status {status}:\n\n"
                         "==STDERR==\n{err}\n{hexerr}\n\n==STDOUT==\n{out}\n"
                         "{hexout}\n"
                         .format(
                             test='test_git_pull_from_read_write_repo',
                             out=out,
                             err=err,
                             hexout=hexout.getvalue(),
                             hexerr=hexerr.getvalue(),
                             status=client.returncode))

    @classmethod
    def setUpClass(cls):
        """Sets up the environment to start-up an SSH daemon and access it.

        This functions keep thing at a high level calling a method for each
        required step.
        """
        cls._OLD_LANG = os.environ.get('LANG', None)
        os.environ['LANG'] = 'C'

        if 'SSH_HARNESS_DEBUG' in os.environ:
            logger.setLevel(logging.DEBUG)
        cls._logger = logger

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
    def runCommand(cls, cmd, input=None):
        if isinstance(input, str) and (3, 0, 0, ) <= sys.version_info:
            input = input.encode('utf-8')
        logger.debug(_("Executing command: `'{}").format(' '.join(cmd)))
        proc = subprocess.Popen(cmd,
                                env=os.environ,
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        (out, err) = proc.communicate(input=input)
        if (3, 0, 0) <= sys.version_info:
            # In Python 3.x subprocess module return bytes not string.
            err = err.decode(_ENCODING)
            out = out.decode(_ENCODING)
        cls._debug(out, err, proc)
        return proc.returncode, out, err

    @classmethod
    def runCommandWarnIfFails(cls, cmd, action, input=None):
        retval, out, err = cls.runCommand(cmd, input=input)
        if retval:
            warnings.warn(
                '{} operation failed ({:d}):\n'
                '{}'.format(action,
                            retval,
                            err  # .encode(_ENCODING)
                            ),
                UserWarning)
        return retval

    @classmethod
    def tearDownClass(cls):
        if cls._OLD_LANG is not None:
            os.environ['LANG'] = cls._OLD_LANG
        # If the server was started.
        if cls._SSHD is not None:
            cls._kill_sshd()

        for f in cls._FILES.keys():
            file = getattr(cls, '{}_PATH'.format(f), None)
            if file is None:
                continue  # File was not created for some reason

            if file.endswith('.pid'):
                continue  # sshd.pid is normally deleted by sshd when it exits.
            cls._delete_file(file)
            if f.endswith('_KEY'):
                # Don't forget to remove the public key along with the
                # private one.
                file = '{}.pub'.format(file)
                cls._delete_file(file)

        BackupEditAndRestore.clear_context(cls._context_name)

        # Now that we destroyed all keys we can restore the modes of the
        # directories that were along their path.
        cls._restore_modes()


class PubKeyAuthSshClientTestCase(BaseSshClientTestCase):

    USE_AUTH_METHOD = BaseSshClientTestCase.AUTH_METHOD_PUBKEY


class PasswdAuthSshClientTestCase(BaseSshClientTestCase):

    USE_AUTH_METHOD = BaseSshClientTestCase.AUTH_METHOD_PASSWORD


# vim: syntax=python:sws=4:sw=4:et:
