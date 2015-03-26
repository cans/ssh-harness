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
module="vcs-ssh"
rcfilename="${module}.coveragerc"
MODULE="vcs_ssh"
TRESHOLD="95"

SOURCE="${BASH_SOURCE[0]}"
PACKAGE_PATH=$(dirname ${SOURCE})
[ -w "${PACKAGE_PATH}" ]                               \
   && { COVERAGERC="${PACKAGE_PATH}/${rcfilename}" ; }   \
   || [ -w "$(pwd)" ]                                  \
       && { COVERAGE="$(pwd)/" ; }                         \
       || { COVERAGERC="${TMP}" ; }

if ! [ -f "./${MODULE}.py" -o -d "./${MODULE}" ]
then
    cat 1>&2 <<EOF
Not where I expected to be !
Assuming I am running on a system where vcs_ssh is installed in site- or
dist-packages.
Trying to retrieve the installation path of \`${MODULE}'...
EOF

    if ! python -m "${MODULE}" 2>/dev/null
    then
        echo
        echo "Well I tried but \`${MODULE}' could not be loaded."
        exit 1
    fi
fi

if [ -n "${TRAVIS_PYTHON_VERSION}" -a "2" = "${TRAVIS_PYTHON_VERSION:0:1}" ]
then
    pip install mercurial
fi

default_coverage=python-coverage
if [ "${1}" = "-3" ]
then
    default_coverage=python3-coverage
fi

COVERAGE="$(which ${default_coverage})"
[ -z "${COVERAGE}" ] && COVERAGE="$(which coverage)"
[ -z "${COVERAGE}" ] && {                                      \
  echo 'Cannot find the coverage command !' 1>&2 ;             \
  exit 1 ;                                                     \
  }

[ -d "tests/fixtures" ] && rm -rf tests/fixtures
[ -d "tests/tmp" ] && rm -rf tests/tmp

cat > "${COVERAGERC}" <<EOF
[run]
branch = True
append = True
source = ${PACKAGE_PATH}/vcs-ssh,${PACKAGE_PATH}/vcs_ssh.py
parallel = True
data_file = ${PACKAGE_PATH}/.coverage
fail_under = ${TRESHOLD}

[report]
fail_under = ${TRESHOLD}

[path]
sources=
    ${PACKAGE_PATH}
    /var/lib/buildbot/slaves/*/*/vcs-ssh

EOF


"${COVERAGE}" run -a -p -m --rcfile "${COVERAGERC}" tests
run_status="${?}"
"${COVERAGE}" combine --rcfile "${COVERAGERC}"
"${COVERAGE}" report --rcfile "${COVERAGERC}" --fail-under "${TRESHOLD}"
report_status="$?"

if [ "x1" = "x${run_status}" ]
then
    outcome="\033[1;31mFailure\033[0m (some test(s) did not pass)"
    status="${run_status}"
else
    status="${report_status}"
    if [ "x0" = "x${status}" ]
    then
        outcome="\033[1;32mSuccess\033[0m"
    else
        outcome="\033[1;31mFailure\033[0m (coverage below ${TRESHOLD}%)"
    fi
fi
echo -e "Overall outcome: ${outcome}"
exit ${status}
