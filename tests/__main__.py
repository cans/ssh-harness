# -*- coding: utf-8; -*-
#
# Copyright © 2014, Nicolas CANIART <nicolas@caniart.net>
#
import os
import sys
from unittest import TestLoader
try:
    from tap import TAPTestRunner as TestRunner
    tap_output = os.path.join(os.path.dirname(__file__),
                              'tap')
    TestRunner.set_outdir(tap_output)
except ImportError:
    from unittest import TextTestRunner as TestRunner

path = os.path.dirname(__file__)
res = TestRunner(verbosity=2).run(
    TestLoader().discover('./', pattern='test_*.py'))

sys.exit(not res.wasSuccessful())


# vim: syntax=python:sws=4:sw=4:et:
