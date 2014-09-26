# -*- coding: utf-8-unix; -*-
from __future__ import print_function
from unittest import TestCase
import errno
import os
import shutil
import signal
import stat
import subprocess


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
        os.getcwd(), 'tests', 'fixtures', 'sshd', ])

    AUTH_METHOD_PASSWORD = (True, False, )
    AUTH_METHOD_PUBKEY = (False, True, )
    PORT = 2200
    BIND_ADDRESS = '127.0.0.1'

    USE_AUTH_METHOD = None

    SSHD_BIN = '/usr/sbin/sshd'
    SSH_KEYSCAN_BIN = '/usr/bin/ssh-keyscan'
    SSH_KEYGEN_BIN = '/usr/bin/ssh-keygen'
    SSH_CONFIG_HOST_NAME = 'test-harness'
    UPDATE_SSH_CONFIG = True

    AUTHORIZED_KEY_OPTIONS = None

    _FILES = {
        'HOST_ECDSA_KEY': 'host_ssh_ecdsa_key',
        'HOST_DSA_KEY': 'host_ssh_dsa_key',
        'HOST_RSA_KEY': 'host_ssh_rsa_key',
        'USER_RSA_KEY': 'id_rsa',
        'AUTHORIZED_KEYS': 'authorized_keys',
        'SSHD_CONFIG': 'sshd_config',
        'SSHD_PIDFILE': 'sshd.pid',
        }
    _KEY_FILES_MODE = 0x00000000 | stat.S_IRUSR
    # The sizes of the key to ask with respect to their type (we purposely
    # request the weakest key sizes possible to not slow the test cases too
    # much)
    _BITS = {
        'dsa': '1024',
        'rsa': '768',
        'ecdsa': '256',
        }
    _AUTH_METHODS = ('password_auth', 'pubkey_auth', )
    _SSH_CONFIG_PATH = os.path.expanduser('~/.ssh/config')
    _SSH_CONFIG_OPEN_TAG= '# BEGIN TEST-HARNES CONFIG'
    _SSH_CONFIG_CLOSE_TAG= '# END TEST-HARNES CONFIG'
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
PermitUserEnvironment yes

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
    def _guess_key_type(cls, name):
        if 'ECDSA' in name:
            return 'ecdsa'
        elif 'DSA' in name:
            return 'dsa'
        else:
            return 'rsa'

    @classmethod
    def _delete_file(cls, file):
        # print("  {} ... ".format(file), end='')
        if os.path.isfile(file) is True:
            with open(file, 'r') as fd:
                data = fd.read()
            os.unlink(file)
            # print("done.")
            # print(data)
        else:
            # print("does not exist.")
            pass

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
    def _generate_authzd_keys_file(cls):
        # Generate the authorized_key file with the newly created key in it.
        with open(cls.AUTHORIZED_KEYS_PATH, 'w') as authzd_file:
            with open('{}.pub'.format(cls.USER_RSA_KEY_PATH), 'r') as user_key:
                key = user_key.read()
            if cls.AUTHORIZED_KEY_OPTIONS is not None:
                authzd_file.write("{} ".format(cls.AUTHORIZED_KEY_OPTIONS))
            authzd_file.write("{}\n".format(key))

    @classmethod
    def _generate_sshd_config(cls, args):
        with open(cls.SSHD_CONFIG_PATH, 'w') as f:
            f.write(cls._SSHD_CONFIG.format(**args))

    @classmethod
    def _gather_data(cls):
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

        return args

    @classmethod
    def _start_sshd(cls):
        # Start the SSH daemon
        cls._SSHD = subprocess.call([
            '/usr/sbin/sshd', '-4', '-f', cls.SSHD_CONFIG_PATH])
        assert 0 == cls._SSHD

    @classmethod
    def _update_ssh_config(cls, args):
        if cls.UPDATE_SSH_CONFIG is False:
            return
        with open(cls._SSH_CONFIG_PATH, 'a') as user_config:
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
        try:
            os.rename(restored_path, cls._SSH_CONFIG_PATH)
        except OSError as e:
            try:
                # For windows.
                os.remove(cls._SSH_CONFIG_PATH)
                os.rename(restored_path, cls._SSH_CONFIG_PATH)
            except OSError:
                pass

    @classmethod
    def _update_user_known_hosts(cls):
        """Updates the user's `~/.ssh/known_hosts' file to prevent to be
        prompted to validate the server's host key.

        The original file is backed-up so it can be restored upon tests
        completion.
        """
        cls._HAVE_KNOWN_HOSTS = False
        cls._KNOWN_HOSTS_PATH = os.path.expanduser('~/.ssh/known_hosts')
        if os.path.isfile(cls._KNOWN_HOSTS_PATH):
            shutil.copyfile(cls._KNOWN_HOSTS_PATH,
                            '{}.back'.format(cls._KNOWN_HOSTS_PATH))
            cls._HAVE_KNOWN_HOSTS = True
        with open(cls._KNOWN_HOSTS_PATH, 'ab') as known_hosts:
            with open('/dev/null', 'a') as DEVNULL:
                keyscanner = subprocess.Popen([
                    'ssh-keyscan', '-H4', '-p', str(cls.PORT),
                    cls.BIND_ADDRESS, ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE)
                (out, errout) = keyscanner.communicate()
                known_hosts.write(out)
                if keyscanner.returncode is None:
                    pass  # !!
                elif 0 != keyscanner.returncode:
                    print('SSH-KEYSCAN failed with return code {} and error '
                          'output:\n{}'.format(keyscanner.returncode,
                                               errout))

    @classmethod
    def setUpClass(cls):
        args = cls._gather_data()
        cls._generate_sshd_config(args)
        cls._generate_keys()
        cls._generate_authzd_keys_file()
        cls._start_sshd()

        if cls.UPDATE_SSH_CONFIG is True:
            cls._update_ssh_config(args)

        # We use ssh-keyscan and thus need SSHD to be up and running.
        cls._update_user_known_hosts()

    @classmethod
    def tearDownClass(cls):
        if cls._HAVE_KNOWN_HOSTS:
            # Restore backed-up ~/.ssh/known_hosts file.
            shutil.move('{}.back'.format(cls._KNOWN_HOSTS_PATH),
                        cls._KNOWN_HOSTS_PATH)
        else:
            # Or remove it if the file did not exists before.
            os.path.unlink(cls._KNOWN_HOSTS_PATH)

        try:
            with open(cls.SSHD_PIDFILE_PATH, 'r') as pidfile:
                daemon_pid = int(pidfile.read())
            os.kill(daemon_pid, signal.SIGTERM)
        except IOError as e:
            if errno.ENOENT == e.errno:
                pass  # Assuming server died (which is not ok... but for now)
            else:
                raise

        for f in cls._FILES.keys():
            file = getattr(cls, '{}_PATH'.format(f))
            if file.endswith('.pid'):
                continue
            cls._delete_file(file)
            if f.endswith('_KEY'):
                file = '{}.pub'.format(getattr(cls, '{}_PATH'.format(f)))
                cls._delete_file(file)
        if cls.UPDATE_SSH_CONFIG is True:
            cls._restore_ssh_config()


class PubKeyAuthSshClientTestCase(BaseSshClientTestCase):

    USE_AUTH_METHOD = BaseSshClientTestCase.AUTH_METHOD_PUBKEY


class PasswdAuthSshClientTestCase(BaseSshClientTestCase):

    USE_AUTH_METHOD = BaseSshClientTestCase.AUTH_METHOD_PASSWORD


# class SshClientTestCase(TestCase):

#     SSHD_PORT = 2200
#     SSHD_BIND_ADDRESS = 'localhost'
#     SSHD_PUBLIC_KEY = './sshd/id_rsa.pub'
#     SSHD_PRIVATE_KEY = './sshd/id_rsa'
#     sshd_user_public_keys = ['~/.ssh/id_rsa.pub',
#                              '~/.ssh/id_dsa.pub',
#                              ]

#     def setUp(self):
#         # import sshd
#         sshd_path = os.path.dirname(
#             getattr(sshd, '__source__',
#                     getattr(sshd, '__file__', None)))
#         print("SSHD Module Path: {}".format(sshd_path))
#         command = ['python', '-m', 'sshd', ]
#         if self.SSHD_PORT is not None:
#             command += ['-p', str(self.SSHD_PORT), ]
#         if self.SSHD_BIND_ADDRESS is not None:
#             command += ['-b', self.SSHD_BIND_ADDRESS, ]
#         if self.SSHD_PUBLIC_KEY:
#             command += ['-k', self.SSHD_PUBLIC_KEY, ]
#         if self.SSHD_PRIVATE_KEY is not None:
#             command += ['-K', self.SSHD_PRIVATE_KEY, ]

#         # if 0 == os.fork():
#             # self._sshd = subprocess.Popen(command,
#             #                           cwd=sshd_path)
#             # self._sshd.communicate()
#             # print(self._sshd)
#         #     pass
#         # else:
#         time.sleep(1)

#     def tearDown(self):
#         # if self._sshd.returncode is None:
#         #     print("Terminate -> {}".format(self._sshd.terminate()))
#         # self._sshd.wait()
#         # print("SSHD return code: {}".format(self._sshd.returncode))
#         pass

#     def test_ssh_connection(self):
#         p = subprocess.Popen(['ssh', '-p', str(self.SSHD_PORT), 'ncaniart@amboss', ],
#                              stdin=subprocess.PIPE,
#                              stdout=subprocess.PIPE,
#                              stderr=subprocess.PIPE,
#                              shell=False)
#         out, err = p.communicate(input='\x04\r\n')
#         print("Standard output:\n\033[1;35m{}\033[0m"
#               "Standard error:\n\033[1;35m{}\033[0m".format(out, err))
#         print("Return code: {}".format(p.returncode))
#         # print("SSHD return code: {}".format(self._sshd.returncode))        


# vim: syntax=python:sws=4:sw=4:et:
