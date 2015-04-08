SSH-HARNESS: A Test Harness for testing SSH dependant applications
==================================================================


Features
--------


How does one use ssh-harness
----------------------------


You basically use it as any TestCase class from Python's unittest
framework:

.. code-block::
   :number-lines:
   :emphasize-lines: 2,6

  # -*- coding: utf-8; -*-
  from ssh_harness import PubKeyAuthSshClientTestCase

  import your_code


  class MyTestCase(PubKeyAuthSshHarness):

      def test_something(self):
          # use your_code, assert something
          pass


The important bits are: importing the :py:class:`PubKeyAuthSshClientTestCase`
(l. 2) and inheriting from it (l. 6).

With that little code, you start a SSH server, bound to the loopback interface
on port 2200.
