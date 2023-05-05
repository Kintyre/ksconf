#!/usr/bin/env python

from __future__ import absolute_import, unicode_literals

import os
import sys
import unittest
from io import open
from pathlib import Path

# Allow interactive execution from CLI,  cd tests; ./test_app.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksconf.app import AppArchiveError, AppInfo
from tests.cli_helper import TestWorkDir, static_data

"""
        self._modsec01_upgrade(twd, "apps/modsecurity-add-on-for-splunk_12.tgz")
        self._modsec01_upgrade(twd, "apps/modsecurity-add-on-for-splunk_14.tgz")
        tgz = static_data("apps/modsecurity-add-on-for-splunk_11.tgz")
"""


class AppTestCase(unittest.TestCase):

    def setUp(self):
        self.twd = TestWorkDir()

    def tearDown(self):
        # Cleanup test working directory
        self.twd.clean()

    def test_appinfo_from_tarball(self):
        tarball_path = static_data("apps/modsecurity-add-on-for-splunk_11.tgz")
        app_info = AppInfo.from_archive(tarball_path)
        self.assertEqual(app_info.description, "ModSecurity Add-on for Splunk.")
        self.assertEqual(app_info.name, "Splunk_TA_modsecurity")
        self.assertEqual(app_info.version, "1.1")
        self.assertEqual(app_info.is_configured, False)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
