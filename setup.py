#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals

import os
import re
from textwrap import dedent

from setuptools import setup

from ksconf.setup_entrypoints import get_entrypoints_setup

package_name = "kintyre-splunk-conf" if os.getenv("BUILD_OLD_PACKAGE") == "1" else "ksconf"

if package_name == "ksconf":
    package_rename_message = "Earlier version of this project were packaged as " \
        "[kintyre-splunk-conf](https://pypi.org/project/kintyre-splunk-conf) prior to v0.10.0"
else:
    package_rename_message = dedent(f"""
    ## Package rename
    This package has been renamed [ksconf](https://pypi.org/project/ksconf/) starting with v0.10.
    Please switch to this new package using the upgrade steps listed below.

    ## Suggested upgrade steps:
    ```sh
    pip uninstall {package_name}
    pip install ksconf
    ```

    ## Who should keep using {package_name}?
    For the time being, you can still install and upgrade the latest release of
    ksconf using the `{package_name}` package.

    Note that as of the v0.10 release, only Python 3.7 and higher are supported.
    If you need a version of ksconf that works with Python 2.7 & Python 3.6,
    then you should use {package_name} prior to v0.10.  We suggest that everyone
    else should upgrade to the latest `ksconf` package.

    Side note:  Attempts to make {package_name} simply install the new ksconf
    package under the covers resulted in an unusable deployment.  So for now
    we are building two identical packages under different names.  In the next
    minor release you can expect additional onscreen warnings about the package
    rename at every invocation.

    ## Moving on ...
    """)


def get_ver(_allow_git_fetch=True):
    # Todo: There has to be a better library/method of doing this junk.
    from ksconf.vc.git import git_cmd
    ver_file = os.path.join("ksconf", "_version.py")
    # git_sha1 = git_cmd(["rev-parse", "HEAD"]).stdout[:12]
    vc_info = git_cmd(["show", "-s", "--abbrev=8", "--format=Git SHA1 %h committed on %cd",
                       "--date=format:%Y-%m-%d", "HEAD"]).stdout.strip()
    gitout = git_cmd(["describe", "--tags", "--always", "--dirty"])
    version = gitout.stdout.strip()
    version = version.lstrip("v")   # Tags format is v0.0.0
    del gitout

    # If version is hex string, assume there's an issue (aka running from pre-commit's install)
    # Pre-commit has it's own shallow clone that doesn't check out that tags we need to build the
    # package.  See https://github.com/pre-commit/pre-commit/issues/2610
    # Alternate pre-commit detection ideas: env PRE_COMMIT=1, or "pre-commit" in VIRTUAL_ENV or PATH
    if re.match(r'^[a-f0-9]+$', version):
        if _allow_git_fetch:
            # Fallback to valid, but silly version number; This seems better than failing
            print(f"Found unlikely version '{version}'.  Fetching git tags")
            git_cmd(["fetch", "--tags"])
            return get_ver(_allow_git_fetch=False)
        else:
            print("Can't determine version from git repository!")
            version = "0.0.0"

    # replace hash with local version format
    # XXX:  Wow. this needs unittests.  smh
    version = re.sub(r'-(\d+)-g([a-f0-9]+)((?:-dirty)?)', r'.dev\1+\2\3', version)
    version = re.sub(r'(\d+\.\d+)-dirty$', r'\1.dev0+dirty', version)
    version = version.replace("-dirty", ".dirty")
    print(f"Version:  {version}")
    build_no = 0
    ci_build_no = os.environ.get("GITHUB_RUN_NUMBER", None)
    if ci_build_no:
        build_no = 1000 + int(ci_build_no)
    code_block = dedent(f"""\
        # Version file autogenerated by the build process
        version = {version!r}
        build = {build_no!r}
        vcs_info = {vc_info!r}
        package_name = {package_name!r}

        if __name__ == '__main__':
            print('KSCONF_VERSION="{version}"\\nKSCONF_BUILD="{build_no}"\\nKSCONF_VCS_INFO="{vc_info}"')
        """)
    open(ver_file, "w").write(code_block)
    return version


DESCRIPTION = f"""\
# Ksconf Splunk CONFiguration tool

This utility handles common Splunk app maintenance tasks in an installable python package.
Specifically, this tool deals with many of the nuances of storing Splunk apps in a
version control system like git and pointing live Splunk apps to a working tree. Merging changes
from the live system's (local) folder to the version controlled (default) folder and dealing with
more than one layer of "default" are all supported tasks which are not native to Splunk.
Tasks like creating new Splunk apps from your local system while merging the 'local' folder into
'default' is also supported.

{package_rename_message}

Install with

    pip install {package_name}

Confirm installation with the following command:

    ksconf --version

To get an overview of all the CLI commands, run:

    ksconf --help

Help on specific command, such as 'unarchive', run:

    ksconf unarchive --help


Please see the [Official docs](https://ksconf.readthedocs.io/en/latest/) for more info.

"""


setup(name=package_name,
      version=get_ver(),
      description="KSCONF: Ksconf Splunk Configuration Tool",
      long_description=DESCRIPTION,
      long_description_content_type="text/markdown",
      classifiers=[
          "Development Status :: 4 - Beta",
          "Environment :: Console",
          "Intended Audience :: System Administrators",
          "License :: OSI Approved :: Apache Software License",
          "Natural Language :: English",
          "Operating System :: MacOS :: MacOS X",
          "Operating System :: Microsoft :: Windows",
          "Operating System :: POSIX :: Linux",
          "Programming Language :: Python :: 3",
          "Programming Language :: Python :: 3.7",
          "Programming Language :: Python :: 3.8",
          "Programming Language :: Python :: 3.9",
          "Programming Language :: Python :: 3.10",
          "Programming Language :: Python :: 3.11",
          "Topic :: Utilities",
      ],
      python_requires='>=3.7',
      license="Apache Software License",
      keywords='ksconf splunk kinytre conf tool',
      author="Lowell Alleman",
      author_email="lowell@kintyre.co",
      url="https://github.com/Kintyre/ksconf",
      project_urls={
          "Documentation": "https://ksconf.readthedocs.io/",
          "Splunk app": "https://splunkbase.splunk.com/app/4383/",
      },
      packages=[
          "ksconf",
          "ksconf.app",
          "ksconf.builder",
          "ksconf.commands",
          "ksconf.conf",
          "ksconf.util",
          "ksconf.vc",
          "ksconf.ext",    # Third-party modules shipping with ksconf
      ],
      setup_requires=[
          "wheel",
      ],
      install_requires=[
          "entrypoints",
          "pluggy",
          "lxml",         # Added as a hard requirement to allow pre-commit to work out of the box
      ],
      # Wacky reason for this explained in ksconf/setup_entrypoints.py
      entry_points=get_entrypoints_setup(),
      # Not required, but useful.
      extras_require={
          "bash": ["argcomplete"],
          "jinja": ["jinja2"],
          "thirdparty": [
              "splunk-sdk>=1.7.0"
          ],
      },
      include_package_data=True,
      zip_safe=True
      )
