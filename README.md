VCS-SSH -- VCS agnostic repository sharing through SSH
======================================================


Some people have very strong feelings about which version control system (vcs)
is best, and which is *evil*. The approach of vcs-ssh is more pragmatical: in
a world of open source development, you often find yourself using several of
them. Indeed your code may depend on the code of others who do not use the
same vcs as you do.

And in the opinion of the author, appart from the divide between the
distributed vs. centralized VCS, there is not that much difference between
them for the day to day edit-commit-merge-push loop.

In the end being able to access easily and securely to any repository of any
VCS. Yet, if many VCS have a way of letting you do that, it generally does not
interoperate very well with others. You cannot, with the same public key,
share a git repository **and** a mercurial one (let alone any other, more
involved, combination of repositories and vcs you may wish for).

*This is the problem vcs-ssh solves*.


Features
--------

- Lets you shares **multiple** Git, Mercurial and Subversion repositories
  **with a single public key** (Bazaar should come soon).
- Can restrict access to read-only (pull) mode, on Git and Mercurial
  repositories (usefull e.g. for CI systems that only needs read-only access).


How do I use vcs-ssh
--------------------

It is quite simple! If you known about public key access and command
restrictions with SSH you probably have already guessed. 
If you don't know about public key authentication with SSH you
Anyhow, here how it works:

Assume you are the user john on the machine named host. You login in to your
account (locally or through SSH). You then create the directory ~/.ssh/, and
then a file name ``authorized_keys`` in that directory. This file is intended to
list the public keys of all the people authorized to log on your account.
It generally looks like that:

        ssh-rsa =AAAA... Alice's key <alice@example.com>
        ssh-dss =AAAA... Bob's key <bob@example.com>


Each *=AAAA...* being a very long string: it is the public key encoded in
base64. But of course you don't want to let those people do everything they'd
like on your account. You just want them to be able to commit, pull, or
push from or to, some of the repositories you store there. This is because by
default SSHD launches the shell you selected in your user profile, but you can
ask SSHD not to do that. It suffice to add a *command* option at the beginning
of each line. This is where vcs-ssh comes into play. Edit your the file like
that:

        ssh-rsa =AAAA... Alice's key <alice@example.com>
        command="vcs-ssh /path/to/some/repository /path/to/another/repository" ssh-rsa =AAAA... Bob's key <bob@example.com>


Now if Alice tries to log in, she still get a shell and can do as she please
on the account, but Bob does not. He will only be able to pull or push to
the two repositories listed after vcs-ssh: ``/path/to/some/repository`` and
``/path/to/another/repository``.

The great thing is that **it does not matter** that e.g.
``/path/to/some/repository`` is a *Git repository* and
``/path/to/another/repository`` is a *Subversion directory* ! Routing the
request to the appropiate vcs is what vcs-ssh does for you. One public key
is sufficient to access as many repositories as you need ! whatever
