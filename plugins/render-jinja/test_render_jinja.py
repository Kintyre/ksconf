#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals

import os
import sys
import unittest
from pathlib import Path, PurePath

# Allow interactive execution from CLI,  cd tests; ./test_cli.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ksconf.conf.parser import parse_conf
from ksconf.consts import EXIT_CODE_SUCCESS
from ksconf.layer import DotDLayerRoot, layer_file_factory
from tests.cli_helper import TestWorkDir, ksconf_cli
from tests.test_cli_combine import CliKsconfCombineTestCase


class LayerTemplateTestCase(unittest.TestCase):
    def test_simple_mapping(self):
        t_context = {
            "max_size": 83830
        }
        with TestWorkDir() as twd, layer_file_factory:
            layer_file_factory.enable("jinja")
            app_dir = twd.makedir("app01")
            twd.write_file("app01/default.d/10-upstream/props.conf", """\
                [mysourcetype]
                SHOULD_LINEBREAK = false
                """)
            twd.write_file("app01/default.d/20-common/props.conf", """\
                [yoursourcetype]
                TIME_FORMAT = %s
                """)
            twd.write_file("app01/default.d/75-custom-magic/props.conf.j2", """\
                [yoursourcetype]
                TRUNCATE = {{ max_size | default('99') }}
                """)

            layer_root = DotDLayerRoot()
            layer_root.set_root(Path(app_dir))
            layer_root.context.template_variables = t_context
            self.assertListEqual(layer_root.list_layer_names(),
                                 ["10-upstream", "20-common", "75-custom-magic"])
            self.assertEqual(len(layer_root.list_logical_files()), 1)
            self.assertEqual(layer_root.list_logical_files()[0].name, "props.conf")
            self.assertEqual(len(layer_root.list_physical_files()), 3)

            layer = list(layer_root.get_layers_by_name("75-custom-magic"))[0]
            # the .j2; extension has been removed for the logical path
            f = layer.get_file(PurePath("default/props.conf"))

            conf = twd.read_conf(f.resource_path)
            self.assertEqual(conf["yoursourcetype"]["TRUNCATE"], "83830")


class CliKsconfLayerJinja2TestCase(unittest.TestCase):
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

    # Repurpose test case from previous home...
    build_test01 = CliKsconfCombineTestCase.build_test01


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
