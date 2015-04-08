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
import sys
from sys import stderr, stdout


def write_to_stderr(msg):
    stderr.write(msg)


def write_to_stdout(msg):
    stdout.write(msg)


def write_to_sys_stderr(msg):
    sys.stderr.write(msg)


def write_to_sys_stdout(msg):
    sys.stdout.write(msg)
