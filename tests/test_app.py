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

from ksconf.app import AppArchiveError, AppInfo, AppManifest, get_info_manifest_from_archive
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

    def test_thin_manifest(self):
        tarball_path = static_data("apps/modsecurity-add-on-for-splunk_12.tgz")
        manifest = AppManifest.from_archive(tarball_path, calculate_hash=False)
        self.assertEqual(len(manifest.files), 15)
        self.assertEqual(manifest.files[0].hash, None)
        self.assertEqual(manifest.hash, None)

    def test_the_do_it_all_function(self):
        tarball_path = static_data("apps/modsecurity-add-on-for-splunk_12.tgz")
        info, manifest = get_info_manifest_from_archive(tarball_path)

        self.assertEqual(info.name, "Splunk_TA_modsecurity")
        self.assertEqual(manifest.hash, "96c0bfd21bf0803c93ff297566029eff1c0d93a5df62d8bb920364fbab51830d")

        # No local files
        self.assertEqual(len(list(manifest.find_local())), 0)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
