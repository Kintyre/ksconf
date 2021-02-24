#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals

import json
import os
import sys
import unittest

# Allow interactive execution from CLI,  cd tests; ./test_builder.py
if __package__ is None:
    sys.path.append(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))

from ksconf.consts import *
from ksconf.util.builder import BuildManager, BuildStep
from tests.cli_helper import TestWorkDir


class BuilderTestCase(unittest.TestCase):

    def setUp(self):
        self.twd = twd = TestWorkDir()
        self.build_manager = BuildManager()
        self.source = twd.makedir("src")
        self.build = twd.makedir("build")
        self.build_manager.set_folders(self.source, self.build)

    def tearDown(self):
        self.twd.clean()
        del self.twd

    def test_basic01(self):
        self.twd.write_file("src/requirements.txt", "six==1.14.0")
        call_count = [0]

        @self.build_manager.cache(inputs=["requirements.txt"], outputs=["lib/six.py"])
        def install_package(step):
            # nonlocal call_count
            call_count[0] += 1
            requirements_txt = step.build_path / "requirements.txt"
            self.assertTrue(requirements_txt.exists(), "Missing input file")
            with requirements_txt.open() as fp:
                self.assertEqual(fp.read(), "six==1.14.0")
            # Pretend that pip ran...
            six_py = step.build_path / "lib" / "six.py"
            six_py.parent.mkdir()
            six_py.open("w").write("#!/bin/python\n# SIX!\n")

        install_package(BuildStep(self.build))

        six_py = os.path.join(self.build, "lib", "six.py")
        self.assertTrue(os.path.exists(six_py), "Missing {}".format(six_py))

        # Run for second time, with same path
        install_package(BuildStep(self.build))
        self.assertEqual(call_count[0], 1, "install_package() was run run too many times")


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
