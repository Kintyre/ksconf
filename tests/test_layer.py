#!/usr/bin/env python

# For coverage info, can be run with nose2, like so:
#  nose2 -s . -C

from __future__ import absolute_import, unicode_literals

import os
import sys
import unittest
from glob import glob
from os import fspath
from pathlib import Path, PurePath

# Allow interactive execution from CLI,  cd tests; ./test_layer.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


try:
    import jinja2
except ImportError:
    jinja2 = None


# Stuff for testing
from ksconf.layer import (DotDLayerCollection, Layer, LayerFilter,
                          MultiDirLayerCollection, layer_file_factory)
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


class HelperFunctionsTestCase(unittest.TestCase):

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
    @unittest.skipIf(jinja2 is None, "Test requires 'jinja2'")
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

            collection = DotDLayerCollection()
            collection.set_root(Path(app_dir))
            collection.context.template_variables = t_context
            self.assertListEqual(collection.list_layer_names(),
                                 ["10-upstream", "20-common", "75-custom-magic"])
            self.assertEqual(len(collection.list_logical_files()), 1)
            self.assertEqual(collection.list_logical_files()[0].name, "props.conf")
            self.assertEqual(len(collection.list_physical_files()), 3)

            layer = list(collection.get_layers_by_name("75-custom-magic"))[0]
            # the .j2; extension has been removed for the logical path
            f = layer.get_file(PurePath("default/props.conf"))

            conf = twd.read_conf(f.resource_path)
            self.assertEqual(conf["yoursourcetype"]["TRUNCATE"], "83830")


class DotDLayerTestCase(unittest.TestCase):

    def test_filtering(self):
        with TestWorkDir() as twd, layer_file_factory:
            app_dir = twd.makedir("app01")
            twd.write_file("app01/default.d/10-upstream/props.conf", """\
                [mysourcetype]
                SHOULD_LINEBREAK = false
                """)
            twd.write_file("app01/default.d/10-upstream/app.conf", """\
                [ui]
                label = APP 001

                [launcher]
                author = lowell
                version = 0.0.1
                """)
            twd.write_file("app01/default.d/20-common/indexes.conf", """\
                [myindex]
                coldPath = $SPLUNK_DB/$_index_name/colddb
                homePath = $SPLUNK_DB/$_index_name/db
                thawedPath = $SPLUNK_DB/$_index_name/thaweddb
                """)
            twd.write_file("app01/default.d/75-custom-magic/props.conf", """\
                [yoursourcetype]
                TRUNCATE = 5
                [minesourcetype]
                rename = yoursourcetype
                """)
            twd.write_file("app01/default.d/88-single-file/fields.conf", r"""\
                [From]
                TOKENIZER = (\w[\w\.\-]*@[\w\.\-]*\w)
                """)

            collection = DotDLayerCollection()
            collection.set_root(Path(app_dir))
            self.assertListEqual(collection.list_layer_names(),
                                 ["10-upstream", "20-common", "75-custom-magic", "88-single-file"])
            self.assertEqual(len(collection.list_logical_files()), 4)
            self.assertEqual(len(collection.list_physical_files()), 5)

            fn_props = PurePath("default/props.conf")
            self.assertEqual(len(collection.get_files(fn_props)), 2)

            layer: Layer = list(collection.get_layers_by_name("75-custom-magic"))[0]
            f = layer.get_file(fn_props)
            conf = twd.read_conf(f.resource_path)
            self.assertEqual(conf["yoursourcetype"]["TRUNCATE"], "5")

            collection.apply_layer_filter(lambda layer: layer.name != "20-common")
            self.assertEqual(len(collection.list_logical_files()), 3)
            self.assertNotIn("20-common", collection.list_layer_names())

            self.assertEqual(collection.list_all_layer_names(),
                             ["10-upstream", "20-common", "75-custom-magic", "88-single-file"])

            collection.apply_path_filter(lambda p: p.name != "fields.conf")
            self.assertEqual(len(collection.list_logical_files()), 2)
            self.assertNotIn("88-single-file", collection.list_layer_names())

            self.assertEqual(collection.list_layer_names(),
                             ["10-upstream", "75-custom-magic"])

            # The '*_all_*' version should report all the layers, even those filtered out
            self.assertEqual(collection.list_all_layer_names(),
                             ["10-upstream", "20-common", "75-custom-magic", "88-single-file"])


class MultiDirLayerTestCase(unittest.TestCase):
    """ Test the MultiDirLayerCollection class """

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

        lc = MultiDirLayerCollection()
        # Take CLI args and apply to root
        for src in sorted(glob(os.path.join(default + ".d", "*"))):
            lc.add_layer(Path(src))
        # Note: Layer order matters
        layers = list([l.name for l in lc.list_layers()])
        self.assertListEqual(layers, ["10-upstream", "20-corp", "60-dept"])
        # Order doesn't matter for file names
        expect_files = [
            np("data/ui/nav/default.xml"),
            "props.conf",
            "transforms.conf",
        ]
        self.assertListEqual(sorted(fspaths(lc.list_files())), sorted(expect_files))

    def test_dotd_simple01(self):
        twd = self.common_data01()
        ta_path = twd.get_path("etc/apps/TA-myproduct")
        lc = DotDLayerCollection()
        lc.set_root(ta_path)

        layers = list([l.name for l in lc.list_layers()])
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
        self.assertListEqual(sorted(fspaths(lc.list_files())), sorted(expect_files))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
