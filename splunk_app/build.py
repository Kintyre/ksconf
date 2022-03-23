#!/usr/bin/env python

import os
import re
import shutil
import sys
from pathlib import Path, PurePath

APP_DIR = Path(__file__).absolute().parent
GIT_ROOT = APP_DIR.parent

# Run script from directory where this file lives
os.chdir(APP_DIR)
# sys.path.insert(0, str(GIT_ROOT))  # noqa

# These safety checks are most likely to go wrong in my local dev, but just in case...
try:
    import wheel
    del wheel
except ImportError:
    print("Missing required 'wheel' package.  Please run:\n\n\t"
          "python -m pip install --upgrade pip setuptools wheel")
    sys.exit(1)

try:
    import ksconf.builder
    del ksconf.builder
except ImportError:
    print("You must have ksconf installed to run this script\n"
          "Run this first:\n\n\t"
          "python -m pip install .")
    sys.exit(2)

from ksconf.builder.steps import clean_build, copy_files, pip_install  # noqa
from ksconf.builder import QUIET, VERBOSE, BuildManager, BuildStep, default_cli  # noqa


manager = BuildManager()

APP_FOLDER = PurePath("ksconf")
SPL_NAME = "ksconf-app_for_splunk-{{version}}.tgz"


def make_wheel(step):
    log = step.get_logger()
    step.run(sys.executable, "setup.py", "bdist_wheel",
             "-d", str(step.dist_path),
             cwd=GIT_ROOT)
    wheel = next(step.dist_path.glob("*.whl"))
    log("Wheel:  {}".format(wheel), VERBOSE)
    return wheel


def make_docs(step):
    log = step.get_logger()
    log("Making html docs via Sphinx")
    docs_dir = GIT_ROOT / "docs"
    static_docs = APP_FOLDER / "appserver/static/docs"
    docs_build = step.build_path / static_docs
    # Use the classic theme (~ 1Mb output vs 11+ mb, due to web fonts)
    os.environ["KSCONF_DOCS_THEME"] = "classic"
    step.run("make", "html", cwd=docs_dir)
    log("Copying docs to {}".format(static_docs))
    shutil.copytree(str(docs_dir / "build/html"),
                    str(docs_build))


def filter_requirements(step: BuildStep, src: str, re_block: str, extra: str):
    """ Copy a filtered version of requirements.txt """
    log = step.get_logger()
    dest = step.build_path / src.name
    log("Filtering requirements.txt:  {} --> {}".format(src, dest, re_block), VERBOSE)
    log("Filtering requirements.txt: filter={}".format(re_block))
    with open(src) as f_src, open(dest, "w") as f_dest:
        for line in f_src:
            line = line.strip()
            if re.search(re_block, line):
                log("Block entry: {}".format(line), VERBOSE)
                continue
            if not line or line.startswith("#"):
                continue
            #  Remove any version specific specifiers
            line = line.split(";", 1)[0]
            log("Keep entry: {}".format(line), VERBOSE * 2)
            f_dest.write(line + "\n")
        log("Adding extra package: {}".format(extra), VERBOSE)
        f_dest.write("{}\n".format(extra))


# XXX: this breaks when cache is enabled.  Figured this out, some path handling is busted
# @manager.cache(["requirements.txt"], ["bin/lib/"], timeout=7200)
def python_packages(step):
    # Reuse shared function from ksconf.build.steps
    pip_install(step, "requirements.txt", APP_FOLDER / "bin/lib",
                handle_dist_info="rename",
                dependencies=False)  # managing dependencies manually


def package_spl(step):
    top_dir = step.dist_path.parent
    release_path = top_dir / ".release_path"
    release_name = top_dir / ".release_name"
    build_no = 0
    if "GITHUB_RUN_NUMBER" in os.environ:
        build_no = 1000 + int(os.environ["GITHUB_RUN_NUMBER"])
    step.run(sys.executable, "-m", "ksconf", "package",
             "--file", step.dist_path / SPL_NAME,
             "--set-version", "{{git_tag}}",
             "--set-build", build_no,
             "--blocklist", ".buildinfo",  # From build docs
             "--blocklist", "requirements.txt",
             "--block-local",
             "--layer-method=disable",
             "--release-file", str(release_path),
             APP_FOLDER)
    # Provide the dist file as a short name too (used by some CI/CD tools)
    path = release_path.read_text()
    short_name = Path(path).name
    release_name.write_text(short_name)


def build(step, args):
    """ Build process """

    # Cleanup build folder
    clean_build(step)

    # build ksconf as a wheel
    ksconf_wheel = make_wheel(step)

    # Copy splunk app template bits into build folder
    copy_files(step, ["{}/".format(APP_FOLDER)])

    # Re-write normal requirements file: Remove some, install all PY2 backports
    filter_requirements(step, GIT_ROOT / "requirements.txt",
                        r"^(lxml|mock)",    # Skip these packages
                        ksconf_wheel)       # Install ksconf (from wheel)

    # Install Python package dependencies
    python_packages(step)

    # Use Sphinx to build a copy of all the HTML docs (for app inclusion)
    make_docs(step)

    # Make tarball
    package_spl(step)


if __name__ == '__main__':
    # Tell build manager where stuff lives
    manager.set_folders(source_path=".",
                        build_path="build",
                        dist_path=GIT_ROOT / "zdist")

    # Launch build CLI
    default_cli(manager, build)
