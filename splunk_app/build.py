#!/usr/bin/env python

import os
import re
import sys
from pathlib import Path

GIT_ROOT = Path(__file__).absolute().parent.parent
sys.path.insert(0, str(GIT_ROOT))  # noqa

from ksconf.builder.steps import clean_build, copy_files, pip_install  # noqa
from ksconf.builder import QUIET, VERBOSE, BuildManager, BuildStep, default_cli  # noqa

manager = BuildManager()

SPL_NAME = "ksconf-{{version}}.tgz"
SOURCE_DIR = "ksconf"


def make_wheel(step):
    log = step.get_logger()
    step.run(sys.executable, "setup.py", "bdist_wheel",
             "-d", str(step.dist_path),
             cwd=GIT_ROOT)
    wheel = next(step.dist_path.glob("*.whl"))
    log("Wheel:  {}".format(wheel), VERBOSE)
    return wheel
    # os.rename(wheel, step.dist_path / "kintyre_splunk_conf.whl")


def filter_requirements(step, src, re_block, extra):
    """ Copy a filtered version of requirements.txt """
    # type: (Buildstep)
    log = step.get_logger()
    dest = step.source_path / src.name
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
            log("Keep entry: {}".format(line), VERBOSE * 2)
            f_dest.write(line + "\n")
        f_dest.write("{}\n".format(extra))


@manager.cache(["requirements.txt"], ["bin/lib/"], timeout=7200)
def python_packages(step):
    # Reuse shared function from ksconf.build.steps
    pip_install(step, "requirements.txt", "bin/lib",
                handle_dist_info="rename",
                dependencies=False,             # managing dependencies manually
                python_path="python2.7")


def package_spl(step):
    top_dir = step.dist_path.parent
    release_path = top_dir / ".release_path"
    release_name = top_dir / ".release_name"
    step.run(sys.executable, "-m", "ksconf", "package",
             "--file", step.dist_path / SPL_NAME,   # Path to created tarball
             "--set-version", "{{git_tag}}",
             "--set-build", os.environ.get("TRAVIS_BUILD_NUMBER", "0"),
             "--block-local",
             "--layer-method=disable",
             "--release-file", str(release_path),
             ".")
    # Provide the dist file as a short name too (used by some CI/CD tools)
    path = release_path.read_text()
    short_name = Path(path).name
    release_name.write_text(short_name)


def build(step, args):
    """ Build process """
    clean_build(step)
    ksconf_wheel = make_wheel(step)
    copy_files(step, ["**/*"])
    filter_requirements(step, GIT_ROOT / "requirements.txt", r"^(lxml|mock)", ksconf_wheel)

    # Install Python package dependencies
    python_packages(step)

    # Make tarball
    package_spl(step)


if __name__ == '__main__':
    # Tell build manager where stuff lives
    manager.set_folders(SOURCE_DIR, "build", GIT_ROOT / "zdist")

    # Launch build CLI
    default_cli(manager, build)
