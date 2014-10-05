#!/bin/bash
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
SOURCE="${BASH_SOURCE[0]}"
PACKAGE_PATH=$(dirname ${SOURCE})
COVERAGERC="${PACKAGE_PATH}/.coveragerc"

if ! [ -f './vcs_ssh.py' -a -f './vcs-ssh' ]
then
    echo 'Not where I expected to be !' 1>&2
fi

if [ -n "${TRAVIS_PYTHON_VERSION}" -a "2" = "${TRAVIS_PYTHON_VERSION:0:1}" ]
then
    pip install mercurial
fi

COVERAGE="$(which python-coverage)"
[ -z "${COVERAGE}" ] && COVERAGE="$(which coverage)"
[ -z "${COVERAGE}" ] && {                                      \
  echo 'Cannot find the coverage command !' 1>&2 ;             \
  exit 1 ;                                                     \
  }

cat > "${COVERAGERC}" <<EOF
[run]
branch = True
append = True
source = ${PACKAGE_PATH}/vcs-ssh,${PACKAGE_PATH}/vcs_ssh.py
parallel = True
data_file = ${PACKAGE_PATH}/.coverage

[path]
sources=
    ${PACKAGE_PATH}
    /var/lib/buildbot/slaves/*/*/vcs-ssh

EOF


"${COVERAGE}" run -a -p -m --rcfile "${COVERAGERC}" tests
status="$?"
"${COVERAGE}" combine
"${COVERAGE}" report

exit ${status}
