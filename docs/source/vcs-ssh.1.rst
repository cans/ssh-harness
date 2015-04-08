:orphan:

The vcs-ssh command manual
==========================


Synopsis
--------

**vcs-ssh** [DIR [DIR ...]] [--read-only DIR [DIR ...]] [--read-write DIR [DIR ...]] [-v|--version] [-h|--help]
               

A tool to helps you share via SSH directories managed by various
version control systems, namely: Bazaar, Git, Mercurial and
Subversion.

This tool is intended to be use in concert with SSH's ForcedCommand
mecanism and as such requires the use of public authentication.


Options
-------

-h, --help            show this help message and exit
--read-only           path to repository directories, to which grant read-
                      only access
--read-write          path to repository directories, to which grant access
                      in r/w mode
-v, --version         show program's version number and exit


History
-------

Lots of version control systems provides a mean to share repositories
via SSH. But sadly they quite never work well all together. Each come
with its tools, but none thought it might be useful to care about
other VCS. In fact vcs-ssh started its lifeYou are then either confined:

- to use a single VCS;
- to manage several keys;
- to find a more clever solution;

As a developper, your projects most likely rely on tools, libraries,
*etc.* not all maintained with the same VCS. The **stick to a single
VCS** approach is not realistic. Juggling with public keys is fun for
about 10 seconds, then it is just plain painful.

Then there is :program:`vcs-ssh` which tries to be the clever solution.


Prerequisites
-------------

Have public key authentification enable on the machine(s) hosting the
repositories you want to share.

Know the location of the public key authorization file on your
system. The default is :file:`~/.ssh/authorized_keys`.


Configuration
-------------

Open your public key authorization file. Add the public key of the
user with which you want to share one or more repostories. Then
on the same line, at the beginning insert a call to program:`vcs-ssh`
as follows::

   command="/usr/bin/vcs-ssh [DIR [DIR ...]]" <user's public key ...>

Each :data:`DIR` listed after ``/usr/bin/vcs-ssh`` is now accessible
vi ssh (provided it is a valid repository). **Note**: that the command
is quoted, be extra careful if the names of the directories you want
to share contain spaces or other strange characters.

That's it ! Of course you need to repeat the above for each user
you wish to share repositories with.


See Also
--------

:manpage:`sshd_config(7)`, :manpage:`ssh_config(7)`, 


