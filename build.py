# Example app building script

import sys
from subprocess import call
from shutil import copy2, rmtree
import argparse

from ksconf.util.builder import BuildManager

manager = BuildManager()

def copy_files(step):
    # args: (BuildStep)
    if step.build_path.is_dir():
        step.log("Purging previous build folder")
        rmtree(str(step.build_path))
    else:
        step.log("Make build folder")
    step.build_path.mkdir()
    for pattern in [
        "requirements.txt",
        "ksconf/**",
        "tests/*.py",
    ]:
        for f in step.source_path.glob(pattern):
            step.log("Copy {}".format(f))
            relative = f.relative_to(step.source_path)
            dest = step.build_path / relative

            dest_parent = dest.parent
            if not dest_parent.is_dir():
                dest_parent.mkdir(parents=True)
            '''
            if f.is_dir():
                if not dest.is_dir():
                    dest.mkdir(parents=True)
            else:
            '''
            if f.is_file():
                copy2(str(f), str(dest))

@manager.cache(["requirements.txt"], ["lib/"], timeout=86400,
               cache_invalidation=[list(sys.version_info)])
def pip_install(step):

    # --isolated --disable-pip-version-check --no-deps --target="$PIP_TARGET" \
    # "$wheel_dir"/*.whl entrypoints splunk-sdk

    target = step.build_path / "lib"
    call([sys.executable, "-m", "pip", "install",
          "--target", str(target),
          "-r", "requirements.txt"])
    step.log("pip installation completed successfully", -1)


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
