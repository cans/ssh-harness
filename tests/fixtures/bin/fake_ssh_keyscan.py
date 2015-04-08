#!/usr/bin/python
# -*- coding: utf-8-unix; -*-
#
#  Copyright © 2015, Nicolas CANIART <nicolas@caniart.net>
#
#  This file is part of ssh-harness.
#
#  ssh-harness is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License version 2 as
#  published by the Free Software Foundation.
#
#  ssh-harness is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with ssh-harness.  If not, see <http://www.gnu.org/licenses/>.
#
import os
import sys

FILE_CONTENT = 'some content'

MODULE_PATH = os.path.abspath(os.path.dirname(__file__))
TEMP_PATH = os.path.normpath(os.path.join(MODULE_PATH, '..', 'tmp'))


if '__main__' == __name__:
    if 'FAKE_SSH_KEYSCAN_FAIL' in os.environ:
        sys.exit(True)
    if 'FAKE_SSH_KEYSCAN_QUIET' in os.environ:
        # Exits successfully but without producing any output.
        sys.exit(False)

    print(FILE_CONTENT)
    sys.exit(False)


# vim: syntax=python:sws=4:sw=4:et:
