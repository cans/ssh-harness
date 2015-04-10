SSH-HARNESS: A Test Harness for testing SSH dependant applications
==================================================================


The ``ssh_harness`` python package provides a ``unittest.TestCase`` subclass
for integration testing programs that requires the presence of a SSH daemon
running. The TestCase spawns a SSH daemon before running your test suite and
takes care of cleaning-up behind itself, when you are done.

To be as close as what would be a production environment, it uses OpenSSH as
a ssh daemon.


Features
--------

- Supports Public Key authentication
- Secure: ssh daemon is bound to the loopback address so to not open a port
  to the outside world while your tests are running.
- Configurable: you can change many of the daemon settings, as well as the
  location of all tools used while running the tests, this way you can
  easily run your tests again custom compiled versions of ssh.



How does one use ssh-harness
----------------------------


You basically use it like any other TestCase class from Python's unittest
framework:

.. code-block:: python
   :linenos:
   :emphasize-lines: 2,6

   # -*- coding: utf-8; -*-
   from ssh_harness import PubKeyAuthSshClientTestCase

   import your_code


   class MyTestCase(PubKeyAuthSshHarness):

       def test_something(self):
           # use your_code, assert something
           pass


The important bits are: importing the
:class:`ssh_harness.PubKeyAuthSshClientTestCase` (l. 2) and inheriting from
it (l. 6).

With that little code, you start a SSH server, bound to the loopback interface
on port 2200. This is of course, is the default configuration, which you can
change if need be.


Roadmap
-------

The ``ssh_harness`` was hacked out of the need of integration testing a
project of mine (`vcs-ssh <http://www.caniart.net/devel/vcs-ssh/>`_). It
as grown to a little project of its own. But there is no long-term road-map
for its development, apart from:

- First there is some refactoring to be made to improve the configurability
  of the system. And also avoid shared state at the class level between the
  test-case class and its sub-classes which sometimes leads to odd-behaviours.
- Then there are ideas that may be implemented has need or demand arises.
  To name a few:

  * Provide ability to configure an :file:`authorized_keys` file on a per
    test-case basis (it is now on a per test-suite basis).
  * Provide the ability to chroot the tests;
  * Provide the ability to restart the ssh daemon on demand or on a per
    test-case basis (not sure the later is really usefull)
  * You name it...


