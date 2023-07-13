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


from ksconf.app import get_facts_manifest_from_archive
from ksconf.app.facts import AppFacts
from ksconf.app.manifest import AppManifest, StoredArchiveManifest
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

    def test_AppFacts_todict(self):
        f = AppFacts("Splunk_TA_modsecurity",
                     version="1.1",
                     description="ModSecurity Add-on for Splunk.")
        f.is_configured = True
        d = f.to_dict()
        self.assertEqual(d["name"], "Splunk_TA_modsecurity")
        self.assertEqual(d["description"], "ModSecurity Add-on for Splunk.")
        self.assertEqual(d["version"], "1.1")

        td = f.to_tiny_dict("name", "build", "label")
        self.assertIs(td["build"], None)
        self.assertNotIn("check_for_updates", td)
        self.assertEqual(len(td), 6)

    def test_AppFacts_from_tarball(self):
        tarball_path = static_data("apps/modsecurity-add-on-for-splunk_11.tgz")
        app_info = AppFacts.from_archive(tarball_path)
        self.assertEqual(app_info.description, "ModSecurity Add-on for Splunk.")
        self.assertEqual(app_info.name, "Splunk_TA_modsecurity")
        self.assertEqual(app_info.version, "1.1")
        self.assertIsInstance(app_info.is_configured, bool)
        self.assertEqual(app_info.is_configured, False)

    def test_thin_manifest(self):
        tarball_path = static_data("apps/modsecurity-add-on-for-splunk_12.tgz")
        manifest = AppManifest.from_archive(tarball_path, calculate_hash=False)
        self.assertEqual(len(manifest.files), 15)
        self.assertEqual(manifest.files[0].hash, None)
        self.assertIs(manifest.hash, None)

    def test_the_do_it_all_function(self):
        tarball_path = static_data("apps/modsecurity-add-on-for-splunk_12.tgz")
        info, manifest = get_facts_manifest_from_archive(tarball_path)

        self.assertEqual(info.name, "Splunk_TA_modsecurity")
        self.assertEqual(manifest.hash, "7f9e7b63ed13befe24b12715b1e1e9202dc1186266497aad0b723fe27ca1de12")

        # No local files
        self.assertEqual(len(list(manifest.find_local())), 0)


class ManifestFormatTestCase(unittest.TestCase):
    def setUp(self):
        self.twd = TestWorkDir()

    def tearDown(self):
        # Cleanup test working directory
        self.twd.clean()

    def test_format_v1(self):
        manifest_v1 = self.twd.write_file(".org_all_indexes.manifest", r"""
        {
         "archive": "/opt/org_repo/splunk/tarred-apps/org_all_indexes-4d69ae148b6c832c.tgz",
         "size": 3411,
         "mtime": 1687465674.7253132,
         "hash": "9e6c28cd95a0ae61894d9feb656a6e8827450ed8ca9fc2328ba81037c6a31c27",
         "manifest": {
          "name": "org_all_indexes",
          "source": "/opt/org_repo/apps/org_all_indexes",
          "hash_algorithm": "sha256",
          "hash": "23c716241bf4268a407c50f235ec075a9afefdb3246070a58eaf778f4892367a",
          "files": [
           {
            "path": "local/app.conf",
            "mode": 420,
            "size": 110,
            "hash": "62d0bc373a5692d5be91b48e08bee3bafb2cfda0edf6b0246aa2b2241f337a53"
           },
           {
            "path": "local/indexes.conf",
            "mode": 420,
            "size": 27110,
            "hash": "82466c170232a2c42831667302f687dda0f6141f0a9f4c45d39904416cd24150"
           },
           {
            "path": "metadata/local.meta",
            "mode": 420,
            "size": 60,
            "hash": "8e0c1f78b2c3e4414fa4f50f758b886f74570c880cd91f0b12cd1dba251aa8ea"
           }
          ]
         }
        }
        """)
        # Confirm that manifest file can still be read
        stored_manifest = StoredArchiveManifest.read_json_manifest(manifest_v1)
        # Confirm that stored hash value matches the on-disk value
        self.assertFalse(stored_manifest.manifest.recalculate_hash())


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
