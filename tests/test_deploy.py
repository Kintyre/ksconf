#!/usr/bin/env python

from __future__ import absolute_import, unicode_literals

import os
import sys
import unittest
from io import open
from pathlib import Path

# Allow interactive execution from CLI,  cd tests; ./test_deploy.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksconf.deploy import (AppManifest, ManifestManager, StoredArchiveManifest,
                           create_manifest_from_archive)
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
        tgz = Path(tgz)
        manifest = AppManifest.from_archive(tgz)
        self.assertEqual(len(manifest.files), 15)

        create_manifest_from_archive(tgz, tgz.with_suffix(".cache"), manifest)
        print(manifest.files)

    def test_load_metadata(self):
        tgz = self.twd.copy_static("apps/modsecurity-add-on-for-splunk_11.tgz", "modsecurity-add-on-for-splunk_11.tgz")
        tgz = Path(tgz)

        mm = ManifestManager()
        manifest = mm.manifest_from_archive(tgz)
        self.assertEqual(len(manifest.files), 15)
        # Ensure hash value doesn't change without knowing
        self.assertEqual(manifest.hash, "d20973be2fd1d8828ee978e2a3fb7bd96e3ced06e234289e789b25a0462e9003")

        # Ensure that cache file was created (lives along side the tarball)
        cache_files = list(tgz.parent.glob("*.manifest"))
        self.assertEqual(len(cache_files), 1)

        # Explicitly load manifest from cache file
        manifest2 = StoredArchiveManifest.from_manifest(tgz, cache_files[0]).manifest

        self.assertEqual(manifest, manifest2)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
