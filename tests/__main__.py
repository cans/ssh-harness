# -*- coding: utf-8; -*-
#
# Copyright © 2014, Nicolas CANIART <nicolas@caniart.net>
#
import os
import sys
from unittest import TestLoader, main
try:
    from tap import TAPTestRunner as TestRunner
except ImportError:
    from unittest import TextTestRunner as TestRunner

path = os.path.dirname(__file__)
res = TestRunner(verbosity=2).run(
    TestLoader().discover('./', pattern='test_*.py'))

sys.exit(not res.wasSuccessful())


# vim: syntax=python:sws=4:sw=4:et:
