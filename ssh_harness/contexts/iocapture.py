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
"""
The :py:mod:`iocapture` module provides the means to capture IO produced
by other python modules.

One can capture output either globally or on a per module basis, through
duck-typing.

Here is an example

   w
"""
from io import StringIO as MemoryIO
from gettext import lgettext as _
import os
import sys
from tempfile import TemporaryFile


class IOCapture(object):

    def __init__(self,
                 stdout=True,
                 stderr=False,
                 file=False,
                 module=None,
                 out_attr=None,
                 err_attr=None):
        """Context Manager to capture either or both stdout and stderr.
        """
        if module is None:
            module = 'sys'
        if module in sys.modules:
            self._mod = sys.modules[module]
        else:
            raise RuntimeError(
                _("Module `{}' is not yet loaded!").format(module))

        self._do_stderr = stderr
        self._do_stdout = stdout

        if stderr:
            self._prepare_attrs(err_attr or 'stderr', 'err', file)
        else:
            self.stderr = sys.stderr

        if stdout:
            self._prepare_attrs(out_attr or 'stdout', 'out', file)
        else:
            self.stdout = sys.stdout

    def __enter__(self):
        if self._do_stderr:
            # Redirect stderr
            setattr(self._err_target, self._err_attr, self.stderr)
        if self._do_stdout:
            # Redirect stdout
            setattr(self._out_target, self._out_attr, self.stdout)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._do_stderr:  # Restore stderr if need be
            setattr(self._err_target, self._err_attr, self._olderr)
        if self._do_stdout:  # Restore stdout if need be
            setattr(self._out_target, self._out_attr, self._oldout)
        # Whatever happens propagate exceptions.
        return False

    def _prepare_attrs(self, module_attr, what, file):
        parent_object = None
        value = self._mod
        for bit in module_attr.split('.'):
            parent_object = value
            value = getattr(value, bit)

        if file is True:
            f = TemporaryFile(mode='w+', prefix='iocpt-')
        else:
            f = MemoryIO()

        setattr(self, '_{}_target'.format(what), parent_object)
        setattr(self, '_{}_attr'.format(what), bit)
        setattr(self, '_old{}'.format(what), value)
        setattr(self, 'std{}'.format(what), f)

    def _get_output(self, name):
        if not getattr(self, '_do_{}'.format(name)):
            return ''
        what = name[-3:]
        attr = getattr(self, name)
        if attr == getattr(getattr(self, '_{}_target'.format(what)),
                           getattr(self, '_{}_attr'.format(what))):
            raise RuntimeError(_("Calling `get_std{}()' while in the context"
                                 " is not allowed!").format(what))

        if isinstance(attr, MemoryIO):
            return attr.getvalue()
        else:
            attr.seek(0, os.SEEK_SET)
            return attr.read()

    def get_stderr(self):
        return self._get_output('stderr')

    def get_stdout(self):
        return self._get_output('stdout')


# vim: syntax=python:sws=4:sw=4:et:
