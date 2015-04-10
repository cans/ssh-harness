.. vcs-ssh documentation master file, created by
   sphinx-quickstart on Tue Apr  7 18:28:02 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

==================================================================
SSH-HARNESS: A Test Harness for testing SSH dependant applications
==================================================================


Features
--------


How does one use ssh-harness
----------------------------


You basically use it like any other TestCase class from Python's unittest
framework:

.. code-block:: python
   :linenos:
   :emphasize-lines: 2,7

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
on port 2200.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

