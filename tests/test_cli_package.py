#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals

import unittest
import os
import sys
import re

# Allow interactive execution from CLI,  cd tests; ./test_cli.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksconf.consts import *
from tests.cli_helper import *


class CliPackageCmdTest(unittest.TestCase):

    # DOH!  No tests yet!
    '''
    def test_package_simple(self):
        """ A short description of my ksconf package test. """
        twd = TestWorkDir()
        conf1 = twd.write_file("savedsearches-1.conf", """
        [x]
        search = noop
        """)
        conf2 = twd.write_file("savedsearches-2.conf", r"""
        [x]
        search = tstats count where index=hippo by sourcetype, source \
        | stats values(source) by sourcetype
        """)
        with ksconf_cli:
            ko = ksconf_cli("package", conf1, conf2)
            self.assertEqual(ko.returncode, EXIT_CODE_DIFF_CHANGE)
            self.assertRegex(ko.stdout, r"^diff ", "Missing diff header line")
    '''




if __name__ == '__main__':  # pragma: no cover
    unittest.main()
