#!/usr/bin/env python
from setuptools import setup

setup(name="KintyreSplunkConfTool",
      version="0.3.1",
      description="Kintyre's Splunk Configuration Tool",
      author="Lowell Alleman",
      author_email="lowell@kintyre.co",
      url="https://github.com/Kintyre/ksconf",
      py_modules=[
        "ksconf",
       ],
      # Not required, but useful.
      # install_requires=[ "argcomplete "],
      entry_points={
        "console_scripts" : [
            "ksconf = ksconf:cli",
        ]
      },
    )
