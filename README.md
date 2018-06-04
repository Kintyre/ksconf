# Kintyre's Splunk CONFiguration tool

[![Travis](https://img.shields.io/travis/Kintyre/ksconf.svg)](https://travis-ci.org/Kintyre/ksconf/builds)
[![codecov](https://codecov.io/gh/Kintyre/ksconf/branch/master/graph/badge.svg)](https://codecov.io/gh/Kintyre/ksconf)
[![Coverage Status](https://coveralls.io/repos/github/Kintyre/ksconf/badge.svg?branch=master)](https://coveralls.io/github/Kintyre/ksconf?branch=master)
[![Windows Build status](https://ci.appveyor.com/api/projects/status/rlbgstkpf17y8nxh?svg=true)](https://ci.appveyor.com/project/lowell80/ksconf)

This utility handles a number of common Splunk app maintenance tasks in an installable python
package.  Specifically, this tools deals with many of the nuances with storing Splunk apps in a
version control system like git and pointing live Splunk apps to a working tree, merging changes
from the live system's (local) folder to the version controlled (default) folder, and dealing with
more than one layer of "default" (which splunk can't handle natively).

Install with

    pip install KintyreSplunkConfTool

See full install documentation in the [INSTALL.md](./INSTALL.md) document.


Confirm installation with the following command:

    ksconf --help

Docs:

  * [Online docs](https://readthedocs.io/KSConf/latest) - Hosted via ReadTheDocs
  * [Command line reference](./docs/source/cli.md)
