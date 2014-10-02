# -*- coding: utf-8-unix; -*-
#  Copyright 2005-2007 by Intevation GmbH <intevation@intevation.de>
#  Copyright © 2013-2014, Nicolas CANIART <nicolas@caniart.net>
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
"""
vcs-ssh - a Git and Mercurial wrapper to grant access to a selected set of
          reposotories.

To be used in ~/.ssh/authorized_keys with the "command" option, see sshd(8):
command="hg-ssh path/to/repo1 /path/to/repo2 ~/repo3 ~user/repo4" ssh-dss ...
(probably together with these other useful options:
 no-port-forwarding,no-X11-forwarding,no-agent-forwarding)

This allows pull/push over ssh from/to the repositories given as arguments.

If all your repositories are subdirectories of a common directory, you can
allow shorter paths with:
command="cd path/to/my/repositories && hg-ssh repo1 subdir/repo2"

You can use pattern matching of your normal shell, e.g.:
command="vcs-ssh user/thomas/* projects/{mercurial,foo}"
"""
import argparse
import os
import shlex
import subprocess
from sys import stderr, version_info as VERSION_INFO

if (3, 0, 0, ) > VERSION_INFO:
    from mercurial import demandimport
    demandimport.enable()
    from mercurial import dispatch

__all__ = [
    'main',
    'parse_args',
    'VERSION',
    ]

VERSION = (1, 0, 1, )


def rejectpush(*args, **kwargs):
    """Mercurial hook to reject push if repository is read-only."""
    prefix = 'remote: '
    if 0 < len(args):
        args[0].warn("Permission denied\n")
        prefix = ''
    stderr.write(
        "{}\033[1;41mYou only have read only access to this "
        "repository\033[0m: you cannot push anything into it !\n"
        .format(prefix))
    # # mercurial hooks use unix process conventions for hook return values
    # # so a truthy return means failure
    # return True
    return 255


def rejectrepo(repo):
    stderr.write('Illegal repository "{}"\n'.format(repo))
    return 255


def rejectcommand(command, extra=""):
    if extra:
        extra = ": {}".format(extra)
    stderr.write('remote: Illegal command "{}"{}\n'.format(command, extra))
    return 255


def warn_no_access_control(vcs_name):
    stderr.write(
        'remote: Warning: using {}: no access control enforced!\n'
        .format(vcs_name))


if (3, 0, 0, ) > VERSION_INFO:
    def bzr_handle(cmdargv, rw_dirs, ro_dirs):
        # For now this is all we do.
        return pipe_dispatch(cmdargv)
else:
    # Bazaar not ported to Python 3, so this is pretty much all we can do
    # so far.
    def bzr_handle(cmdargv, rw_dirs, ro_dirs):
        return pipe_dispatch(cmdargv)


def git_handle(cmdargv, rw_dirs, ro_dirs):
    path = cmdargv[1]
    repo = os.path.abspath(os.path.normpath(os.path.expanduser(path)))

    # Is the given repository path valid at all ?
    if repo not in rw_dirs + ro_dirs:
        return rejectrepo(repo)

    # Moreover is it read-only ?
    if repo in ro_dirs and "git-receive-pack" == cmdargv[0]:
        return rejectpush()

    cmdargv[1] = repo
    return pipe_dispatch(cmdargv)


def hg_handle(cmdargv, rw_dirs, ro_dirs):
    do_dispatch = False

    path = cmdargv[2]
    repo = os.path.abspath(os.path.normpath(os.path.expanduser(path)))
    rewrote_command = ['-R', repo, 'serve', '--stdio']

    if repo in ro_dirs:
        rewrote_command += [
            '--config',
            'hooks.prechangegroup.hg-ssh=python:vcs_ssh.rejectpush',
            '--config',
            'hooks.prepushkey.hg-ssh=python:vcs_ssh.rejectpush'
            ]
        do_dispatch = True

    if repo in rw_dirs:
        do_dispatch = True

    if do_dispatch is True:
        return hg_dispatch(rewrote_command)
    else:
        return rejectrepo(repo)


if (3, 0, 0) > VERSION_INFO:
    def hg_dispatch(cmdargv):
        return dispatch.dispatch(dispatch.request(cmdargv))
else:
    # mercurial not ported to Python 3 yet (and they have no plan to do so !)
    def hg_dispatch(cmdargv):
        return pipe_dispatch(['hg', ] + cmdargv)


def pipe_dispatch(cmd):
    serv = subprocess.Popen(cmd, shell=False)
    serv.communicate()
    return serv.returncode


def parse_args(argv):
    args = {
        # 'scp': args.SCP_ONLY,
        'rw_dirs': [],
        'ro_dirs': [],
        }

    parser = argparse.ArgumentParser(
        description='Share multiple vcs repositories of different kinds on a '
        'single user account, via ssh.',
        add_help=True)

    parser.add_argument('MORE_RW_DIRS', nargs='*', metavar='DIR',
                        help="More repository directories, accessible in r/w "
                        "mode.", default=[])
    parser.add_argument('--read-only', metavar='DIR', nargs='+',
                        help="path to repository directories, to which grant "
                        "read-only access", dest='RO_DIRS', default=[])
    parser.add_argument('--read-write', metavar='DIR', dest='RW_DIRS',
                        help="path to repository directories, to which grant "
                        "access in r/w mode", nargs='+', default=[])
    parser.add_argument('-v', '--version',
                        action='version',
                        version='vcs-ssh version {}.{}.{}'.format(*VERSION))
    # parser.add_argument('--scp-only', type=bool, default=False, metavar=None,
    #                     help='SCP read-only restricted access')

    parsed_args = parser.parse_args(argv)
    for v in ['RW_DIRS', 'RO_DIRS', 'MORE_RW_DIRS', ]:
        key = v.lower()
        if 'M' == v[0]:
            key = key[5:]
        args[key] += [
            os.path.abspath(os.path.normpath(os.path.expanduser(path)))
            for path in getattr(parsed_args, v, [])]

    return args


def main(rw_dirs=None, ro_dirs=None):
    orig_cmd = os.getenv('SSH_ORIGINAL_COMMAND', '?')
    rw_dirs = rw_dirs or []
    ro_dirs = ro_dirs or []

    try:
        cmdargv = shlex.split(orig_cmd)
    except ValueError as e:
        # Python3 deprecated the message attribute on exceptions.
        return rejectcommand(orig_cmd,
                             extra=getattr(e, 'message', e))

    if cmdargv[:2] == ['hg', '-R'] and cmdargv[3:] == ['serve', '--stdio']:
        return hg_handle(cmdargv, rw_dirs, ro_dirs)
    elif (('git-receive-pack' == cmdargv[0] or 'git-upload-pack' == cmdargv[0])
          and 2 == len(cmdargv)):
        return git_handle(cmdargv, rw_dirs, ro_dirs)
    elif cmdargv == [
            'bzr', 'serve', '--inet', '--directory=/', '--allow-writes']:
        warn_no_access_control('Bazaar')
        return bzr_handle(cmdargv, rw_dirs, ro_dirs)
    elif "svnserve -t" == orig_cmd:
        warn_no_access_control('Subversion')
        return pipe_dispatch(cmdargv)
    else:
        return rejectcommand(orig_cmd)


# vim: syntax=python:sws=4:sw=4:et:
