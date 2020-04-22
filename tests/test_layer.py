#!/usr/bin/env python

# For coverage info, can be run with nose2, like so:
#  nose2 -s . -C

from __future__ import absolute_import, unicode_literals

import os
import sys
import unittest

from glob import glob

from io import StringIO
from functools import partial

import ksconf.ext.six as six

# Allow interactive execution from CLI,  cd tests; ./test_layer.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from tests.cli_helper import TestWorkDir

# Stuff for testing
from ksconf.layer import *




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
            dlr.add_layer(src)
        # Note: Layer order matters
        layers = list([l.name for l in dlr.list_layers()])
        self.assertListEqual(layers, ["10-upstream", "20-corp", "60-dept"])
        # Order doesn't matter for file names
        expect_files = [
            "data/ui/nav/default.xml".replace("/", os.path.sep),
            "props.conf",
            "transforms.conf",
        ]
        self.assertListEqual(sorted(dlr.list_files()), sorted(expect_files))


    def test_dotd_simple01(self):
        twd = self.common_data01()
        ta_path = twd.get_path("etc/apps/TA-myproduct")
        dlr = DotDLayerRoot()
        dlr.set_root(ta_path)

        layers = list([l.name for l in dlr.list_layers()])
        self.assertListEqual(layers, ["10-upstream", "20-corp", "60-dept"])


        self.maxDiff = 1000
        # Order doesn't matter for file names
        expect_files = [
            "bin/hello_world.py",
            "README.md",
            "default/data/ui/nav/default.xml",
            "default/props.conf",
            "default/transforms.conf",
        ]
        expect_files = sorted([f.replace("/", os.path.sep) for f in expect_files])
        self.assertListEqual(sorted(dlr.list_files()), sorted(expect_files))















if __name__ == '__main__':  # pragma: no cover
    unittest.main()
