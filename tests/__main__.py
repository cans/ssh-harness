# -*- coding: utf-8; -*-
#
# Copyright © 2014, Nicolas CANIART <nicolas@caniart.net>
#

import os
from unittest import TestLoader, TextTestRunner

path = os.path.dirname(__file__)
TextTestRunner(verbosity=2).run(
    TestLoader().discover('./', pattern='test_*.py'))


# vim: syntax:tw=4:sw=4:et:
