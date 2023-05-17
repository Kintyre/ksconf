#!/usr/bin/env python

# For coverage info, can be run with nose2, like so:
#  nose2 -s . -C

from __future__ import absolute_import, unicode_literals

import contextlib
import os
import sys
import unittest
from glob import glob
from io import StringIO
from os import fspath
from pathlib import Path, PurePath

# Allow interactive execution from CLI,  cd tests; ./test_layer.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Stuff for testing
from ksconf.layer import (DirectLayerRoot, DotDLayerRoot, LayerFilter,
                          TemplatedLayerFile, path_in_layer)
from tests.cli_helper import TestWorkDir


def np(p, nominal="/"):
    """ Transform a normalize path into an OS-specific path format """
    if os.path.sep != nominal:
        p = p.replace(nominal, os.path.sep)
    return p


def npl(iterable, nominal="/"):
    return [np(i, nominal) for i in iterable]


def fspaths(iterable):
    return (fspath(p) for p in iterable)


@contextlib.contextmanager
def set_template_context(d):
    _prev_context = TemplatedLayerFile.template_context
    TemplatedLayerFile.template_context = d
    yield
    TemplatedLayerFile.template_context = _prev_context


class HelperFunctionsTestCase(unittest.TestCase):

    def test_path_in_layer_01(self):
        path = Path(np("default/data/ui/nav/default.xml"))
        self.assertEqual(path_in_layer(Path("default"), path), Path(np("data/ui/nav/default.xml")))
        self.assertEqual(path_in_layer(Path("bin"), path), None)
        self.assertEqual(path_in_layer(Path(np("a/path/longer/than/the/given/path")), path), None)

    def test_path_in_layer_nulls(self):
        self.assertEqual(path_in_layer(None, "path"), "path")

    def test_layerfilter_include(self):
        class mocklayer:
            def __init__(self, name):
                self.name = name
        layers = [mocklayer(l) for l in [
            "10-upstream",
            "20-kintyre",
            "30-indexers",
            "30-searchhead",
            "30-cloudinputs"
        ]]

        def eval_layer_filter(rules):
            layerfilter = LayerFilter()
            for rule in rules:
                layerfilter.add_rule(*rule)
            return [i.name for i in layers if layerfilter.evaluate(i)]

        # Simple include/exclude test
        self.assertListEqual(eval_layer_filter([("include", "20-kintyre")]),
                             ["20-kintyre"])
        self.assertListEqual(eval_layer_filter([("exclude", "20-kintyre")]),
                             ["10-upstream", "30-indexers", "30-searchhead", "30-cloudinputs"])

        # Test wildcards
        self.assertListEqual(eval_layer_filter([("exclude", "30-*")]),
                             ["10-upstream", "20-kintyre"])
        self.assertListEqual(eval_layer_filter([("include", "*search*")]),
                             ["30-searchhead"])

        # Test chained rules
        self.assertListEqual(eval_layer_filter([("exclude", "30-*"), ("include", "30-indexers")]),
                             ["10-upstream", "20-kintyre", "30-indexers"])

        # Default to all if NO rules provided
        self.assertListEqual(eval_layer_filter([]),
                             ["10-upstream", "20-kintyre", "30-indexers", "30-searchhead", "30-cloudinputs"])


class LayerTemplateTestCase(unittest.TestCase):
    def test_simple_mapping(self):
        t_context = {
            "max_size": 83830,
            "happy": {
                "things": "YO!"
            }
        }
        with TestWorkDir() as twd, set_template_context(t_context):
            print(f"CONTEXT:  {TemplatedLayerFile.template_context}")
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
                # {{ happy }}
                TRUNCATE = {{ max_size | default('99') }}
                """)

            layer_root = DotDLayerRoot()
            layer_root.set_root(Path(app_dir))
            self.assertListEqual(layer_root.list_layer_names(),
                                 ["10-upstream", "20-common", "75-custom-magic"])
            self.assertEqual(len(layer_root.list_logical_files()), 1)
            self.assertEqual(layer_root.list_logical_files()[0].name, "props.conf")
            self.assertEqual(len(layer_root.list_physical_files()), 3)

            print(layer_root.list_logical_files()[0])
            print(list(layer_root.get_file(PurePath("default/props.conf"))))

            layer = list(layer_root.get_layers_by_name("75-custom-magic"))[0]
            # the .j2; extension has been removed for the logical path
            f = layer.get_file(PurePath("default/props.conf"))

            print("OUTPUT!")
            print(f.resource_path.read_text())
            conf_text = f.resource_path.read_text()

            from ksconf.conf.parser import parse_conf
            conf = parse_conf(StringIO(conf_text))
            # Can't figure out why this isn't working
            #conf = twd.read_conf(f.resource_path)
            self.assertEqual(conf["yoursourcetype"]["TRUNCATE"], "83830")


class DefaultLayerTestCase(unittest.TestCase):
    """ Test the DefaultLayerRoot class """

    def common_data01(self):
        twd = TestWorkDir()

        twd.write_file("etc/apps/TA-myproduct/README.md", """
        My Product Add on
        =================

        ....
        """)
        twd.write_file("etc/apps/TA-myproduct/bin/hello_world.py", """
        print("HELLO WORLD -- a fake modular input")
        """)

        # 10-* layer
        twd.write_file("etc/apps/TA-myproduct/default.d/10-upstream/props.conf", """
        [aws:config]
        SHOULD_LINEMERGE = false
        TRUNCATE = 8388608
        FIELDALIAS-region-for-aws-config = awsRegion AS region
        """)
        twd.write_file("etc/apps/TA-myproduct/default.d/10-upstream/data/ui/nav/default.xml", """
        <nav search_view="search" color="#65A637">
        <view name="Inputs" default="true" label="Inputs" />
        </nav>
        """)
        # 20-* layer
        twd.write_file("etc/apps/TA-myproduct/default.d/20-corp/props.conf", """
        [aws:config]
        TZ = UTC
        # Corp want's punct to be enabled globally
        ANNOTATE_PUNCT = true
        """)
        # 60-* layer
        twd.write_file("etc/apps/TA-myproduct/default.d/60-dept/props.conf", """
        [aws:config]
        TRANSFORMS-truncate = aws-truncate-em
        INGEST-EVAL = _raw=substr(_raw,0,100)
        """)
        twd.write_file("etc/apps/TA-myproduct/default.d/60-dept/transforms.conf", """
        [aws-truncate-em]
        INGEST-EVAL = _raw=substr(_raw,1,100)
        """)
        twd.write_file("etc/apps/TA-myproduct/default.d/60-dept/data/ui/nav/default.xml", """
        <nav search_view="search" color="#65A637">

        <view name="My custom view" />
        <view name="Inputs" default="true" label="Inputs" />
        <view name="Configuration" default="false" label="Configuration" />
        <view name="search" default="false" label="Search" />

        </nav>
        """)
        return twd

    def test_defaultlayer_simple01(self):
        twd = self.common_data01()
        default = twd.get_path("etc/apps/TA-myproduct/default")

        dlr = DirectLayerRoot()
        # Take CLI args and apply to root
        for src in sorted(glob(os.path.join(default + ".d", "*"))):
            dlr.add_layer(Path(src))
        # Note: Layer order matters
        layers = list([l.name for l in dlr.list_layers()])
        self.assertListEqual(layers, ["10-upstream", "20-corp", "60-dept"])
        # Order doesn't matter for file names
        expect_files = [
            np("data/ui/nav/default.xml"),
            "props.conf",
            "transforms.conf",
        ]
        self.assertListEqual(sorted(fspaths(dlr.list_files())), sorted(expect_files))

    def test_dotd_simple01(self):
        twd = self.common_data01()
        ta_path = twd.get_path("etc/apps/TA-myproduct")
        dlr = DotDLayerRoot()
        dlr.set_root(ta_path)

        layers = list([l.name for l in dlr.list_layers()])
        self.assertListEqual(layers, ["10-upstream", "20-corp", "60-dept"])

        self.maxDiff = 1000
        # Order doesn't matter for file names
        expect_files = npl([
            "bin/hello_world.py",
            "README.md",
            "default/data/ui/nav/default.xml",
            "default/props.conf",
            "default/transforms.conf",
        ])
        expect_files = sorted([np(f) for f in expect_files])
        self.assertListEqual(sorted(fspaths(dlr.list_files())), sorted(expect_files))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
