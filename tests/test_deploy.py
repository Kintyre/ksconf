#!/usr/bin/env python

from __future__ import absolute_import, unicode_literals

import os
import sys
import unittest
from io import open
from pathlib import Path

# Allow interactive execution from CLI,  cd tests; ./test_meta.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksconf.deploy import ManifestManager
from tests.cli_helper import TestWorkDir, static_data

"""
        self._modsec01_upgrade(twd, "apps/modsecurity-add-on-for-splunk_12.tgz")
        self._modsec01_upgrade(twd, "apps/modsecurity-add-on-for-splunk_14.tgz")
        tgz = static_data("apps/modsecurity-add-on-for-splunk_11.tgz")
"""


class ManifestTestCase(unittest.TestCase):

    def setUp(self):
        self.twd = TestWorkDir()

    def tearDown(self):
        # Cleanup test working directory
        self.twd.clean()

    def test_build_metadata(self):
        tgz = self.twd.copy_static("apps/modsecurity-add-on-for-splunk_11.tgz", "modsecurity-add-on-for-splunk_11.tgz")

        mm = ManifestManager()
        tgz = Path(tgz)
        manifest = mm.build_manifest_from_archive(tgz)
        self.assertEqual(len(manifest.files), 15)

        mm.save_manifest_from_archive(tgz.with_suffix(".cache"), manifest)
        print(manifest.files)

    def test_load_metadata(self):
        tgz = self.twd.copy_static("apps/modsecurity-add-on-for-splunk_11.tgz", "modsecurity-add-on-for-splunk_11.tgz")
        tgz = Path(tgz)

        mm = ManifestManager()
        manifest = mm.manifest_from_archive(tgz)
        self.assertEqual(len(manifest.files), 15)
        # Ensure hash value doesn't change without knowing
        self.assertEqual(manifest.hash, "964240d4c07268a6eac6776bec265dfeab30f8704a23ecdd542709a8796e10b0")

        # Ensure that cache file was created (lives along side the tarball)
        self.assertEqual(len(list(tgz.parent.glob("*.cache"))), 1)

        # Ensure that second load
        manifest2 = mm.manifest_from_archive(tgz)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
