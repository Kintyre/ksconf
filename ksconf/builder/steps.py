""" ksconf.builder.steps:  Collection of reusable build steps for reuse in your build script.
"""

import re
import sys
from shutil import copy2, rmtree
from typing import List

from ksconf.builder import QUIET, VERBOSE, BuildStep


def clean_build(step: BuildStep) -> None:
    """ Ensure a clean build folder for consistent build results."""
    log = step.get_logger()
    if step.build_path.is_dir():
        log("Purging previous build folder")
        rmtree(step.build_path)
    else:
        log("Make build folder")
    step.build_path.mkdir()

    if not step.dist_path.is_dir():
        log("Made dist dir")
        step.dist_path.mkdir()


def copy_files(step: BuildStep,
               patterns: List[str],
               target: str = None) -> None:
    """ Copy source files into the build folder that match given glob patterns """
    log = step.get_logger()
    if target:
        log(f"Copying files into build folder under {target}")
    else:
        log("Copying files into build folder")
    log(f"Copy src={step.source_path} to build={step.build_path} target={target}", VERBOSE * 2)
    dirs = files = 0
    for pattern in patterns:
        if pattern.endswith("/"):
            log(f"Looking for all files under '{pattern}'", VERBOSE * 3)
            pattern += "**/*"
        elif "*" in pattern:
            log(f"Looking for all files matching '{pattern}'", VERBOSE * 3)
        else:
            log(f"Looking for files named '{pattern}'", VERBOSE * 3)
        file_per_pattern = 0
        for f in step.source_path.glob(pattern):
            relative = f.relative_to(step.source_path)
            if target:
                dest = step.build_path / target / relative
            else:
                dest = step.build_path / relative

            dest_parent = dest.parent
            if not dest_parent.is_dir():
                log(f"Mkdir {dest_parent}", VERBOSE)
                dest_parent.mkdir(parents=True)
                dirs += 1
            if f.is_file():
                log(f"Copy  {f}", VERBOSE)
                copy2(f, dest)
                files += 1
                file_per_pattern += 1
        log(f"Copied {file_per_pattern} files matching '{pattern}'", VERBOSE * 2)
    # TODO: Expand capabilities to capture files/dirs per pattern, helpful to get lookup counts
    log(f"Completed copying {len(patterns)} patterns.  Created {files} files in {dirs} directories")


def _get_python_info_rename(path: str) -> str:
    """ Figure out the name of the package, without the version for renaming the directory.
    Why do all this?  Well, (1) it's tricky to figure the boundary between package name and version
    for some packages, and this approach removes the guesswork, (2) sometimes you want to distribute
    this metadata about the upstream packages bundled with a Splunk app, but you don't want to leave
    a mess behind after app upgrades.  Or, sometime packages need access to entrypoints stored
    within these folders.   But whenever possible, just delete 'em.
    """
    if path.name.endswith(".egg-info"):
        f = "PKG-INFO"
    else:
        # Assume dist-info.  Are there other options?
        f = "METADATA"
    pkgmetainfodata = path / f
    with pkgmetainfodata.open() as f:
        for line in f:
            match = re.match(r'^Name: ([A-Z-a-z].+)', line)
            if match:
                name = match.group(1)
                break
            if not line.strip():
                # First blank line; gone too far; give up
                return
        else:
            return
        return name + path.suffix


def pip_install(step: BuildStep,
                requirements_file: str = "requirements.txt",
                dest: str = "lib",
                python_path: str = None,
                isolated: bool = True,
                dependencies: bool = True,
                handle_dist_info: str = "remove",  # or 'rename'
                remove_console_scripts: bool = True
                ) -> None:
    dist_info_options = ("remove", "rename", "keep")
    if handle_dist_info not in dist_info_options:
        raise ValueError(f"Expecting 'handle_dist_info' to be one of {dist_info_options}")

    log = step.get_logger()
    if python_path is None:
        python_path = sys.executable
    target = step.build_path / dest

    extra_args = []

    if isolated:
        extra_args.append("--isolated")
    if not dependencies:
        extra_args.append("--no-deps")

    step.run(python_path, "-m", "pip",          # '-m pip' is reliable; avoids pip/pip2/pip3
             "install",                         # Install mode (no upgrade needed; fresh install)
             "-r", requirements_file,           # File to read packages from
             "--target", target,                # Targeted (directory) mode
             "--disable-pip-version-check",     # Warnings aren't helpful here
             "--no-compile",                    # Avoid creating *.pyc files
             *extra_args)

    log("pip installation completed successfully", QUIET)

    #  With the "--no-compile" options, this shouldn't be needed.  Keeping for now.
    for unwanted in target.rglob("*.py[co]"):
        log(f"Remove unwanted {unwanted}", VERBOSE * 2)
        unwanted.unlink()

    # Remove any console-script entry points files (bin|Script); depends on package
    if remove_console_scripts:
        for folder in ("bin", "Scripts"):
            path = target / folder
            if path.is_dir():
                log(f"Removing console-script folder: {path}")
                rmtree(path)

    if handle_dist_info == "keep":
        return

    log(f"Handling {{dist,egg}}-info folders:  mode={handle_dist_info} folder={target}", VERBOSE)
    di_handled = 0
    for path in target.iterdir():
        if path.is_dir() and path.suffix in (".dist-info", ".egg-info"):
            if handle_dist_info == "remove":
                log(f"Remove unwanted dist-info folder: {path.name}", VERBOSE * 2)
                rmtree(path)
                di_handled += 1
            elif handle_dist_info == "rename":
                try:
                    new_name = _get_python_info_rename(path)

                    if new_name:
                        log(f"Replacing dist-info {path} with {new_name}", VERBOSE * 2)
                        path.rename(path.with_name(new_name))
                        di_handled += 1
                    else:
                        log("Dist-info rename failed.  Unable to determine package name for "
                            f"{path}", QUIET)
                except Exception as e:
                    log(f"Exception during Dist-info rename for {path}:  {e}", QUIET * 2)
    if di_handled:
        log(f"Dist info:  {handle_dist_info}d {di_handled} directories")
