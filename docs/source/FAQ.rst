FAQ
===


Why use SSH at all
------------------


   My VCS allows me to share repositories through HTTP, it even
   provides a shiny repository browsing interface ! Why should I bother ?


Well, on one hand, you have to administer your systems right ? If not
you someone else does. Most likely they use SSH for that, especially if
they do it remotely. Thus using SSH for sharing repositories as well
will not expand the exposure of your server. Moreover SSH servers
are pretty small application and being regarded as security tools,
they are fairly thoroughly looked after for providers

On the hand other, HTTP has become quite a beast over time, and so have
HTTP servers. From serving static files, they have become the
workhorses of the web, often providing lots of plugins... they represent
huge amounts of code. Of course as they are also thoroughly looked after
too. But the smaller the haystack...

The shiny repository browsing feature, you can run it locally if need
be, especially if you work with distributed VCS:

- Mercurial embeds a web-server exactly for that (:manpage:`hg(1)`,
  look for the `serve` command);
- Git has :manpage:`git-instaweb(1)`;

You may even find shinier desktop applications, sometimes they even
support multiple VCS.


Why use VCS-SSH
---------------

VCS-SSH itself is fairly small (about 350 LoC), easy to review and
(hopefully) free of security holes.


How do I install vcs-ssh
------------------------

You need to make sure you have a Python interpreter first.

Then if you have a Python package manager installed, you can use it,
*e.g.* with PIP::

  user@host:~# pip install vcs-ssh

Otherwise download `vcs-ssh` source `package
<https://pypi.python.org/vcs-ssh/>`_ from the `Python Package Index
<https://pypi.python.org/>`_


There are also `Debian packages <http://www.caniart.net/debian/>`_
available.

.. note::

   Whatever :program:`vcs-ssh` package you grab, make sure to grab the
   signature that comes with it as well, and don't forget to verify
   it. The packages should be signed by the following key::

     ID: 3072D/C1794172
     FP: 9673 2B75 D034 7CD0 29C9  95AF 3B15 5522 C179 4172


Why is vcs-ssh written in Python
--------------------------------

Well for historical reason mostly: it started it life as a
modification of :program:`hg-ssh` a script distributed with the
Mercurial VCS that allows sharing such repositories (but *only such*
repositories via SSH) written by Thomas Arendsen Hein.

If today there is not much left from the original script in `vcs-ssh`,
it is still written in Python.
