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


__all__ = [
    'BackupEditAndRestore',
    ]


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


# vim: syntax=python:sws=4:sw=4:et:
