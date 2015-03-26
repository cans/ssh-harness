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
from gettext import lgettext as _
import shutil


__all__ = [
    'BackupEditAndRestore',
    ]


def _move(src, dst):
    """Wrapper around :py:func:`os.rename` that handles some issues on
    platform which do not have an atomic rename."""
    try:
        os.rename(src, dst)
    except OSError:
        # For windows.
        os.remove(dst)
        os.rename(src, dst)


class BackupEditAndRestore(object):
    """Open a file for edition but creates a backup copy first.

    :param str path: the path to the target file.
    :param str suffix: the suffix to append the name of the file to create
        its backup copy (default is 'backup').
    :param str mode: the mode in which open the file (see :py:func:`open`)
    :param str context: the context keywork lets you partition the set of
        files you back-up (see methods :py:meth:`clear` and
        :py:meth:`clear_context`)

    Additionnaly keyword arguments accepted by the :py:func:`open` function
    are accepted, with some restriction on mode (see. note
        below).

    This context manager tryes to make the changes to the file appear atomic.
    To that end as well as creating a backup copy, it create an *edition*
    copy of the target file.
    When entering the context the file being modified is in fact not the target
    file but its *edition-copy*
    When the contex is exited the *edition-file* replaces the target file
    (atomically if the OS platform supports it, i.e. atomicity is guaranteed
    on POSIX system).

    You later restore the file either with either of the :py:meth:`restore`
    py:meth:`clear` and :py:meth:`clear_context` methods (see their respective
    descriptions).

    :Example:

        with BackupEditAndRestore('context', './my-precious', 'a') as f:
            f.write(data)
        with BackupEditAndRestore('context', './my-other-precious', 'a') as f:
            f.write(data)

        # Do something ...

        BackupEditAndRestore.clear_context('context')

    .. note::

       The mode 'r' is prohibited here as it makes no sense to backup
       a file to do nothing with it.
    """

    _SUFFIX = 'backup'

    _contexts = {}
    """Stores contexts """

    def __init__(self, context, path, mode='a', suffix=None, **kwargs):
        check_mode = (mode * 1).replace('U', 'r').replace('rr', 'r')
        if 'r' == check_mode[0] and '+' not in check_mode:
            raise ValueError('Wrong file opening mode: {}'.format(mode))
        self.__class__._register(context, path, self)

        self._path = path
        self._suffix = suffix or self.__class__._SUFFIX
        self._new_suffix = 'new-{}'.format(self._suffix)

        self._new_path = '{}.{}'.format(self._path, self._new_suffix)
        self._backup_path = '{}.{}'.format(self._path, self._suffix)

        # Some flags used to know where we're at.
        self._entered = False
        self._have_backup = None
        self._restored = False
        self._context = context

        # Users expects some content in the file, so we copy the original one.
        if mode[0] in ['a', 'r', 'U']:
            # Cannot copy, unless the file exists:
            if os.path.isfile(self._path):
                shutil.copy(self._path, self._new_path)

        kwargs.update({'mode': mode})  # Default mode is 'a'
        # Output is redirected to the new file
        try:
            self._f = open(self._new_path, **kwargs)
        except IOError as e:
            self.__class__._unregister(context, path, self)
            raise e
        # super(BackupEditAndRestore, self).__init__(self._new_path, **kwargs)

    def __enter__(self):
        if self._entered is True:
            raise RuntimeError(
                "You cannot re-use a {} context manager (recursivelly or "
                "otherwise)".format(self.__class__.__name__))
        self._entered = True
        self._have_backup = False
        self._f.__enter__()

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

        # Replace the original file with the one that has been edited.
        _move(self._new_path, self._path)
        return res

    def restore(self):
        """Restores the file to its original state.

        If it did not exist then it is removed, otherwise its back-up
        copy is used to restore it in its previous state."""
        if self._restored is True:
            # TODO raise an exception.
            return

        if self._have_backup is True:
            _move(self._backup_path, self._path)
        else:
            os.unlink(self._path)
        self._restored = True
        self.__class__._unregister(self._context, self._path, self)

    @classmethod
    def _register(cls, context, path, inst):
        # Create the context if need be.
        if context not in cls._contexts:
            cls._contexts[context] = dict()

        # Check the file has not already been backed up.
        if path in cls._contexts[context]:
            raise RuntimeError("File already backed up!")

        cls._contexts[context][path] = inst

    @classmethod
    def _unregister(cls, context, path, inst):
        if path not in cls._contexts[context]:
            raise RuntimeError(_("No backup registered for the given path: "
                                 "`{}'!")
                               .format(path, context))
        if inst is not cls._contexts[context][path]:
            raise RuntimeError(_("Registered and passed instances for path"
                                 " `{}' in context `{}' do not match!")
                               .format(path, context))

        del cls._contexts[context][path]

    @classmethod
    def clear_context(cls, context):
        """Restore all files in the specified :param:`context`.

        Using the :meth:`restore` requires of you to keep track of the files
        you backup.

        The :class:`BackupEditAndRestore` class can perform this
        book-keeping for you. May find this method more convenient, if
        you don't need each individual file to be restored at a specific point
        in time.

        Not that :meth:`clear_context`
        """
        if context not in cls._contexts:
            return

        for instance in list(cls._contexts[context].values()):
            instance.restore()

    @classmethod
    def clear(cls, context, path):
        """Restores the file designated :param:`path` and :param:`context`

        This is a convinience method so that you don't need to keep a
        reference on files you back-up.
        """
        cls._contexts[context][path].restore()

# vim: syntax=python:sws=4:sw=4:et:
