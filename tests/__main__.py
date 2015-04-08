# -*- coding: utf-8; -*-
#
# Copyright © 2014-2015, Nicolas CANIART <nicolas@caniart.net>
#
import os
import sys
from unittest import TestLoader
path = os.path.dirname(__file__)
try:
    from tap import TAPTestRunner as TestRunner
    TestRunner.set_outdir(os.path.join(path, 'tap'))
except ImportError:
    from unittest import TextTestRunner as TestRunner

res = TestRunner(verbosity=2).run(
    TestLoader().discover('./', pattern='test_*.py'))

sys.exit(not res.wasSuccessful())


# vim: syntax=python:sws=4:sw=4:et:
