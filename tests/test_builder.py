#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals

import json
import os
import sys
import unittest

try:
    # Python 3.3+
    from unittest import mock
except ImportError:
    # Add on for earlier versions
    import mock


# Allow interactive execution from CLI,  cd tests; ./test_builder.py
if __package__ is None:
    sys.path.append(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))

from ksconf.consts import *
from ksconf.util.builder import BuildManager, BuildStep, BuildCacheException
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

    def test_cache_call_once(self):
        self.twd.write_file("src/requirements.txt", "six==1.14.0")
        call_count = [0]
        step = self.build_manager.get_build_step()

        @self.build_manager.cache(inputs=["requirements.txt"], outputs=["lib/six.py"])
        def install_package(build):
            # nonlocal call_count
            call_count[0] += 1
            self.assertFalse(build.source_path, "'source_path' should be absent for cached execution")
            requirements_txt = build.build_path / "requirements.txt"
            self.assertTrue(requirements_txt.exists(), "Missing input file")
            with requirements_txt.open() as fp:
                self.assertEqual(fp.read(), "six==1.14.0")
            # Pretend that pip ran...
            six_py = build.build_path / "lib" / "six.py"
            six_py.parent.mkdir()
            with six_py.open("w") as f:
                f.write("#!/bin/python\n# SIX!\n")

        # Call my new function
        install_package(step)

        six_py = os.path.join(self.build, "lib", "six.py")
        self.assertTrue(os.path.exists(six_py), "Missing {}".format(six_py))
        os.unlink(six_py)
        # Run for second time, with same path
        install_package(step)
        self.assertEqual(call_count[0], 1, "install_package() was run run too many times")
        self.assertTrue(os.path.exists(six_py), "Missing {}".format(six_py))

    def test_cache_expire(self):
        """Mock datetime object to ensure that cache expires so that wrapped funcion is re-run. """
        self.twd.write_file("src/requirements.txt", "six==1.14.0")
        step = self.build_manager.get_build_step()
        call_count = [0]
        @self.build_manager.cache(inputs=["requirements.txt"], outputs=["lib/*.py"], timeout=3600)
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
            with six_py.open("w") as f:
                f.write("#!/bin/python\n# SIX!\n")

        from datetime import datetime, timedelta
        # Make system clock return a time from 10 hours ago
        with mock.patch("ksconf.util.builder.datetime",
                        mock.Mock(now=lambda: datetime.now() - timedelta(hours=10))):
            install_package(step)

        six_py = os.path.join(self.build, "lib", "six.py")
        self.assertTrue(os.path.exists(six_py), "Missing {}".format(six_py))
        os.unlink(six_py)

        # Run for second time, with same path; cache should expire and therefore re-run the install_package()
        install_package(step)
        self.assertEqual(call_count[0], 2, "install_package() should have run 2 times due to cache expiration")
        self.assertTrue(os.path.exists(six_py), "Missing {}".format(six_py))

    def test_change_inputs(self):
        self.twd.write_file("src/requirements.txt", "six")
        step = self.build_manager.get_build_step()

        @self.build_manager.cache(inputs=["requirements.txt"], outputs=["x/"])
        def change_input(build):
            requirements_txt = build.build_path / "requirements.txt"
            with requirements_txt.open("w") as f:
                f.write("Input modified.  This isn't allowed")

        with self.assertRaises(BuildCacheException) as e:
            change_input(step)

        @self.build_manager.cache(inputs=["requirements.txt"], outputs=["x/"])
        def del_input(build):
            requirements_txt = build.build_path / "requirements.txt"
            requirements_txt.unlink()

        with self.assertRaises(BuildCacheException) as e:
            del_input(step)




if __name__ == '__main__':  # pragma: no cover
    unittest.main()