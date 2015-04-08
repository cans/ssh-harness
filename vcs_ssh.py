# -*- coding: utf-8-unix; -*-
#  Copyright 2005-2007 by Intevation GmbH <intevation@intevation.de>
#  Copyright © 2013-2014, Nicolas CANIART <nicolas@caniart.net>
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
from __future__ import unicode_literals
import argparse
from functools import wraps
import os
import shlex
import subprocess
import logging
from gettext import gettext as _
from sys import stderr, version_info as VERSION_INFO
logger = logging.getLogger('vcs-ssh')


HAVE_MERCURIAL = False
if (3, 0, 0, ) > VERSION_INFO:
    try:
        # from mercurial import demandimport
        # demandimport.enable()
        from mercurial import dispatch
        HAVE_MERCURIAL = True
    except ImportError:
        pass

__all__ = [
    'main',
    'parse_args',
    'VERSION',
    ]

VERSION = (1, 0, 5, )


def have_required_command(func):
    """Provides feedback to the user that is much nicer than the traceback
    of a failed call to one of the subprocess's module function, when a
    command is missing."""
    @wraps(func)
    def wrap(command, rw_dirs, ro_dirs):
        system_path = os.getenv('PATH').split(os.pathsep)
        for directory in system_path:
            binary = os.path.join(directory, command[0])
            if os.path.isfile(binary) and os.access(binary, os.R_OK | os.X_OK):
                return func(command, rw_dirs, ro_dirs)
        stderr.write('The command required to fulfill your request has not '
                     'been found on this system.')
        return 254
    return wrap


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
    logger.warning(_("Illegal repository \"{}\"\n").format(repo))
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
    @have_required_command
    def bzr_handle(cmdargv, rw_dirs, ro_dirs):
        # For now this is all we do.
        return pipe_dispatch(cmdargv)
else:
    # Bazaar not ported to Python 3, so this is pretty much all we can do
    # so far.
    @have_required_command
    def bzr_handle(cmdargv, rw_dirs, ro_dirs):
        return pipe_dispatch(cmdargv)


@have_required_command
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


@have_required_command
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


if HAVE_MERCURIAL:
    def hg_dispatch(cmdargv):
        logger.debug(_("Using in-process Mercurial dispatch"))
        return dispatch.dispatch(dispatch.request(cmdargv))
else:
    # mercurial not ported to Python 3 yet (and they have no plan to do so !)
    def hg_dispatch(cmdargv):
        return pipe_dispatch(['hg', ] + cmdargv)


def pipe_dispatch(cmd):
    logger.debug(_("Dispatching via a pipe."))
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
        description=_("Share multiple vcs repositories of different kinds on a"
                      " single user account, via ssh."),
        add_help=True)

    parser.add_argument('MORE_RW_DIRS', nargs='*', metavar='DIR',
                        help=_("More repository directories, accessible in r/w"
                               " mode."),
                        default=[])
    parser.add_argument('--read-only', metavar='DIR', nargs='+',
                        help=_("path to repository directories, to which grant"
                               " read-only access"),
                        dest='RO_DIRS',
                        default=[])
    parser.add_argument('--read-write', metavar='DIR', nargs='+',
                        help=_("path to repository directories, to which grant"
                               " access in r/w mode"),
                        dest='RW_DIRS',
                        default=[])
    parser.add_argument('-v', '--version',
                        action='version',
                        version=_("vcs-ssh version {}.{}.{}").format(*VERSION))
    # parser.add_argument('--scp-only', type=bool, default=False, metavar=None,
    #                     help='SCP read-only restricted access')

    parsed_args = parser.parse_args(argv)
    for v in ['RW_DIRS', 'RO_DIRS', 'MORE_RW_DIRS', ]:
        key = v.lower()
        if 'M' == v[0]:
            # Remove MORE_ we want all in those dir. in a single RW_DIRS list.
            key = key[5:]
        args[key] += [
            os.path.abspath(os.path.normpath(os.path.expanduser(path)))
            for path in getattr(parsed_args, v, [])]

    return args


def main(rw_dirs=None, ro_dirs=None):
    orig_cmd = os.getenv('SSH_ORIGINAL_COMMAND', '?')
    rw_dirs = rw_dirs or []
    ro_dirs = ro_dirs or []

    logger.info(_("vcs-ssh started with command `{}' for user {}.")
                .format(orig_cmd, os.getuid()))
    logger.debug(_("Accessible repositories are:\n  + read-only:\n    - {}\n"
                 "  + read-write:\n    - {}")
                 .format('\n    - '.join(ro_dirs) or None,
                         '\n    - '.join(rw_dirs) or None))

    try:
        cmdargv = shlex.split(orig_cmd)
    except ValueError as e:
        logger.debug(_("Original command parsing failed with error: {}")
                     .format(getattr(e, 'message', e)))
        # Python3 deprecated the message attribute on exceptions.
        return rejectcommand(orig_cmd,
                             extra=getattr(e, 'message', e))

    if cmdargv[:2] == ['hg', '-R'] and cmdargv[3:] == ['serve', '--stdio']:
        logger.debug(_("Selected the {} handler.").format('Mercurial'))
        result = hg_handle(cmdargv, rw_dirs, ro_dirs)
    elif (('git-receive-pack' == cmdargv[0] or 'git-upload-pack' == cmdargv[0])
          and 2 == len(cmdargv)):
        logger.debug(_("Selected the {} handler.").format('Git'))
        result = git_handle(cmdargv, rw_dirs, ro_dirs)
    elif cmdargv == [
            'bzr', 'serve', '--inet', '--directory=/', '--allow-writes']:
        logger.debug(_("Selected the {} handler.").format('Bazaar'))
        warn_no_access_control('Bazaar')
        result = bzr_handle(cmdargv, rw_dirs, ro_dirs)
    elif "svnserve -t" == orig_cmd:
        logger.debug(_("Selected the {} handler.").format('Subversion'))
        warn_no_access_control('Subversion')
        result = pipe_dispatch(cmdargv)
    else:
        logger.error(_("Could not determine a valid handler."))
        result = rejectcommand(orig_cmd)

    logger.info(_("vcs-ssh exiting with status `{}'").format(result))
    return result

# vim: syntax=python:sws=4:sw=4:et:
