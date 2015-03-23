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
import os
import shutil
from tempfile import mkdtemp
import warnings


class InThrowableTempDir(object):
    """
    Context manager that puts your program in a pristine temporary directory
    upon entry and puts you back where you were upon exit. It also cleans
    the temporary directory
    """

    def __init__(self, suffix='', prefix='throw-', dir=None):
        if dir is not None and not os.path.isdir(dir):
            # mkdtemp fails with OSError if :param:`dir` does not exists.

            # Py3 uses 0o700 for octal not plain 0700 (where the fuck did
            # that come from!) So we use plain decimal encoding for mode.
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


# vim: syntax=python:sws=4:sw=4:et:
