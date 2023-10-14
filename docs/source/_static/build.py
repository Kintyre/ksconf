#!/usr/bin/env python
#
# KSCONF Official example app building script
#
from pathlib import Path

from ksconf.builder import QUIET, VERBOSE, BuildManager, BuildStep, default_cli
from ksconf.builder.steps import clean_build, copy_files, pip_install

manager = BuildManager()

APP_FOLDER = "TA-my_technology"
SPL_NAME = "ta_my_technology-{{version}}.tgz"
SOURCE_DIR = "."

REQUIREMENTS = "requirements.txt"

# Files that support the build process, but don't end up in the tarball.
BUILD_FILES = [
    REQUIREMENTS,
]

COPY_FILES = [
    "README.md",
    "bin/*.py",
    "default/",
    "metadata/*.meta",
    "static/",
    "lookups/*.csv",
    "appserver/",
    "README/*.spec",
] + BUILD_FILES


@manager.cache([REQUIREMENTS], ["lib/"], timeout=7200)
def python_packages(step):
    # Reuse shared function from ksconf.build.steps
    pip_install(step, REQUIREMENTS, "lib",
                handle_dist_info="remove")


def package_spl(step: BuildStep):
    log = step.get_logger()
    top_dir = step.dist_path.parent
    release_path = top_dir / ".release_path"
    release_name = top_dir / ".release_name"
    # Verbose message
    log("Starting to package SPL file!", VERBOSE)
    step.run_ksconf("package",
                    "--file", step.dist_path / SPL_NAME,   # Path to created tarball
                    "--app-name", APP_FOLDER,              # Top-level directory name
                    "--block-local",                       # VC build, no 'local' folder
                    "--release-file", str(release_path),
                    ".")
    # Provide the dist file as a short name too (used by some CI/CD tools)
    path = release_path.read_text()
    short_name = Path(path).name
    release_name.write_text(short_name)
    # Output message will be produced even in QUIET mode
    log(f"Created SPL file:  {short_name}", QUIET)


def build(step: BuildStep, args):
    """ Build process """
    # Step 1:  Clean/create build folder
    clean_build(step)

    # Step 2:  Copy files from source to build folder
    copy_files(step, COPY_FILES)

    # Step 3:  Install Python package dependencies
    python_packages(step)

    # Step 4:  Make tarball
    package_spl(step)


if __name__ == '__main__':
    # Tell build manager where stuff lives
    manager.set_folders(SOURCE_DIR, "build", "dist")

    # Launch build CLI
    default_cli(manager, build)
