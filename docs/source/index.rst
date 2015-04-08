.. vcs-ssh documentation master file, created by
   sphinx-quickstart on Tue Apr  7 18:28:02 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

=====================================================
VCS-SSH:  VCS agnostic repository sharing through SSH
=====================================================

Contents:

.. toctree::
   :maxdepth: 1

   FAQ



Some people have very strong feelings about which version control
system (vcs) is best, and which is *evil*. Understand which you should
use and which you should not. The approach of vcs-ssh is more
pragmatical: in a world of open source development, you often find
yourself using several of them. Indeed your code may depend on the
code of others who do not use the same vcs as you do.

And in the opinion of the author, appart from the divide between the
distributed vs. centralized VCS, there is not that much difference between
them for the day to day edit-commit-merge-push loop.

In the end, being able to access *easily* and **securely** to the
repositories you need is what matters. Yet, if many VCS have a way of
letting you do that, it generally does not interoperate very well with
others. You cannot, with the same public key, share a git repository
**and** a mercurial one (let alone any other, more involved,
combination of repositories and vcs you may wish for).

*This is the problem vcs-ssh solves*.


Features
--------

- Lets you shares **multiple** Git, Mercurial and Subversion repositories
  **with a single public key** (Bazaar should come soon).
- Can restrict access to read-only (pull) mode, on Git and Mercurial
  repositories (usefull e.g. for CI systems that only needs read-only access).


How does one use vcs-ssh
------------------------

It is quite simple! If you know about public key access and command
restrictions with SSH you probably have guessed already. If you don't
know about public key authentication with SSH, you should probably
investigate this first. There are plenty of HowTo on the net, to get
you started. And if you really want to understand how it works in
depth, I would recommand the [Snail Book](http://www.snailbook.com/).

Anyhow, here is how you use vcs-ssh:

Assume you are user ``john`` on the machine named ``host``. You log
in to your account (locally or through SSH). You first need to create
the ``~/.ssh/`` directory, and a file named ``authorized_keys`` in
that directory. Make sure permissions on that file are restricted to
``0600`` (``-rw-------``). This file is intended to list the public
keys of all the people authorized to log on your account, via SSH. It
generally looks like that::

  ssh-rsa =AAAA... My own key <john@host>
  ssh-rsa =AAAA... Alice's key <alice@example.com>
  ssh-dss =AAAA... Bob's key <bob@example.com>


Each *=AAAA...* being a very long string: it is the public key encoded
in base64. Anyone whose public key is listed there, will be granted
access to your account.

SSH default behaviour is to launch the shell you selected in your user
profile, for anyone connecting on your account. Of course you don't
want to let those people do everything they'd like on your account.
You just want them to be able to pull, or push from or to, some of the
repositories you store there. You can ask SSHD not to start a shell but
any other command. It suffice to add a *command* option at the
beginning of each line. This is where vcs-ssh comes into play. Edit
your ``~/.ssh/authorized_keys`` file like that::

  ssh-rsa =AAAA... My own key <john@host>
  command="vcs-ssh /home/john/shared/repository" ssh-rsa =AAAA... Alice's key <alice@example.com>
  command="vcs-ssh /path/to/some/repository /path/to/another/repository" ssh-rsa =AAAA... Bob's key <bob@example.com>


Now if you (John) try to log in, you still get a shell and can do as
you please on your own account, but Alice and Bob do not. Bob will
only be able to pull or push to the two repositories listed after
vcs-ssh: ``/path/to/some/repository`` and
``/path/to/another/repository``. The same goes for Alice which can
now only access to the repository in ``/home/john/shared/repository``.


The great thing is that **it does not matter** that e.g.
``/path/to/some/repository`` is a *Git repository* and
``/path/to/another/repository`` is a *Subversion repository* ! Routing
your request to the appropiate vcs is what ``vcs-ssh`` does for
you. One public key per user is sufficient to access as many
repositories as you need !



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

