#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals
import os
import sys
import unittest

# Allow interactive execution from CLI,  cd tests; ./test_cli.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.cli_helper import ksconf_cli


class CliSimpleTestCase(unittest.TestCase):
    """ Test some very simple CLI features. """

    def test_help(self):
        out = ksconf_cli("--help")
        self.assertIn("Kintyre Splunk CONFig tool", out.stdout)
        self.assertIn("usage: ", out.stdout)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
