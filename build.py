# Example app building script

import sys
from shutil import copy2, rmtree
import argparse

from ksconf.util.builder import BuildManager, VERBOSE, QUIET

manager = BuildManager()

def copy_files(step):
    # args: (BuildStep)
    log = step.get_logger()
    if step.build_path.is_dir():
        log("Purging previous build folder")
        rmtree(str(step.build_path))
    else:
        log("Make build folder")
    step.build_path.mkdir()

    log("Copying files into build folder")
    for pattern in [
        "requirements.txt",
        "ksconf/**",
        "tests/*.py",
    ]:
        for f in step.source_path.glob(pattern):
            log("Copy {}".format(f), VERBOSE)
            relative = f.relative_to(step.source_path)
            dest = step.build_path / relative

            dest_parent = dest.parent
            if not dest_parent.is_dir():
                dest_parent.mkdir(parents=True)
            if f.is_file():
                copy2(str(f), str(dest))

@manager.cache(["requirements.txt"], ["lib/"], timeout=86400,
               cache_invalidation=[list(sys.version_info)])
def pip_install(step):
    log = step.get_logger()
    # --isolated --disable-pip-version-check --no-deps --target="$PIP_TARGET" \
    # "$wheel_dir"/*.whl entrypoints splunk-sdk

    target = step.build_path / "lib"

    step.run(sys.executable, "-m", "pip", "install",
             "--target", str(target),
             "--disable-pip-version-check",    # Warnings are helpful here
             "--no-compile",   # Avoid creating *.pyc files
             "-r", "requirements.txt")

    log("pip installation completed successfully", QUIET)

    #  With the "--no-compile" options, this shouldn't be needed.  Keeping for now.
    for unwanted in target.rglob("*.py[co]"):
        log("Remove unwanted {}".format(unwanted), VERBOSE * 2)
        unwanted.unlink()

    # Remove any console-script entry points files (bin|Script)

    for folder in ("bin", "Scripts"):
        path = target / folder
        if path.is_dir():
            log("Removing console-script folder: {}".format(path))
            rmtree(str(path))

def build():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action="count", default=0)
    parser.add_argument("--quiet", "-q", action="count", default=0)
    parser.add_argument("--build", metavar="DIR", default="build",
                        help="Set build folder destination")
    parser.add_argument("--no-cache", action="store_true", default=False,
                        help="Disable caching")
    parser.add_argument("--taint-cache",
                        action="store_true", default=False)

    args = parser.parse_args()

    verbosity = args.verbose - args.quiet
    manager.set_folders(".", args.build)
    if args.no_cache:
        manager.disable_cache()
    if args.taint_cache:
        manager.taint_cache()
    step = manager.get_build_step()
    step.verbosity = verbosity

    # 1. Copy files from source to build
    copy_files(step)

    # 2. PIP install
    pip_install(step)


if __name__ == '__main__':
    build()
