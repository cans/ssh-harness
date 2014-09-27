#!/bin/bash

SOURCE="${BASH_SOURCE[0]}"
PACKAGE_PATH=$(dirname ${SOURCE})
COVERAGERC="${PACKAGE_PATH}/.coveragerc"

if ! [ -f './vcs_ssh.py' -a -f './vcs-ssh' ]
then
    echo 'Not where I expected to be !' 1>&2
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
"${COVERAGE}" combine
"${COVERAGE}" report

exit 0
