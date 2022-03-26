# Ksconf Splunk CONFiguration tool

[![Build](https://github.com/Kintyre/ksconf/actions/workflows/build.yml/badge.svg)](https://github.com/Kintyre/ksconf/actions/workflows/build.yml)
[![PyPI](https://img.shields.io/pypi/v/ksconf.svg)](https://pypi.org/project/ksconf/)
[![codecov](https://codecov.io/gh/Kintyre/ksconf/branch/master/graph/badge.svg)](https://codecov.io/gh/Kintyre/ksconf)
[![Coverage Status](https://coveralls.io/repos/github/Kintyre/ksconf/badge.svg?branch=master)](https://coveralls.io/github/Kintyre/ksconf?branch=master)
[![Windows Build status](https://ci.appveyor.com/api/projects/status/rlbgstkpf17y8nxh/branch/master?svg=true)](https://ci.appveyor.com/project/lowell80/ksconf/branch/master)
[![Documentation Status](https://readthedocs.org/projects/ksconf/badge/?version=latest)](https://ksconf.readthedocs.io/en/latest/?badge=latest)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/ksconf.svg)](https://pypi.org/project/ksconf/)
![PyPI - Downloads](https://img.shields.io/pypi/dm/ksconf.svg)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![Snyk Score](https://snyk.io/advisor/python/ksconf/badge.svg)](https://snyk.io/advisor/python/ksconf)
[![PEP8](https://img.shields.io/badge/code%20style-pep8-orange.svg)](https://www.python.org/dev/peps/pep-0008/)


![Ksconf logo][logo]

This utility handles a number of common Splunk app maintenance tasks in an installable python
package. Specifically, this tools deals with many of the nuances of storing Splunk apps in a
version control system like git and pointing live Splunk apps to a working tree. Merging changes
from the live system's (local) folder to the version controlled (default) folder and dealing with
more than one layer of "default" are all supported tasks which are not native to Splunk.


## Install

**Splunk:**

 1. Download and install [KSCONF App for Splunk](https://splunkbase.splunk.com/app/4383/)
 2. Run the command:  `splunk cmd python3 $SPLUNK_HOME/etc/apps/ksconf/bin/install.py`

**Python:**

    pip install ksconf

**Confirm installation** with the following command:

    ksconf --help

## Resources

Docs:

  * [Official docs](https://ksconf.readthedocs.io/en/latest/) hosted via ReadTheDocs.io
  * [Command line reference](./docs/source/dyn/cli.rst)
  * [Installation docs](./docs/source/install.rst)
  * [Change log](./docs/source/changelog.rst)


Need help?

 * Ask questions on [GitHub](https://github.com/Kintyre/ksconf/issues/new?labels=question) or [Splunk Answers](https://answers.splunk.com/app/questions/4383.html)
 * Chat about [#ksconf](https://slack.com/app_redirect?channel=CDVT14KUN) on Splunk's [Slack](https://splunk-usergroups.slack.com) channel


Get involved:

 * [Report bugs](https://github.com/Kintyre/ksconf/issues/new?template=bug.md)
 * Review [known bugs](https://github.com/Kintyre/ksconf/labels/bug)
 * [Request new features](https://github.com/Kintyre/ksconf/issues/new?template=feature-request.md&labels=enhancement)
 * [Contribute code](./docs/source/devel.md)


Presentations:

* About ksconf:
  * [The joys and pitfalls of managing your Splunk deployment with Git](http://kintyre.rocks/70d87) Philly Splunk Meetup - June 6, 2018
  * [Managing Splunk Deployments With Git and KSCONF](https://youtu.be/-NIME9XRqlo) ![YouTube Video Likes](https://img.shields.io/youtube/likes/-NIME9XRqlo?logo=youtube&style=flat-square)
    ([slides](https://kintyre.rocks/ksconf18)) Splunk .conf bsides talk - Oct 2, 2018

* Honorable mentions:
  * DEV1132B - How To Become the Best SPL Reviewer ([slides](https://conf.splunk.com/files/2021/slides/DEV1132B.pdf) | [video](https://conf.splunk.com/files/2021/recordings/DEV1132B.mp4) ) - Splunk .conf 2021, Samsung Electronics  (slides 10-19)


[logo]: docs/images/logo.png
