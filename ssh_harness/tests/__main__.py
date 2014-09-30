# -*- coding: utf-8; -*-
#
# Copyright © 2014, Nicolas CANIART <nicolas@caniart.net>
#
import os
from unittest import TestLoader
try:
    from tap import TAPTestRunner as TestRunner
except ImportError:
    from unittest import TextTestRunner as TestRunner

path = os.path.dirname(__file__)
TestRunner(verbosity=2).run(
    TestLoader().discover('./', pattern='test_*.py'))


# vim: syntax=python:sws=4:sw=4:et:
