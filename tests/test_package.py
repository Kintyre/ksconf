#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals

import os
import sys
import tarfile
import unittest
from io import StringIO
from pathlib import Path

from ksconf.layer import DotDLayerCollection, LayerFilter, MultiDirLayerCollection
from ksconf.package import AppPackager

# Allow interactive execution from CLI,  cd tests; ./test_cli.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksconf.consts import EXIT_CODE_SUCCESS
from tests.cli_helper import TestWorkDir


class PackageTest(unittest.TestCase):

    @staticmethod
    def build_basic_app_01(twd, app_name='.', folder="default", metadata=False):
        twd.write_file(f"{app_name}/{folder}/savedsearches.conf", r"""
        [my_search]
        search = noop
        """)
        twd.write_file(f"{app_name}/{folder}/app.conf", r"""
        [ui]
        label = My cool app

        [launcher]
        author = lowell
        description = some text that barely shows up anywhere in splunk
        version = 0.0.1

        [package]
        id = my_app_on_splunkbase
        check_for_updates = 1
        """)
        twd.write_file(f"{app_name}/{folder}/data/ui/views/mrs_dash.xml", r"""
        <dashboard>
        <row>
        <table>
        <search>
        <query>index=fav sourcetype=seasoning</query>
        </table>
        </row>
        </dashboard>
        """)
        if metadata:
            twd.write_file(f"{app_name}/{metadata}/{metadata}.meta", r"""
            []
            system = export
            """)

    def build_dird_test01(self, twd):
        twd.write_file("Splunk_TA_aws/default.d/10-upstream/props.conf", r"""
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
        twd.write_file("Splunk_TA_aws/default.d/10-upstream/data/ui/nav/default.xml", """
        <nav search_view="search" color="#65A637">

        <view name="Inputs" default="true" label="Inputs" />
        <view name="Configuration" default="false" label="Configuration" />
        <view name="search" default="false" label="Search" />

        </nav>
        """)
        # In the future there will be a more efficient way to handle the global 'ANNOTATE_PUCT' scenario
        twd.write_file("Splunk_TA_aws/default.d/20-corp/props.conf", """
        [aws:config]
        TZ = UTC
        # Corp want's punct to be enabled globally
        ANNOTATE_PUNCT = true
        """)
        twd.write_file("Splunk_TA_aws/default.d/60-dept/props.conf", """
        [aws:config]
        # Our config is bigger than yours!
        TRUNCATE = 9999999
        """)

        twd.write_file("Splunk_TA_aws/default.d/10-upstream/alert_actions.conf", """
        [aws_sns_modular_alert]
        is_custom = 1
        label = AWS SNS Alert
        description = Publish search result to AWS SNS
        payload_format = json
        icon_path = appIcon.png
        """)
        twd.write_file("Splunk_TA_aws/default.d/60-dept/alert_actions.conf", """
        [aws_sns_modular_alert]
        param.account = DeptAwsAccount
        """)

        twd.write_file("Splunk_TA_aws/default.d/60-dept/data/ui/views/my_dept_view.xml", """
        <dashboard>
            <row><html><h2>TBD</h2></html></row>
        </dashboard>
        """)

    def test_package_simple_from_source(self):
        twd = TestWorkDir()
        self.build_basic_app_01(twd, folder="default")

        log_out = StringIO()
        with AppPackager(twd.get_path("."), "my_app_on_splunkbase", log_out, predictable_mtime=False) as packager:
            packager.combine(twd.get_path("."), [], layer_method="disable")
            packager.check()
            tarball = packager.make_archive(twd.get_path("my_app_on_splunkbase-{{version}}.tgz"))

        self.assertTrue(os.path.basename(tarball), "my_app_on_splunkbase-0.0.1.tgz")
        self.assertTrue(os.path.isfile(tarball))
        with tarfile.open(tarball, "r:gz") as tf:
            names = tf.getnames()
            self.assertIn("my_app_on_splunkbase/default/app.conf", names)
            self.assertNotIn("my_app_on_splunkbase/local/app.conf", names)

    def test_package_simple_explict_layer_collection(self):
        twd = TestWorkDir()
        self.build_basic_app_01(twd, "my_app", "default")
        log_out = StringIO()

        lc = MultiDirLayerCollection()
        lc.add_layer(Path(twd.get_path("my_app")))

        with AppPackager(twd.get_path("."), "my_app_on_splunkbase", log_out, predictable_mtime=False) as packager:
            packager.combine_from_layer(lc)
            packager.update_app_conf(version="1.2.3")
            packager.check()
            tarball = packager.make_archive(twd.get_path("my_app_on_splunkbase-{{version}}.tgz"))

        self.assertTrue(os.path.basename(tarball), "my_app_on_splunkbase-1.2.3.tgz")
        self.assertTrue(os.path.isfile(tarball))
        with tarfile.open(tarball, "r:gz") as tf:
            names = tf.getnames()
            self.assertIn("my_app_on_splunkbase/default/app.conf", names)
            self.assertIn("my_app_on_splunkbase/default/data/ui/views/mrs_dash.xml", names)
            self.assertNotIn("my_app_on_splunkbase/local/app.conf", names)

    def test_package_dird_explict_layer_collection(self):
        twd = TestWorkDir()
        self.build_dird_test01(twd)
        # log_out = StringIO()

        def pkg_with_filter(*filters):
            lc = DotDLayerCollection()
            lc.set_root(Path(twd.get_path("Splunk_TA_aws")))
            lf = LayerFilter()
            for fltr in filters:
                lf.add_rule(*fltr)
            lc.apply_filter(lf)
            with AppPackager(twd.get_path("."), "Splunk_TA_aws", sys.stdout) as packager:
                packager.combine_from_layer(lc)
                packager.update_app_conf(version="1.2.3")
                packager.check()
                tarball = packager.make_archive(twd.get_path("Splunk_TA_aws-{{version}}.tgz"))
            return lc, packager, tarball

        lc, packager, tarball = pkg_with_filter(("include", "10-upstream"))
        self.assertEqual(lc.list_all_layer_names(), ["10-upstream", "20-corp", "60-dept"])
        self.assertEqual(lc.list_layer_names(), ["10-upstream"])
        self.assertTrue(os.path.basename(tarball), "Splunk_TA_aws-1.2.3.tgz")
        self.assertTrue(os.path.isfile(tarball))
        with tarfile.open(tarball, "r:gz") as tf:
            names = tf.getnames()
            self.assertIn("Splunk_TA_aws/default/app.conf", names)
            self.assertIn("Splunk_TA_aws/default/alert_actions.conf", names)
            self.assertNotIn("Splunk_TA_aws/default/data/ui/views/my_dept_view.xml", names)

        lc, packager, tarball = pkg_with_filter(("exclude", "20-corp"))
        self.assertEqual(lc.list_all_layer_names(), ["10-upstream", "20-corp", "60-dept"])
        self.assertEqual(lc.list_layer_names(), ["10-upstream", "60-dept"])
        self.assertTrue(os.path.basename(tarball), "Splunk_TA_aws-1.2.3.tgz")
        self.assertTrue(os.path.isfile(tarball))
        with tarfile.open(tarball, "r:gz") as tf:
            names = tf.getnames()
            self.assertIn("Splunk_TA_aws/default/app.conf", names)
            self.assertIn("Splunk_TA_aws/default/alert_actions.conf", names)
            self.assertIn("Splunk_TA_aws/default/data/ui/views/my_dept_view.xml", names)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
