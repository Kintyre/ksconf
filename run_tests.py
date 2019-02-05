#!/usr/bin/env python
# May eventually switch to some other mechanism (possibly nose) but for now this works

from __future__ import absolute_import, unicode_literals

import os
import sys
import unittest

# Run tests from this working directory; not from a previous 'pip install' run.
home = os.path.dirname(os.path.abspath(sys.argv[0] or __file__))
sys.path.insert(0, home)

import ksconf
print("Running all KSCONF unit tests.   KSCONF home:  {}".format(ksconf.__path__[0]))

# Because this script is run from the 'pre-commit' hooks, and some of these
# unittests do git automation, we need to purge all the "GIT_*" variables
for k in list(os.environ):
    if k.startswith("GIT_"):
        del os.environ[k]


def run_all():
    loader = unittest.TestLoader()
    # Top-level "tests" directory, contains "test_*.py" scripts
    suite = loader.discover("tests")
    runner = unittest.TextTestRunner()
    results = runner.run(suite)
    if results.errors:  # pragma: no cover
        return 2
    elif results.failures:  # pragma: no cover
        return 1


if __name__ == "__main__":
    sys.exit(run_all())
