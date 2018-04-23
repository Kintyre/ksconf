#!/usr/bin/env python
# May eventually switch to some other mechanism (possibly nose) but for now this works

# Note:  TestLoader.discover() is new in Python 2.7 (won't work in 2.6, if we care)

import unittest

def run_all():
    loader = unittest.TestLoader()
    # Top-level "tests" directory, contains "test_*.py" scripts
    suite = loader.discover("tests")
    runner = unittest.TextTestRunner()
    runner.run(suite)

if __name__ == "__main__":
    run_all()
