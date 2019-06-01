#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import os
import re
from setuptools import setup
from textwrap import dedent

from ksconf.setup_entrypoints import get_entrypoints_setup


def get_ver():
    # Todo: There has to be a better library/method of doing this junk.
    from ksconf.vc.git import git_cmd
    ver_file = os.path.join("ksconf", "_version.py")
    #git_sha1 = git_cmd(["rev-parse", "HEAD"]).stdout[:12]
    vc_info = git_cmd(["show", "-s", "--abbrev=8", "--format=Git SHA1 %h committed on %cd",
                       "--date=format:%Y-%m-%d", "HEAD"]).stdout.strip()
    gitout = git_cmd(["describe", "--tags", "--always", "--dirty"])
    version = gitout.stdout.strip()
    version = version.lstrip("v")   # Tags format is v0.0.0
    # replace hash with local version format
    ### XXX:  Wow. this needs unittests.  smh
    version = re.sub(r'-(\d+)-g([a-f0-9]+)((?:-dirty)?)', r'.dev\1+\2\3', version)
    version = re.sub(r'(\d+\.\d+)-dirty$', r'\1.dev0+dirty', version)
    version = version.replace("-dirty",".dirty")
    print("Version:  {}".format(version))
    code_block = dedent("""\
        # Version file autogenerated by the build process
        version = {0!r}
        build = {1!r}
        vcs_info = {2!r}

        if __name__ == '__main__':
            print('KSCONF_VERSION="{0}"\\nKSCONF_BUILD="{1}"\\nKSCONF_VCS_INFO="{2}"')
        """).format(version, os.environ.get("TRAVIS_BUILD_NUMBER", None), vc_info)
    open(ver_file, "w").write(code_block)
    return version

DESCRIPTION = """\
# Kintyre's Splunk CONFiguration tool

This utility handles a number of common Splunk app maintenance tasks in an installable python
package.  Specifically, this tools deals with many of the nuances with storing Splunk apps in a
version control system like git and pointing live Splunk apps to a working tree, merging changes
from the live system's (local) folder to the version controlled (default) folder, and dealing with
more than one layer of "default" (which splunk can't handle natively).

Install with

    pip install kintyre-splunk-conf

Confirm installation with the following command:

    ksconf --help


Please see the [Official docs](https://ksconf.readthedocs.io/en/latest/) for more info.

"""


setup(name="kintyre-splunk-conf",
      version=get_ver(),
      description="KSCONF: Kintyre's Splunk Configuration Tool",
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
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Utilities",
      ],
      python_requires='>=2.7,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*',
      license="Apache Software License",
      keywords='ksconf splunk kinytre conf tool',
      author="Lowell Alleman",
      author_email="lowell@kintyre.co",
      url="https://github.com/Kintyre/ksconf",
      project_urls = {
        "Documentation" : "https://ksconf.readthedocs.io/",
        "Splunk app" : "https://splunkbase.splunk.com/app/4383/",
      },
      packages=[
          "ksconf",
          "ksconf.commands",
          "ksconf.conf",
          "ksconf.util",
          "ksconf.vc",
      ],
      setup_requires=[
          "wheel",
      ],
      install_requires=[
        "six",
        "entrypoints",
        "lxml",         # Added as a hard requirement to allow pre-commit to work out of the box
      ],
      # Wacky reason for this explained in ksconf/setup_entrypoints.py
      entry_points = get_entrypoints_setup(),
      # Not required, but useful.
      extras_require = {
        "bash" : [ "argcomplete" ],
        "thirdparty" : [
            "splunk-sdk"
        ],
      },
      include_package_data=True,
      zip_safe=True
)
