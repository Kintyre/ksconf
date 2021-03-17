#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals

import os
import sys
import unittest

# Allow interactive execution from CLI,  cd tests; ./test_cli.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksconf.consts import *
from tests.cli_helper import *


class CliKsconfCombineTestCase(unittest.TestCase):

    def build_test01(self, twd):
        twd.write_file("etc/apps/Splunk_TA_aws/default.d/10-upstream/props.conf", r"""
        [aws:config]
        SHOULD_LINEMERGE = false
        TRUNCATE = 8388608
        TIME_PREFIX = configurationItemCaptureTime"\s*:\s*"
        TIME_FORMAT = %Y-%m-%dT%H:%M:%S.%3NZ
        TZ = GMT
        MAX_TIMESTAMP_LOOKAHEAD = 28
        KV_MODE = json
        ANNOTATE_PUNCT = false

        FIELDALIAS-dest = resourceType AS dest
        FIELDALIAS-object = resourceId AS object
        FIELDALIAS-object_id = ARN AS object_id
        EVAL-change_type = "configuration"
        EVAL-dvc = "AWS Config"
        EVAL-status="success"
        LOOKUP-action= aws_config_action_lookup status AS configurationItemStatus OUTPUT action
        LOOKUP-object_category = aws_config_object_category_lookup type AS resourceType OUTPUT object_category

        # unify account ID field
        FIELDALIAS-aws-account-id = awsAccountId as aws_account_id
        FIELDALIAS-region-for-aws-config = awsRegion AS region
        """)
        twd.write_file("etc/apps/Splunk_TA_aws/default.d/10-upstream/data/ui/nav/default.xml", """
        <nav search_view="search" color="#65A637">

        <view name="Inputs" default="true" label="Inputs" />
        <view name="Configuration" default="false" label="Configuration" />
        <view name="search" default="false" label="Search" />

        </nav>
        """)
        # In the future there will be a more efficient way to handle the global 'ANNOTATE_PUCT' scenario
        twd.write_file("etc/apps/Splunk_TA_aws/default.d/20-corp/props.conf", """
        [aws:config]
        TZ = UTC
        # Corp want's punct to be enabled globally
        ANNOTATE_PUNCT = true
        """)
        twd.write_file("etc/apps/Splunk_TA_aws/default.d/60-dept/props.conf", """
        [aws:config]
        # Our config is bigger than yours!
        TRUNCATE = 9999999
        """)
        twd.write_file("etc/apps/Splunk_TA_aws/default.d/60-dept/data/ui/nav/default.xml", """
        <nav search_view="search" color="#65A637">

        <view name="My custom view" />
        <view name="Inputs" default="true" label="Inputs" />
        <view name="Configuration" default="false" label="Configuration" />
        <view name="search" default="false" label="Search" />

        </nav>
        """)

    def test_combine_3dir(self):
        twd = TestWorkDir()
        self.build_test01(twd)
        default = twd.get_path("etc/apps/Splunk_TA_aws/default")
        with ksconf_cli:
            ko = ksconf_cli("combine", "--dry-run", "--target", default, default + ".d/*")
            ko = ksconf_cli("combine", "--target", default, default + ".d/*")
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            cfg = parse_conf(twd.get_path("etc/apps/Splunk_TA_aws/default/props.conf"))
            self.assertIn("aws:config", cfg)
            self.assertEqual(cfg["aws:config"]["ANNOTATE_PUNCT"], "true")
            self.assertEqual(cfg["aws:config"]["EVAL-change_type"], '"configuration"')
            self.assertEqual(cfg["aws:config"]["TRUNCATE"], '9999999')
            nav_content = twd.read_file("etc/apps/Splunk_TA_aws/default/data/ui/nav/default.xml")
            self.assertIn("My custom view", nav_content)

        twd.write_conf("etc/apps/Splunk_TA_aws/default.d/99-theforce/props.conf", {
            "aws:config": {"TIME_FORMAT": "%Y-%m-%dT%H:%M:%S.%6NZ"}
        })
        twd.write_file("etc/apps/Splunk_TA_aws/default.d/99-theforce/data/ui/nav/default.xml", """
        <nav search_view="search" color="#65A637">
        <view name="My custom view" />
        <view name="Inputs" default="true" label="Inputs" />
        <view name="Configuration" default="false" label="Configuration" />
        </nav>
        """)
        twd.write_file("etc/apps/Splunk_TA_aws/default/data/dead.conf", "# File to remove")
        twd.write_file("etc/apps/Splunk_TA_aws/default/data/tags.conf", "# Locally created file")

        twd.write_file("etc/apps/Splunk_TA_aws/default.d/99-blah/same.txt", "SAME TEXT")
        twd.write_file("etc/apps/Splunk_TA_aws/default/same.txt", "SAME TEXT")

        twd.write_file("etc/apps/Splunk_TA_aws/default.d/99-blah/binary.bin", b"#BINARY \xff \x00")
        twd.write_file("etc/apps/Splunk_TA_aws/default/binary.bin", b"#BINARY NEW \x00 \xff \xFB")
        with ksconf_cli:
            ko = ksconf_cli("combine", "--dry-run", "--target", default, default + ".d/*")
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegex(ko.stdout, r'[\r\n][-]\s*<view name="search"')
            self.assertRegex(ko.stdout, r'[\r\n][-] ?[\r\n]')  # Remove empty lines from nav
            self.assertRegex(ko.stdout, r"[\r\n][+]TIME_FORMAT = [^\r\n]+%6N")
        with ksconf_cli:
            ko = ksconf_cli("combine", "--target", default, default + ".d/*")

    def test_sort_order(self):
        "Confirm that single input files are copied as-is"
        twd = TestWorkDir()
        default = twd.get_path("input")
        target = twd.get_path("output")
        unique_conf = [
            "z = 1",
            " b=?  ",
            "a = 9"]
        twd.write_file("input/unique.conf",
                       "\n".join(unique_conf))
        with ksconf_cli:
            ko = ksconf_cli("combine", "--layer-method", "disable", "--banner", "",
                            "--target", target, default)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            data = twd.read_file("output/unique.conf").splitlines()
            self.assertListEqual(unique_conf, data)

    def test_combine_dird(self):
        twd = TestWorkDir()
        self.build_test01(twd)
        default = twd.get_path("etc/apps/Splunk_TA_aws")
        target = twd.get_path("etc/apps/Splunk_TA_aws-OUTPUT")
        with ksconf_cli:
            ko = ksconf_cli("combine", "--layer-method", "dir.d", "--dry-run", "--target", target, default)
            ko = ksconf_cli("combine", "--layer-method", "dir.d", "--target", target, default)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            cfg = parse_conf(target + "/default/props.conf")
            self.assertIn("aws:config", cfg)
            self.assertEqual(cfg["aws:config"]["ANNOTATE_PUNCT"], "true")
            self.assertEqual(cfg["aws:config"]["EVAL-change_type"], '"configuration"')
            self.assertEqual(cfg["aws:config"]["TRUNCATE"], '9999999')
            nav_content = twd.read_file("etc/apps/Splunk_TA_aws-OUTPUT/default/data/ui/nav/default.xml")
            self.assertIn("My custom view", nav_content)

    def test_require_arg(self):
        with ksconf_cli:
            ko = ksconf_cli("combine", "source-dir")
            self.assertRegex(ko.stderr, "Must provide [^\r\n]+--target")

    def test_missing_combine_dir(self):
        twd = TestWorkDir()
        twd.write_file("source-dir/someapp/default/blah.conf", "[entry]\nboring=yes\n")
        twd.write_file("dest-dir/someapp/default//blah.conf", "[entry]\nboring=yes\n")

        ko = ksconf_cli("combine", twd.get_path("source-dir"), "--target", twd.get_path("dest-dir"))
        self.assertEqual(ko.returncode, EXIT_CODE_COMBINE_MARKER_MISSING)
        self.assertRegex(ko.stderr, r".*Marker file missing\b.*")


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
