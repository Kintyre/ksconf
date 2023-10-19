#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals

import os
import sys
import unittest

from ksconf.layer import layer_file_factory

# Allow interactive execution from CLI,  cd tests; ./test_cli.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksconf.conf.parser import PARSECONF_LOOSE, parse_conf
from ksconf.consts import EXIT_CODE_COMBINE_MARKER_MISSING, EXIT_CODE_SUCCESS
from tests.cli_helper import TestWorkDir, ksconf_cli

try:
    import jinja2
except ImportError:
    jinja2 = None


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

        twd.write_file("etc/apps/Splunk_TA_aws/default.d/10-upstream/alert_actions.conf", """
        [aws_sns_modular_alert]
        is_custom = 1
        label = AWS SNS Alert
        description = Publish search result to AWS SNS
        payload_format = json
        icon_path = appIcon.png
        """)
        twd.write_file("etc/apps/Splunk_TA_aws/default.d/60-dept/alert_actions.conf", """
        [aws_sns_modular_alert]
        param.account = DeptAwsAccount
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
        # Note that this test tests the old shool version of '*.d' processing.  But we must preserve this behavior.
        # Be aware that we pass in 'default.d/*' as a string, and expand the glob vs allowing the shell to handle this
        # and this is _normal_ behavior when dealing with Windows.
        twd = TestWorkDir()
        self.build_test01(twd)
        default = twd.get_path("etc/apps/Splunk_TA_aws/default")
        with ksconf_cli:
            ko = ksconf_cli("combine", "--dry-run", "--target", default, default + ".d/*")
            # Q: Why do we run this once, but not check anything about it?  (To ensure dry-run has no side effects?)
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

            alert_action = twd.read_conf("etc/apps/Splunk_TA_aws-OUTPUT/default/alert_actions.conf")
            self.assertIn("aws_sns_modular_alert", alert_action)
            self.assertEqual(alert_action["aws_sns_modular_alert"]["param.account"], "DeptAwsAccount")  # layer 10
            self.assertEqual(alert_action["aws_sns_modular_alert"]["label"], "AWS SNS Alert")  # layer 60

    @unittest.skipIf(jinja2 is None, "Test requires 'jinja2'")
    def test_combine_dird_with_JINJA(self):
        twd = TestWorkDir()
        self.build_test01(twd)
        template_vars = '{"big_ole_number": 8383}'
        twd.write_file("etc/apps/Splunk_TA_aws/default.d/99-dynamic-magic/props.conf.j2", """
        [aws:config]
        TRUNCATE = {{ big_ole_number }}
        """)
        default = twd.get_path("etc/apps/Splunk_TA_aws")
        target = twd.get_path("etc/apps/Splunk_TA_aws-OUTPUT")
        with ksconf_cli, layer_file_factory:
            ko = ksconf_cli("combine", "--layer-method", "dir.d",
                            "--template-vars", template_vars,
                            "--enable-handler", "jinja",
                            "--target", target, default)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            cfg = parse_conf(target + "/default/props.conf")
            self.assertIn("aws:config", cfg)
            self.assertEqual(cfg["aws:config"]["TRUNCATE"], '8383')

    def test_keep_existing_ds_local_app(self):
        twd = TestWorkDir()
        src = twd.get_path("repo/apps/Splunk_TA_nix")
        target = twd.get_path("etc/deployment-apps/Splunk_TA_nix")

        twd.write_file("repo/apps/Splunk_TA_nix/default/app.conf", r"""
        [install]
        allows_disable = false
        is_configured = true
        state = enabled

        [launcher]
        author = Splunk
        description = The app is Splunk
        version = 7.0.0
        """)
        # Make parent directories
        os.makedirs(twd.get_path("etc/deployment-apps"))

        # First run (creates maker file)
        with ksconf_cli:
            ko = ksconf_cli("combine", "--keep-existing", "local/app.conf",
                            "--target", target, src)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            # Local folder hasn't been created yet
            self.assertFalse(os.path.isdir(twd.get_path("etc/deployment-apps/Splunk_TA_nix/local")))

        # Simulate a 'splunk reload deploy-server'
        twd.write_file("etc/deployment-apps/Splunk_TA_nix/local/app.conf", "# Autogenerated file ")

        with ksconf_cli:
            ko = ksconf_cli("combine", "--keep-existing", "local/app.conf",
                            "--target", target, src)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            cfg = parse_conf(os.path.join(target, "default/app.conf"))
            self.assertIn("install", cfg)
            self.assertEqual(cfg["launcher"]["version"], "7.0.0")

            self.assertEqual(twd.read_file("etc/deployment-apps/Splunk_TA_nix/local/app.conf"),
                             "# Autogenerated file ")

            # This time the file will be removed
            ko = ksconf_cli("combine", "--target", target, src)
            self.assertFalse(os.path.isfile(twd.get_path("etc/deployment-apps/Splunk_TA_nix/local/app.conf")),
                             "local/app.conf should have been removed.")

    def test_combine_conf_spec(self):
        twd = TestWorkDir()
        self.build_test01(twd)

        twd.write_file("etc/apps/Splunk_TA_aws/README.d/10-upstream/custom_config.conf.spec", r"""
            [<stanza_type1>]
            important_field = <str>
            * Some notes about the important field.
            * Required!
            disabled = <bool>
            """)
        twd.write_file("etc/apps/Splunk_TA_aws/README.d/60-dept/custom_config.conf.spec", r"""
            [bookmark::<prefixed_stanza_type>]
            resource = <url>
            category = <str>
            * Label for organization
            disabled = <bool>
            """)

        default = twd.get_path("etc/apps/Splunk_TA_aws")
        target = twd.get_path("etc/apps/Splunk_TA_aws-OUTPUT")
        with ksconf_cli:
            ko = ksconf_cli("combine", "--layer-method", "dir.d", "--target", target, default)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)

            spec_file = twd.get_path("etc/apps/Splunk_TA_aws-OUTPUT/README/custom_config.conf.spec")
            spec = parse_conf(spec_file, profile=PARSECONF_LOOSE)

            self.assertIn("bookmark::<prefixed_stanza_type>", spec)
            self.assertIn("<stanza_type1>", spec)

    def test_require_arg(self):
        with ksconf_cli:
            ko = ksconf_cli("combine", "source-dir")
            self.assertRegex(ko.stderr, "arguments are required: --target")

    def test_missing_marker(self):
        twd = TestWorkDir()
        twd.write_file("source-dir/someapp/default/blah.conf", "[entry]\nboring=yes\n")
        twd.write_file("dest-dir/someapp/default/blah.conf", "[entry]\nboring=yes\n")

        ko = ksconf_cli("combine", twd.get_path("source-dir"), "--target", twd.get_path("dest-dir"))
        self.assertEqual(ko.returncode, EXIT_CODE_COMBINE_MARKER_MISSING)
        self.assertRegex(ko.stderr, r".*Marker file missing\b.*")


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
