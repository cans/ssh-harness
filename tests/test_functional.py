# -*- coding: utf-8-unix; -*-
#
#  Copyright © 2014, Nicolas CANIART <nicolas@caniart.net>
#
#  This file is part of vs-ssh.
#
#  vs-ssh is free software: you can redistribute it and/or modify
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
import os
import shutil
import subprocess
from tempfile import mkdtemp
import warnings
import re
import sys

from ssh_harness import PubKeyAuthSshClientTestCase, BackupEditAndRestore


__ALL__ = [
    '']

_GIT_CONFIG_TEMPLATE = '''[user]
        name = Test User
        email = test@example.com
[color]
        ui = auto
[push]
        default = simple
'''

_HG_CONFIG_TEMPLATE = '''[ui]
username = Test User <test@example.com>
'''

MODULE_PATH = os.path.abspath(os.path.dirname(__file__))
PACKAGE_PATH = os.path.dirname(MODULE_PATH)
TEMP_PATH = os.path.join(MODULE_PATH, 'tmp')

# BEGIN TO BE REMOVED

# Deal with the varying expectation of the methods of the various
# StringIO implementations. Used as follows, they can accept str arguments
# both under Python 2 and Python 3 (Py2 io.String only accepts unicode args).
if (3, 0, 0, ) > sys.version_info:
    from StringIO import StringIO
else:
    from io import StringIO
import string
_EOL = u'\r\n'
_realprintable = None


def hexdump(buf, file=sys.stdout):
    global _realprintable, _EOL
    if _realprintable is None:
        _realprintable = [x for x in string.printable if x not in '\t\n\r\v\f']
    octets = ''
    i = 0

    if isinstance(buf, bytes):
        # Py2/Py3 compatibility
        buf = buf.decode('utf-8')

    for i, byte in enumerate(buf):
        if 0 == i % 16:
            if i > 0:
                file.write('|{}|{}'.format(octets, _EOL))
            octets = ''
            file.write('{:08x}  '.format(i))
        file.write('{:02x} '.format(ord(byte)))
        octets += '.' if byte not in _realprintable else byte
        if 7 == i % 8:
            file.write(' ')
            if 15 != i % 16:
                octets += ' '

    if i > 0 and '' != octets:
        remainder = i % 16 + 1
        file.write(' ' * (((16 - remainder) * 3) + (2 - int(len(octets)/8))))
        file.write('|{}|{}'.format(octets, _EOL))
        i += 1
    file.write(u'{:08x}{}'.format(i, _EOL))
# END TO BE REMOVED


def double_slash(path, name):
    if name.endswith('_hg'):
        return '/{}'.format(path)
    return path


def maybe_bytes(ref, mystr):
    """When run with Python >=3, converts string to bytes (assumes your string
    is a literal and your source is utf-8 encoded).
    """
    # If Py < 3, bytes == str (at least with 2.7)
    if isinstance(ref, bytes) and str != bytes:
        return bytes(mystr, encoding='utf-8')
    return mystr


class InThrowableTempDir(object):
    """
    Context manager that puts your program in a pristine temporary directory
    upon entry and puts you back where you were upon exit. It also cleans
    the temporary directory
    """

    def __init__(self, suffix='', prefix='throw-', dir=None):
        if not os.path.isdir(dir):
            # Py3 uses 0o700 for octal not plain 0700 (where the fuck did
            # that come from!)
            os.makedirs(dir, mode=448)

        # to make sure mkdtemp returns an absolute path which it may not
        # if given a relative path as its :param:`dir` keyword-argument.
        # It is important to prevent removing a directory that is not the
        # one we intended to when exiting the context manager.
        dir = os.path.abspath(dir)
        self._dir = mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
        self._oldpwd = None

    @property
    def path(self):
        """Path to the temporary directory created by the context manager."""
        return self._dir

    @property
    def old_path(self):
        """Path

        .. note::

           This attribute value will remain `None` until you enter the context.
        """
        return self._oldpwd

    def __enter__(self):
        if os.getcwd() != self._dir:
            self._oldpwd = os.getcwd()
            os.chdir(self._dir)
        else:
            warnings.warn(
                "Already in the temporary directory !",
                UserWarning)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.chdir(self._oldpwd)

        def ignore(f, p, e):
            pass

        shutil.rmtree(self._dir,
                      ignore_errors=False,
                      onerror=ignore)

        if exc_type is not None:
            return False
        return True


class VcsSshIntegrationTestCase(PubKeyAuthSshClientTestCase):
    """
    ==Methods nomenclature==

    Methods related to VCS like :meth:`_commit` or :meth:`_do_commit` are
    helpers that abstract away the details of each individual VCS.

    The difference between the methods with or without `_do` prefix is the
    following:

    - methods *with* a ``_do`` prefix assume you are in the working copy
      directory
    - methods *without* the prefix put you in the working copy directory
      if you were not, before doing anything and put you back were you
      were before they return.

    .. todo::

       - Make use of the cwd keyword-argument of the subprocess functions
         instead os using the _enter/leave_working_copy() methods.
    """

    _REPOSITORIES = {
        'ro_git': 'fixtures/git-ro.git',
        'rw_git': 'fixtures/git-rw.git',
        'ro_hg': 'fixtures/hg-ro',
        'rw_hg': 'fixtures/hg-rw',
        'ro_svn': 'fixtures/svn-ro',
        'rw_svn': 'fixtures/svn-rw',
        'rw_bzr': 'fixtures/bzr-rw',
        }
    """The list of repositories we create for our tests on per access mode (ro, rw)
       and handled VCS type

    Each value corresponds a fixture repository to be created.

    Also, each item in the dictionary is used to generate class attributes in
    the :meth:`setUpClass`. Three of them are created per item in the
    dictionary:

    - ``_<uppercased key>_PATH``: the absolute path to the repository;
    - ``_<uppercased key>_URL``: a ssh: scheme url to access the repository
      *remotely* via ssh;
    - ``_<uppercased key>_LOCAL``, e.g. ``_RO_GIT_LOCAL``: a file: scheme url
      to access the repository locally (required by svn; hg, git or bzr could
      do without this);
    """

    SSH_ENVIRONMENT = {
        'COVERAGE_PROCESS_START': os.path.join(PACKAGE_PATH, '.coveragerc'),
        'COVERAGE_FILE': os.path.join(PACKAGE_PATH, '.coverage'),
        'PYTHONPATH': PACKAGE_PATH,
        # 'COVERAGE_OPTIONS': '--source={} -p '.format(
        #     ','.join([
        #         os.path.join(PACKAGE_PATH, 'vcs-ssh'),
        #         os.path.join(PACKAGE_PATH, 'vcs_ssh.py'),
        #         ])),
        }

    VCS = {
        'HG': ('/usr/bin/hg', ),
        'GIT': ('/usr/bin/git', ),
        'SVN': ('/usr/bin/svn', '/usr/bin/svnadmin', ),
        'BZR': ('/usr/bin/bzr', ),
        }

    @classmethod
    def _get_program_version(cls):
        rex = re.compile('(?:.*version )(?P<version>(:?\d+\.?)+)(?:.*)'
                         .encode('utf-8'))
        for vcs, v in cls.VCS.items():
            attr = '{}_VERSION'.format(vcs)
            if getattr(cls, 'HAVE_{}'.format(vcs), False):
                out = subprocess.check_output([v[0], '--version'])
                out = out.splitlines()[0]
                match = rex.search(out)
                if match is not None:
                    setattr(cls,
                            attr,
                            tuple([int(x)
                                   for x in match.groupdict()['version'].split(
                                       '.'.encode('utf-8'))
                                   ]))
                else:
                    # bazaar
                    out.split()[-1]
                    setattr(cls, attr, None)

    @classmethod
    def _update_vcs_config(cls):
        global _GIT_CONFIG_TEMPLATE, _HG_CONFIG_TEMPLATE
        with BackupEditAndRestore(os.path.expanduser('~/.gitconfig'),
                                  'a') as gitconfig:
            gitconfig.write(_GIT_CONFIG_TEMPLATE)
        cls._add_file_to_restore(gitconfig)

        with BackupEditAndRestore(os.path.expanduser('~/.hgrc'), 'a') as hgrc:
            hgrc.write(_HG_CONFIG_TEMPLATE)
        cls._add_file_to_restore(hgrc)

    @classmethod
    def setUpClass(cls):
        # We want all programs output to be in 'C' locale (makes output
        # independant of the user's environment)
        os.putenv('LANG', 'C')  # TODO: not reset on tests completion
        read_only_repos = []
        read_write_repos = []

        # Some preconditions:
        cls.HAVE_BZR = cls._check_auxiliary_program('/usr/bin/bzr',
                                                    error=False)
        cls.HAVE_HG = cls._check_auxiliary_program('/usr/bin/hg', error=False)
        cls.HAVE_GIT = cls._check_auxiliary_program('/usr/bin/git',
                                                    error=False)
        cls.HAVE_SVN = cls._check_auxiliary_program('/usr/bin/svn',
                                                    error=False)
        cls.HAVE_SVNADMIN = cls._check_auxiliary_program('/usr/bin/svnadmin',
                                                         error=False)

        # Use this to keep track of commits.
        cls._COMMIT = 0

        for name, path in cls._REPOSITORIES.items():
            upper_name = name.upper()
            path_attr = '_{}_PATH'.format(upper_name)
            url_attr = '_{}_URL'.format(upper_name)
            local_attr = '_{}_LOCAL'.format(upper_name)

            local_scheme = 'file://'
            if name.endswith('_git'):
                # otherwise Git is confused when trying a push
                local_scheme = ''

            url_scheme = 'ssh'
            if name.endswith('_bzr'):
                url_scheme = 'bzr+' + url_scheme
            elif name.endswith('_svn'):
                url_scheme = 'svn+' + url_scheme

            setattr(cls, path_attr, os.path.join(MODULE_PATH, path))
            if cls.UPDATE_SSH_CONFIG is False:
                # Forces us of address + port syntax
                setattr(cls, url_attr,
                        '{scheme}://{address}:{port}{path}'.format(
                            path=double_slash(getattr(cls, path_attr), name),
                            address=cls.BIND_ADDRESS,
                            port=cls.PORT,
                            scheme=url_scheme))
            else:
                setattr(cls, url_attr,
                        '{scheme}://{ssh_config_host_name}{path}'.format(
                            path=double_slash(getattr(cls, path_attr), name),
                            ssh_config_host_name=cls.SSH_CONFIG_HOST_NAME,
                            scheme=url_scheme))

            setattr(cls, local_attr,
                    '{scheme}{path}'.format(
                        scheme=local_scheme,
                        path=getattr(cls, path_attr)))

            if name.startswith('ro_'):
                read_only_repos.append(getattr(cls, path_attr))

            elif name.startswith('rw_'):
                read_write_repos.append(getattr(cls, path_attr))

            else:
                warnings.warn(UserWarning, "...")
                pass

            if name.endswith('_git') and cls.HAVE_GIT:
                cmd = ['git', 'init', '--bare', '-q',
                       getattr(cls, path_attr), ]
            elif name.endswith('_hg') and cls.HAVE_HG:
                cmd = ['hg', 'init', getattr(cls, path_attr), ]
            elif name.endswith('_svn') and cls.HAVE_SVNADMIN and cls.HAVE_SVN:
                cmd = ['svnadmin', 'create', '--fs-type', 'fsfs',
                       getattr(cls, path_attr), ]
            elif name.endswith('_bzr') and cls.HAVE_BZR:
                cmd = ['bzr', 'init', '--no-tree', getattr(cls, path_attr), ]
            else:
                warnings.warn("!!!", UserWarning)
                pass
            # TODO: check the command exit status, calling init_repository()
            # is pointless if the command failed.
            subprocess.call(cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)

            cls.init_repository(name,
                                getattr(cls, path_attr),
                                getattr(cls, local_attr))

        cls.AUTHORIZED_KEY_OPTIONS = (
            'command="{basedir}/vcs-ssh '
            '--read-write {rw_repos} '
            '--read-only {ro_repos}"').format(
                basedir=PACKAGE_PATH,
                ro_repos=' '.join(read_only_repos),
                rw_repos=' '.join(read_write_repos))

        cls._update_vcs_config()
        cls._get_program_version()
        super(VcsSshIntegrationTestCase, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        super(VcsSshIntegrationTestCase, cls).tearDownClass()
        for name, repo in cls._REPOSITORIES.items():
            path_attr = '_{}_PATH'.format(name.upper())

            shutil.rmtree(getattr(cls, path_attr),
                          ignore_errors=True)

    @classmethod
    def init_repository(cls, name, path, url):
        inst = cls()
        inst.setUp()
        inst._make_a_revision_and_push_it(url, msg="Initial commit.")

    def setUp(self):
        # Used to memoïze repository working copy directory name
        self._repo_basename = None
        # Used to keep track of wether we are in the working copy or not.
        self._OLDPWD = None

    def run(self, result=None):
        """
        Override the run method so that tests are each run within a pristine
        temporary directory.
        """
        global TEMP_PATH
        # self.setUp() has not been called yet.
        self._tempdir = InThrowableTempDir(dir=TEMP_PATH)
        with self._tempdir:
            return super(VcsSshIntegrationTestCase, self).run(result=result)

    if (3, 0, 0, ) > sys.version_info:
        """Hack to make the _init_repository() work: it creates a TestCase instance and
        python 2.7.8 requires that method to exists (we dont use it but...)"""
        runTest = run

    def _debug(self, out, err, client):
        if os.getenv("PYTHON_DEBUG"):
            hexerr = StringIO()
            hexout = StringIO()
            hexdump(err, file=hexerr)
            hexdump(out, file=hexout)

            print("Test `{test}' ended with status {status}:\n\n"
                  "==STDERR==\n{err}\n{hexerr}\n\n==STDOUT==\n{out}\n"
                  "{hexout}\n"
                  .format(
                      test='test_git_pull_from_read_write_repo',
                      out=out,
                      err=err,
                      hexout=hexout.getvalue(),
                      hexerr=hexerr.getvalue(),
                      status=client.returncode))

    def _basename(self, url):
        if self._repo_basename is None:
            self._repo_basename = os.path.basename(url)
            if self._repo_basename.endswith('.git'):
                self._repo_basename = self._repo_basename[0:-4]
        return self._repo_basename

    def _clone(self, url):
        repo_basename = self._basename(url)
        if repo_basename.startswith('git-'):
            cmd = ['git', 'clone', url, ]
        elif repo_basename.startswith('hg-'):
            cmd = ['hg', 'clone', url, ]
        elif repo_basename.startswith('svn-'):
            cmd = ['svn', 'checkout', url, ]
        elif repo_basename.startswith('bzr-'):
            cmd = ['bzr', 'branch', url, ]
        return subprocess.call(cmd,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)

    def _enter_working_copy(self, url, path=None):
        if path is None:
            path = self._tempdir.path
        if not path == os.getcwd():
            raise Exception('Not where I should be')
        repo_basename = self._basename(url)
        os.chdir(repo_basename)

    def _leave_working_copy(self, path=None):
        if path is None:
            path = self._tempdir.path
        os.chdir(path)

    def _do_add(self):
        if os.path.isdir('./.git'):
            cmd = ['git', 'add', 'content', ]
        elif os.path.isdir('./.hg'):
            cmd = ['hg', 'add', 'content', ]
        elif os.path.isdir('./.svn'):
            cmd = ['svn', 'add', 'content', ]
        elif os.path.isdir('./.bzr'):
            cmd = ['bzr', 'add', 'content', ]
        else:
            return 1
        return subprocess.call(cmd,
                               stderr=subprocess.PIPE,
                               stdout=subprocess.PIPE)

    def _do_content(self):
        if os.path.isfile('./content') is False:
            with open('./content', 'w+') as f:
                f.write('{}'.format(self.__class__._COMMIT))
        else:
            self.__class__._COMMIT += 1
            with open('./content', 'w') as f:
                f.write('{}'.format(self.__class__._COMMIT))
        return self.__class__._COMMIT

    def _do_commit(self, msg=None):
        self._do_add()
        default = "commit without a description"
        if os.path.isdir('./.git'):
            cmd = ['git', 'commit', '-m', msg or default, ]
        elif os.path.isdir('./.hg'):
            cmd = ['hg', 'commit', '-m', msg or default, ]
        elif os.path.isdir('./.svn'):
            cmd = ['svn', 'commit', '-m', msg or default, ]
        elif os.path.isdir('./.bzr'):
            cmd = ['bzr', 'commit', '-m', msg or default, ]
        else:
            return 1
        return subprocess.call(cmd,
                               stderr=subprocess.PIPE,
                               stdout=subprocess.PIPE)

    def _commit(self, url, expect=None, path=None, msg=None):
        self._enter_working_copy(url, path=path)
        res = self._do_commit(msg=msg)
        self._leave_working_copy(url)
        return res

    def _do_push(self):
        if os.path.isdir('./.git'):
            cmd = ['git', 'push', 'origin', 'master', ]
        elif os.path.isdir('./.hg'):
            cmd = ['hg', 'push', ]
        elif os.path.isdir('./.svn'):
            return 0  # Their is no such things as `push' in subversion.
        elif os.path.isdir('./.bzr'):
            # TODO: review this
            cmd = ['bzr', 'push', ':parent', ]
        else:
            return 1
        return subprocess.call(cmd,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)

    def _push(self, url, path=None):
        self._enter_working_copy(url, path=path)
        cmt_res = self._do_commit(url)
        psh_res = self._do_push()
        self._leave_working_copy(path=path)
        return cmt_res or psh_res  # If 0 then both are -> both succeeded.

    def _do_make_a_revision(self, expect=None, msg=None):
        content = self._do_content()
        if expect is not None:
            self.assertEqual(content, expect)
        res = self._do_commit(msg=msg)

        return res

    def _make_a_revision(self, url, path=None, msg=None):
        self._clone(url)
        self._enter_working_copy(url, path=path)
        res = self._do_make_a_revision(msg=msg)
        self._leave_working_copy(path=path)
        return res

    def _make_a_revision_and_push_it(self, url, msg=None):
        global TEMP_PATH
        with InThrowableTempDir(dir=TEMP_PATH) as d:
            self._clone(url)
            self._enter_working_copy(url, path=d.path)
            rev_res = self._do_make_a_revision(msg=msg)
            psh_res = self._do_push()
            self._leave_working_copy(path=d.path)
            return rev_res and psh_res

    # -- Git related tests ----------------------------------------------------

    def test_git_clone_from_read_only_repo(self):
        if not self.HAVE_GIT:
            self.skipTest('Git is not available')
        cmd = ['git', 'clone', self._RO_GIT_URL, ]

        client = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, err = client.communicate()

        self.assertEqual(client.returncode, 0)

    def test_git_clone_from_read_write_repo(self):
        if not self.HAVE_GIT:
            self.skipTest('Git is not available')
        cmd = [
            'git',
            'clone',
            self._RW_GIT_URL,
            ]
        client = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, err = client.communicate()

        self.assertEqual(client.returncode, 0)

    def test_git_pull_from_read_only_repo(self):
        if not self.HAVE_GIT:
            self.skipTest('Git is not available')
        # First we clone the repo as it is.
        self._clone(self._RO_GIT_URL)
        cmd = [
            'git',
            'pull',
            ]

        # Then we add something to pull to the repository (by
        # making a new revision in another, local, working copy)
        self._make_a_revision_and_push_it(self._RO_GIT_LOCAL)

        self._enter_working_copy(self._RO_GIT_URL)
        client = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, err = client.communicate()
        self._leave_working_copy()

        self._debug(out, err, client)

        self.assertEqual(client.returncode, 0)

        self.assertRegexpMatches(
            err,
            maybe_bytes(
                err,
                'From {}\n'
                '( \* \[new branch\]|'
                '   [0-9a-f]{{7}}\.\.[0-9a-f]{{7}}) +'
                'master     -> origin/master\n'
                .format(self._RO_GIT_URL[:-4])))
        if self.GIT_VERSION < (2, 0, 0):
            self.assertEqual(out, ''.encode('utf-8'))
        else:
            self.assertRegexpMatches(
                out,
                re.compile(
                    maybe_bytes(out,
                                'Updating [0-f]{7}\.\.[0-f]{7}\n'
                                'Fast-forward\n.*'),
                    re.S))

    def test_git_pull_from_read_write_repo(self):
        if not self.HAVE_GIT:
            self.skipTest('Git is not available')
        # First we clone the repo as it is.
        self._clone(self._RW_GIT_URL)

        cmd = [
            'git',
            'pull',
            ]

        # Then we add something to pull to the repository (by
        # making a new revision in another, local, working copy)
        self._make_a_revision_and_push_it(self._RW_GIT_LOCAL)

        self._enter_working_copy(self._RW_GIT_URL)
        client = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, err = client.communicate()
        self._leave_working_copy()

        self._debug(out, err, client)

        self.assertEqual(client.returncode, 0)
        self.assertRegexpMatches(
            err,
            re.compile(
                maybe_bytes(
                    err,
                    'From {}\n( \* \[new branch\]|   [0-9a-f]{{7}}\.\.'
                    '[0-9a-f]{{7}}) +master     -> origin/master'
                    .format(self._RW_GIT_URL[:-4])),
                re.S))
        self.assertRegexpMatches(
            out,
            re.compile(
                maybe_bytes(out,
                            'Updating [0-f]{7}\.\.[0-f]{7}\n'
                            'Fast-forward\n.*'),
                re.S))

    def test_git_push_to_read_write_repo(self):
        # Have to make a remote clone or the push would be local (slow i know).
        self._make_a_revision(self._RW_GIT_URL)

        cmd = [
            'git',
            'push',
            self._RW_GIT_URL,
            ]

        self._enter_working_copy(self._RW_GIT_URL)
        client = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, err = client.communicate()
        self._leave_working_copy()

        self._debug(out, err, client)

        self.assertEqual(client.returncode, 0)
        self.assertEqual(out, maybe_bytes(out, ''))

        self.assertRegexpMatches(
            err,
            maybe_bytes(err, 'To {}\n   [0-f]{{7}}\.\.[0-f]{{7}}  '
                        'master -> master\n.*'.format(self._RW_GIT_URL)))

    def test_git_push_to_read_only_repo(self):
        if not self.HAVE_GIT:
            self.skipTest('Git is not available')
        # Have to make a remote clone or the push would be local (slow i know).
        self._make_a_revision(self._RO_GIT_URL)

        self._enter_working_copy(self._RO_GIT_URL)
        client = subprocess.Popen([
            'git',
            'push',
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, err = client.communicate()
        self._leave_working_copy()

        self._debug(out, err, client)

        self.assertEqual(client.returncode, 128)
        self.assertEqual(
            err,
            'remote: \x1b[1;41mYou only have read only access to this '
            'repository\x1b[0m: you cannot push anything into it !\n'
            'fatal: Could not read from remote repository.\n\nPlease make sure'
            ' you have the correct access rights\nand the repository exists.\n'
            .encode('utf-8'))
        self.assertEqual(out, ''.encode('utf-8'))

    # -- Mercurial related tests ----------------------------------------------

    def test_hg_clone_from_ro_repository(self):
        if not self.HAVE_HG:
            self.skipTest('Mercurial is not available')
        cmd = ['hg', 'clone', self._RO_HG_URL, ]

        client = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, err = client.communicate()

        self._debug(out, err, client)

        self.assertEqual(client.returncode, 0)
        self.assertTrue(
            os.path.isdir(
                os.path.join(os.getcwd(), self._basename(self._RO_HG_URL))))

    def test_hg_clone_from_rw_repository(self):
        if not self.HAVE_HG:
            self.skipTest('Mercurial is not available')
        cmd = ['hg', 'clone', self._RW_HG_URL, ]

        client = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, err = client.communicate()

        self._debug(out, err, client)

        self.assertEqual(client.returncode, 0)
        self.assertTrue(
            os.path.isdir(
                os.path.join(os.getcwd(), self._basename(self._RW_HG_URL))))

    def test_hg_clone_from_wrong_repository(self):
        if not self.HAVE_HG:
            self.skipTest('Mercurial is not available')
        url = '{}-rubbish'.format(self._RW_HG_URL)
        local = '{}-rubbish'.format(self._RW_HG_PATH)
        cmd = ['hg', 'clone', url, ]

        client = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, err = client.communicate()

        self._debug(out, err, client)

        self.assertEqual(client.returncode, 255)
        self.assertEqual(
            out,
            'remote: Illegal repository "{}"\n'
            .format(local)
            .encode('utf-8'))
        self.assertEqual(err,
                         'abort: no suitable response from remote hg!\n'
                         .encode('utf-8'))

    def test_hg_pull_from_ro_repository(self):
        if not self.HAVE_HG:
            self.skipTest('Mercurial is not available')
        # First we clone the repo as it is.
        self._clone(self._RO_HG_URL)

        cmd = [
            'hg',
            'pull',
            '-u',
            ]

        # Then we add something to pull to the repository (by
        # making a new revision in another, local, working copy)
        self._make_a_revision_and_push_it(self._RO_HG_LOCAL)

        self._enter_working_copy(self._RO_HG_URL)
        client = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, err = client.communicate()
        self._leave_working_copy()

        self._debug(out, err, client)

        self.assertEqual(client.returncode, 0)
        self.assertEqual(err, ''.encode('utf-8'))
        self.assertRegexpMatches(
            out,
            re.compile(
                'pulling from {}\n(searching for|requesting all) changes\n'
                'adding changesets\nadding manifests\nadding file changes\n'
                'added \d+ changesets with \d+ changes to \d+ files\n'
                '\d+ files updated, \d+ files merged, \d+ files removed, '
                '\d+ files unresolved\n'
                ''.format(self._RO_HG_URL).encode('utf-8'),
                re.S))

    def test_hg_pull_from_rw_repository(self):
        if not self.HAVE_HG:
            self.skipTest('Mercurial is not available')
        # First we clone the repo as it is.
        self._clone(self._RW_HG_URL)

        cmd = [
            'hg',
            'pull',
            '-u',
            ]

        # Then we add something to pull to the repository (by
        # making a new revision in another, local, working copy)
        self._make_a_revision_and_push_it(self._RW_HG_LOCAL)

        self._enter_working_copy(self._RW_HG_URL)
        client = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, err = client.communicate()
        self._leave_working_copy()

        self._debug(out, err, client)

        self.assertEqual(client.returncode, 0)
        self.assertEqual(err, ''.encode('utf-8'))
        self.assertRegexpMatches(
            out,
            re.compile(
                'pulling from {}\n(searching for|requesting all) changes\n'
                'adding changesets\nadding manifests\nadding file changes\n'
                'added \d+ changesets with \d+ changes to \d+ files\n'
                '\d+ files updated, \d+ files merged, \d+ files removed, '
                '\d+ files unresolved\n'
                ''.format(self._RW_HG_URL).encode('utf-8'),
                re.S))

    def test_hg_push_to_read_only_repository(self):
        if not self.HAVE_HG:
            self.skipTest('Mercurial is not available')
        # Have to make a remote clone or the push would be local (slow i know).
        self._make_a_revision(self._RO_HG_URL)

        self._enter_working_copy(self._RO_HG_URL)
        client = subprocess.Popen([
            'hg',
            'push',
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, err = client.communicate()
        self._leave_working_copy()

        self._debug(out, err, client)

        # Note the double 'remote: ' prefix in the error line (cf. function
        # rejectpush) Not sure why it occurs but it seems out of my control
        # (added somewhere within mercurial's internals).
        self.assertEqual(
            out,
            'pushing to {}\nsearching for changes\n'
            'remote: remote: \x1b[1;41mYou only have read only access to this '
            'repository\x1b[0m: you cannot push anything into it !\n'
            'remote: abort: prechangegroup.hg-ssh hook failed\n'
            .format(self._RO_HG_URL)
            .encode('utf-8'))
        self.assertEqual(err, ''.encode('utf-8'))
        self.assertEqual(client.returncode, 1)

    # TODO: def test_hg_push_to_read_write_repository(self):

    # -- Bazaar related tests -------------------------------------------------

    def test_bzr_branch_from_repository(self):
        if not self.HAVE_BZR:
            self.skipTest('Bazaar is not available')
        cmd = ['bzr', 'branch', self._RW_BZR_URL, ]

        client = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, err = client.communicate()

        self._debug(out, err, client)

        self.assertEqual(client.returncode, 0)
        self.assertTrue(
            os.path.isdir(
                os.path.join(os.getcwd(), self._basename(self._RW_BZR_URL))))

    def test_bzr_pull_from_repository(self):
        if not self.HAVE_BZR:
            self.skipTest('Bazaar is not available')

        self._clone(self._RW_BZR_URL)
        cmd = ['bzr', 'pull', self._RW_BZR_URL, ]

        # Then we add something to pull to the repository (by
        # making a new revision in another, local, working copy)
        self._make_a_revision_and_push_it(self._RW_BZR_LOCAL)

        self._enter_working_copy(self._RW_BZR_URL)
        client = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, err = client.communicate()
        self._leave_working_copy()

        self._debug(out, err, client)

        self.assertEqual(client.returncode, 0)
        self.assertTrue(
            os.path.isdir(
                os.path.join(os.getcwd(), self._basename(self._RW_BZR_URL))))
        self.assertEqual(
            err,
            ' M  content\nAll changes applied successfully.'
            '\nremote: Warning: using Bazaar: no access control enforced!\n'
            .encode('utf-8'))
        self.assertRegexpMatches(
            out,
            re.compile(
                'Now on revision \d+.'
                .format(self._RW_BZR_URL).encode('utf-8'),
                re.S))

    def test_bzr_send_to_repository(self):
        if not self.HAVE_BZR:
            self.skipTest('Bazaar is not available')

        self._clone(self._RW_BZR_URL)
        cmd = ['bzr', 'push', self._RW_BZR_URL, ]

        self._enter_working_copy(self._RW_BZR_URL)
        self._do_make_a_revision()
        client = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, err = client.communicate()
        self._leave_working_copy()

        self._debug(out, err, client)

        self.assertEqual(client.returncode, 0)
        self.assertTrue(
            os.path.isdir(
                os.path.join(os.getcwd(), self._basename(self._RW_BZR_URL))))
        self.assertRegexpMatches(
            err,
            re.compile(
                'Pushed up to revision \d.\n'
                'remote: Warning: using Bazaar: no access control enforced!\n'
                ''.encode('utf-8'),
                re.S))
        self.assertRegexpMatches(
            out,
            re.compile(
                ''.format(self._RW_BZR_URL).encode('utf-8'),
                re.S))

    # -- Basic commands validatation tests ------------------------------------

    def test_ssh_connection_with_command_is_rejected(self):
        # Have to make a remote clone or the push would be local (slow i know).
        self._make_a_revision(self._RW_GIT_URL)

        self._enter_working_copy(self._RW_GIT_URL)
        client = subprocess.Popen([
            'ssh',
            '-T',
            '-p',
            str(self.PORT),
            self.SSH_CONFIG_HOST_NAME,
            '/bin/sh',
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, err = client.communicate(input='exit 0'.encode('utf-8'))
        self._leave_working_copy()

        self._debug(out, err, client)

        self.assertEqual(client.returncode, 255)
        self.assertEqual(err,
                         'remote: Illegal command "/bin/sh"\n'.encode('utf-8'))
        self.assertEqual(out, ''.encode('utf-8'))

    def test_ssh_connection_without_command_is_rejected(self):
        # Have to make a remote clone or the push would be local (slow i know).
        self._make_a_revision(self._RW_GIT_URL)

        self._enter_working_copy(self._RW_GIT_URL)
        client = subprocess.Popen([
            'ssh',
            '-T',
            '-p',
            str(self.PORT),
            self.SSH_CONFIG_HOST_NAME,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, err = client.communicate(input='exit 0'.encode('utf-8'))
        self._leave_working_copy()

        self._debug(out, err, client)

        self.assertEqual(client.returncode, 255)
        self.assertEqual(err,
                         'remote: Illegal command "?"\n'.encode('utf-8'))
        self.assertEqual(out, ''.encode('utf-8'))


# vim: syntax=python:sws=4:sw=4:et:
