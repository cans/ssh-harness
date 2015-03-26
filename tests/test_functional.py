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
from __future__ import print_function
import os
import shutil
import subprocess
import warnings
from locale import getpreferredencoding
import re
import sys

from ssh_harness import PubKeyAuthSshClientTestCase, BackupEditAndRestore
from ssh_harness.contexts import InThrowableTempDir


_GIT_CONFIG_TEMPLATE = '''[user]
        name = Test User
        email = test@example.com
[color]
        ui = auto
[push]
        default = matching
'''

_HG_CONFIG_TEMPLATE = '''[ui]
username = Test User <test@example.com>
'''

_BZR_CONFIG_TEMPLATE = '''[DEFAULT]
email = John Doe <jdoe@example.com>
'''

MODULE_PATH = os.path.abspath(os.path.dirname(__file__))
PACKAGE_PATH = os.path.dirname(MODULE_PATH)
TEMP_PATH = os.path.join(MODULE_PATH, 'tmp')
_ENCODING = getpreferredencoding(do_setlocale=False)


def double_slash(path, name):
    """Mercurial has a peculiar way of formating its URLs: it needs a double slash
    inbetween the host name and the path for the path to be absolute.
    """
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
        'PYTHON_DEBUG': '1',
        'VCS_SSH_DEBUG': '1',
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

    BZR_CONFIG_DIR = os.path.expanduser('~/.bazaar')

    _context_name = 'test_functional'

    @classmethod
    def _get_program_versions(cls):
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
        global _GIT_CONFIG_TEMPLATE, _HG_CONFIG_TEMPLATE, _BZR_CONFIG_TEMPLATE
        with BackupEditAndRestore(cls._context_name,
                                  os.path.expanduser('~/.gitconfig'),
                                  'w') as gitconfig:
            gitconfig.write(_GIT_CONFIG_TEMPLATE)
        # cls._add_file_to_restore(gitconfig)

        with BackupEditAndRestore(cls._context_name,
                                  os.path.expanduser('~/.hgrc'),
                                  'w') as hgrc:
            hgrc.write(_HG_CONFIG_TEMPLATE)
        # cls._add_file_to_restore(hgrc)

        with BackupEditAndRestore(cls._context_name,
                                  os.path.join(cls.BZR_CONFIG_DIR,
                                               'bazaar.conf'),
                                  'w') as bzrrc:
            bzrrc.write(_BZR_CONFIG_TEMPLATE)
        # cls._add_file_to_restore(bzrrc)

    @classmethod
    def init_repository(cls, url):
        """Publish a first revision to the given repository.

        We do this to have more consistent outputs from the different
        vcs we add a first revision to each. Indeed a first commit may
        create a first branch or something, which changes the
        output. And not doing this would make the results expected by
        the tests sensitive to the order in which they are run, which is
        obviously undiserable."""
        inst = cls()
        inst.setUp()

        res = inst._make_a_revision_and_push_it(url, msg="Initial commit.")
        return 0 == res

    @classmethod
    def _create_fixture_repositories(cls):
        for name, path in cls._REPOSITORIES.items():
            upper_name = name.upper()
            path_attr = '_{}_PATH'.format(upper_name)
            local_attr = '_{}_LOCAL'.format(upper_name)

            # Create a HAVE_<REPO BASENAME> flag so we can skip a test if the
            # repotory initialization fails.
            basename = cls._basename(
                getattr(cls, local_attr)).upper().replace('-', '_')
            attr_name = 'HAVE_{}_REPOSITORY'.format(basename)
            if hasattr(cls, attr_name):
                warnings.warn(_("Ambiguous repository name: attribute `{}' "
                                "already set!").format(attr_name),
                              UserWarning)
            setattr(cls, attr_name, False)

            cmd = None
            if name.endswith('_git'):
                if not cls.HAVE_GIT:
                    continue

                cmd = ['git', 'init', '--bare', '-q',
                       getattr(cls, path_attr), ]

            elif name.endswith('_hg'):
                if not cls.HAVE_HG:
                    continue

                cmd = ['hg', 'init', getattr(cls, path_attr), ]

            elif name.endswith('_svn'):
                if not (cls.HAVE_SVNADMIN and cls.HAVE_SVN):
                    continue

                cmd = ['svnadmin', 'create', '--fs-type', 'fsfs',
                       getattr(cls, path_attr), ]

            elif name.endswith('_bzr'):
                if not cls.HAVE_BZR:
                    continue

                cmd = ['bzr', 'init', '--no-tree', getattr(cls, path_attr), ]

            else:
                warnings.warn(
                    "Could not find which VCS use to initialized the "
                    "repository name {} ({}).".format(name, path), UserWarning)
                pass

            if cmd is not None:
                cls.runCommandWarnIfFails(cmd, 'Create')
                setattr(cls,
                        attr_name,
                        cls.init_repository(getattr(cls, local_attr)))

    @classmethod
    def setUpClass(cls):
        # We want all programs output to be in 'C' locale (makes output
        # independant of the user's environment)
        os.putenv('LANG', 'C')

        read_only_repos = []
        read_write_repos = []

        # Use this to keep track of commits.
        cls._COMMIT = 0

        # Computes repositories paths required to set the
        # AUTHORIZED_KEY_OPTIONS member below.
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
                # Forces use of address + port syntax
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

        # Set or update parent class attributes
        cls.AUTHORIZED_KEY_OPTIONS = (
            'command="{basedir}/vcs-ssh '
            '--read-write {rw_repos} '
            '--read-only {ro_repos}"').format(
                basedir=PACKAGE_PATH,
                ro_repos=' '.join(read_only_repos),
                rw_repos=' '.join(read_write_repos))

        super(VcsSshIntegrationTestCase, cls).setUpClass()
        # Any code that is not required to run before the parent method
        # should be run after. This check preconditions and as their name
        # state those are *PRE*-conditions
        cls._get_program_versions()
        cls._update_vcs_config()
        cls._create_fixture_repositories()

    @classmethod
    def _preconditions(cls):
        super(VcsSshIntegrationTestCase, cls)._preconditions()
        pc_met = cls._check_dir(os.path.join(cls.MODULE_PATH, 'tmp'))
        pc_met = cls._check_dir(cls.BZR_CONFIG_DIR)

        # Soft preconditions: they don't fail the test suite, but will
        # condition the execution of some tests.
        cls.HAVE_BZR = cls._check_auxiliary_program('/usr/bin/bzr',
                                                    error=False)
        cls.HAVE_HG = cls._check_auxiliary_program('/usr/bin/hg', error=False)
        cls.HAVE_GIT = cls._check_auxiliary_program('/usr/bin/git',
                                                    error=False)
        cls.HAVE_SVN = cls._check_auxiliary_program('/usr/bin/svn',
                                                    error=False)
        cls.HAVE_SVNADMIN = cls._check_auxiliary_program('/usr/bin/svnadmin',
                                                         error=False)

        if not pc_met:
            self._skip()

    @classmethod
    def tearDownClass(cls):
        super(VcsSshIntegrationTestCase, cls).tearDownClass()
        for name, repo in cls._REPOSITORIES.items():
            path_attr = '_{}_PATH'.format(name.upper())

            shutil.rmtree(getattr(cls, path_attr),
                          ignore_errors=True)

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

    @classmethod
    def _do_basename(cls, url):
        basename = os.path.basename(url)
        if basename.endswith('.git'):
            basename = basename[0:-4]
        return basename

    @classmethod
    def _basename(cls, url):
        if not isinstance(cls, type):
            # Cheat to make the method also work on instances.
            if not hasattr(cls, '_repo_basename'):
                setattr(cls, '_repo_basename', cls._do_basename(url))
            return getattr(cls, '_repo_basename')
        return cls._do_basename(url)

    # -- Basic VCS workflow emulation functions -------------------------------

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
        else:
            return 1

        return self.runCommandWarnIfFails(cmd, 'Checkout/Clone')

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
        return self.runCommandWarnIfFails(cmd, 'Add')

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
        return self.runCommandWarnIfFails(cmd, 'Commit')

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
        return self.runCommandWarnIfFails(cmd, 'Push')

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
            self.skipTest('Git is not available on this system.')
        if not self.HAVE_GIT_RO_REPOSITORY:
            self.skipTest('Git fixture repository could not be created.')

        cmd = ['git', 'clone', self._RO_GIT_URL, ]

        client = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, err = client.communicate()

        if self.GIT_VERSION < (1, 8, 0):
            self.assertEqual('', err.decode('utf-8'))
            self.assertEqual("Cloning into 'git-ro'...\n", out.decode('utf-8'))
        else:
            self.assertEqual('', out.decode('utf-8'))
            self.assertEqual("Cloning into 'git-ro'...\n", err.decode('utf-8'))
        self.assertEqual(client.returncode, 0)

    def test_git_clone_from_read_write_repo(self):
        if not self.HAVE_GIT:
            self.skipTest('Git is not available')
        if not self.HAVE_GIT_RW_REPOSITORY:
            self.skipTest('Git fixture repository could not be created.')

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
        if not self.HAVE_GIT_RO_REPOSITORY:
            self.skipTest('Git fixture repository could not be created.')

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
        # Git output changed over time. This change has been seen with version
        # as early as 1.9.1. Exact version for the change is unknown but we
        # assume 1.9.0 here.
        if self.GIT_VERSION >= (1, 9, 0) and self.GIT_VERSION < (2, 0, 0):
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
        if not self.HAVE_GIT_RW_REPOSITORY:
            self.skipTest('Git fixture repository could not be created.')
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
        if not self.HAVE_GIT:
            self.skipTest('Git is not available')
        if not self.HAVE_GIT_RW_REPOSITORY:
            self.skipTest('Git fixture repository could not be created.')

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
        if not self.HAVE_GIT_RO_REPOSITORY:
            self.skipTest('Git fixture repository could not be created.')

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
        self.assertRegexpMatches(
            err,
            re.compile(
                'remote: \x1b\[1;41mYou only have read only access to this '
                'repository\x1b\[0m: you cannot push anything into it !\n'
                'fatal: .*'.encode('utf-8'),
                re.S))
        self.assertEqual(out, ''.encode('utf-8'))

    # -- Mercurial related tests ----------------------------------------------

    def test_hg_clone_from_ro_repository(self):
        if not self.HAVE_HG:
            self.skipTest('Mercurial is not available on this system.')
        if not self.HAVE_HG_RO_REPOSITORY:
            self.skipTest('Mercurial fixture repository could not be created.')
        cmd = ['hg', 'clone', self._RO_HG_URL, ]

        # client = subprocess.Popen(
        #     cmd,
        #     stdin=subprocess.PIPE,
        #     stdout=subprocess.PIPE,
        #     stderr=subprocess.PIPE)
        # out, err = client.communicate()
        returncode, out, err = self.runCommand(cmd)

        self.assertEqual(returncode, 0)
        self.assertTrue(
            os.path.isdir(
                os.path.join(os.getcwd(), self._basename(self._RO_HG_URL))))

    def test_hg_clone_from_rw_repository(self):
        if not self.HAVE_HG:
            self.skipTest('Mercurial is not available on this system.')
        if not self.HAVE_HG_RW_REPOSITORY:
            self.skipTest('Mercurial fixture repository could not be created.')
        cmd = ['hg', 'clone', self._RW_HG_URL, ]

        returncode, out, err = self.runCommand(cmd)

        self.assertEqual(returncode, 0)
        self.assertTrue(
            os.path.isdir(
                os.path.join(os.getcwd(), self._basename(self._RW_HG_URL))))

    def test_hg_clone_from_wrong_repository(self):
        if not self.HAVE_HG:
            self.skipTest('Mercurial is not available on this system.')
        url = '{}-rubbish'.format(self._RW_HG_URL)
        local = '{}-rubbish'.format(self._RW_HG_PATH)
        cmd = ['hg', 'clone', url, ]

        returncode, out, err = self.runCommand(cmd)

        self.assertEqual(returncode, 255)
        self.assertEqual(
            out, 'remote: Illegal repository "{}"\n'.format(local))
        self.assertEqual(err,
                         'abort: no suitable response from remote hg!\n')

    def test_hg_pull_from_ro_repository(self):
        if not self.HAVE_HG:
            self.skipTest('Mercurial is not available on this system.')
        if not self.HAVE_HG_RO_REPOSITORY:
            self.skipTest('Mercurial fixture repository could not be created.')

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
        returncode, out, err = self.runCommand(cmd)
        self._leave_working_copy()

        self.assertEqual(returncode, 0)
        self.assertEqual(err, '')
        self.assertRegexpMatches(
            out,
            re.compile(
                'pulling from {}\n(searching for|requesting all) changes\n'
                'adding changesets\nadding manifests\nadding file changes\n'
                'added \d+ changesets with \d+ changes to \d+ files\n'
                '\d+ files updated, \d+ files merged, \d+ files removed, '
                '\d+ files unresolved\n'
                ''.format(self._RO_HG_URL),
                re.S))

    def test_hg_pull_from_rw_repository(self):
        if not self.HAVE_HG:
            self.skipTest('Mercurial is not available')
        if not self.HAVE_HG_RW_REPOSITORY:
            self.skipTest(
                'Fixture repository creation failed (look above for '
                'warnings).')

        # First we clone the repo as it is.
        self.assertEqual(self._clone(self._RW_HG_URL), 0)

        cmd = [
            'hg',
            'pull',
            '-u',
            ]

        # Then we add something to pull to the repository (by
        # making a new revision in another, local, working copy)
        self.assertEqual(self._make_a_revision_and_push_it(self._RW_HG_LOCAL),
                         0)

        self._enter_working_copy(self._RW_HG_URL)
        returncode, out, err = self.runCommand(cmd)
        self._leave_working_copy()

        self.assertEqual(returncode, 0)
        self.assertEqual(err, '')
        self.assertRegexpMatches(
            out,
            re.compile(
                'pulling from {}\n(searching for|requesting all) changes\n'
                'adding changesets\nadding manifests\nadding file changes\n'
                'added \d+ changesets with \d+ changes to \d+ files\n'
                '\d+ files updated, \d+ files merged, \d+ files removed, '
                '\d+ files unresolved\n'
                ''.format(self._RW_HG_URL),
                re.S))

    def test_hg_push_to_read_only_repository(self):
        if not self.HAVE_HG:
            self.skipTest('Mercurial is not available')
        if not self.HAVE_HG_RO_REPOSITORY:
            self.skipTest(
                'Fixture repository creation failed (look above for '
                'warnings).')

        # Have to make a remote clone or the push would be local (slow i know).
        self._make_a_revision(self._RO_HG_URL)

        cmd = [
            'hg',
            'push',
            ]

        self._enter_working_copy(self._RO_HG_URL)
        returncode, out, err = self.runCommand(cmd)
        self._leave_working_copy()

        # Note the double 'remote: ' prefix in the error line (cf. function
        # rejectpush) Not sure why it occurs but it seems out of my control
        # (added somewhere within mercurial's internals).
        self.assertEqual(
            out,
            'pushing to {}\nsearching for changes\n'
            'remote: remote: \x1b[1;41mYou only have read only access to this '
            'repository\x1b[0m: you cannot push anything into it !\n'
            'remote: abort: prechangegroup.hg-ssh hook failed\n'
            .format(self._RO_HG_URL))
        self.assertEqual(err, '')
        self.assertEqual(returncode, 1)

    # TODO: def test_hg_push_to_read_write_repository(self):

    # -- Bazaar related tests -------------------------------------------------

    def test_bzr_branch_from_repository(self):
        if not self.HAVE_BZR:
            self.skipTest('Bazaar is not available on this system.')
        if not self.HAVE_BZR_RW_REPOSITORY:
            self.skipTest('Bazaar fixture repository could not be created.')

        cmd = ['bzr', 'branch', self._RW_BZR_URL, ]

        returncode, out, err = self.runCommand(cmd)

        self.assertEqual(returncode, 0)
        self.assertTrue(
            os.path.isdir(
                os.path.join(os.getcwd(), self._basename(self._RW_BZR_URL))))

    def test_bzr_pull_from_repository(self):
        if not self.HAVE_BZR:
            self.skipTest('Bazaar is not available on this system.')
        if not self.HAVE_BZR_RW_REPOSITORY:
            self.skipTest('Bazaar fixture repository could not be created.')

        self._clone(self._RW_BZR_URL)
        cmd = ['bzr', 'pull', self._RW_BZR_URL, ]

        # Then we add something to pull to the repository (by
        # making a new revision in another, local, working copy)
        self._make_a_revision_and_push_it(self._RW_BZR_LOCAL)

        self._enter_working_copy(self._RW_BZR_URL)
        returncode, out, err = self.runCommand(cmd)
        self._leave_working_copy()

        self.assertEqual(returncode, 0)
        self.assertTrue(
            os.path.isdir(
                os.path.join(os.getcwd(), self._basename(self._RW_BZR_URL))))
        self.assertRegexpMatches(
            err,
            re.compile(
                '( M  content\nAll changes applied successfully.\n)?'
                'remote: Warning: using Bazaar: no access control enforced!\n',
                re.S))
        self.assertRegexpMatches(
            out,
            re.compile('Now on revision \d+.'.format(self._RW_BZR_URL),
                       re.S))

    def test_bzr_send_to_repository(self):
        if not self.HAVE_BZR:
            self.skipTest('Bazaar is not available on this system.')
        if not self.HAVE_BZR_RW_REPOSITORY:
            self.skipTest('Bazaar fixture repository could not be created.')

        self._clone(self._RW_BZR_URL)
        cmd = ['bzr', 'push', self._RW_BZR_URL, ]

        self._enter_working_copy(self._RW_BZR_URL)
        self._do_make_a_revision()
        returncode, out, err = self.runCommand(cmd)
        self._leave_working_copy()

        self.assertEqual(returncode, 0)
        self.assertTrue(
            os.path.isdir(
                os.path.join(os.getcwd(), self._basename(self._RW_BZR_URL))))
        self.assertRegexpMatches(
            err,
            re.compile(
                '(Pushed up to revision \d.\n|'
                'remote: Warning: using Bazaar: no access control enforced!\n)'
                '{2}',
                re.S))
        self.assertEqual(out, '')

    # -- Basic commands validatation tests ------------------------------------

    def test_ssh_connection_with_command_is_rejected(self):
        cmd = [
            'ssh',
            '-T',
            '-p',
            str(self.PORT),
            self.SSH_CONFIG_HOST_NAME,
            '/bin/sh',
            ]

        returncode, out, err = self.runCommand(cmd, input='exit 0')

        self.assertEqual(returncode, 255)
        self.assertEqual(err,
                         'remote: Illegal command "/bin/sh"\n')
        self.assertEqual(out, '')

    def test_ssh_connection_without_command_is_rejected(self):
        cmd = [
            'ssh',
            '-T',
            '-p',
            str(self.PORT),
            self.SSH_CONFIG_HOST_NAME,
            ]
        returncode, out, err = self.runCommand(cmd, input='exit 0')

        self.assertEqual(returncode, 255)
        self.assertEqual(err, 'remote: Illegal command "?"\n')
        self.assertEqual(out, '')


# vim: syntax=python:sws=4:sw=4:et:
