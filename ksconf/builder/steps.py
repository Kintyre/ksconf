""" ksconf.builder.steps:  Collection of reusable build steps for reuse in your build script.
"""
from __future__ import absolute_import, unicode_literals

import re
import sys
from shutil import copy2, rmtree

from ksconf.builder import QUIET, VERBOSE, BuildStep

if sys.version_info < (3, 6):
    # Allow these stdlib functions to work with pathlib
    from ksconf.util.file import pathlib_compat
    copy2 = pathlib_compat(copy2)
    rmtree = pathlib_compat(rmtree)
    del pathlib_compat


def clean_build(step):
    """ Ensure a clean build folder for consistent build results."""
    # args: (BuildStep)
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


def copy_files(step, patterns, target=None):
    """ Copy source files into the build folder that match given glob patterns """
    # args: (BuildStep, list(str), str)
    log = step.get_logger()
    if target:
        log("Copying files into build folder under {}".format(target))
    else:
        log("Copying files into build folder")
    log("Copy src={} to build={} target={}".format(step.source_path, step.build_path, target), VERBOSE * 2)
    dirs = files = 0
    for pattern in patterns:
        if pattern.endswith("/"):
            log("Looking for all files under '{}'".format(pattern), VERBOSE * 3)
            pattern += "**/*"
        elif "*" in pattern:
            log("Looking for all files matching '{}'".format(pattern), VERBOSE * 3)
        else:
            log("Looking for files named '{}'".format(pattern), VERBOSE * 3)
        file_per_pattern = 0
        for f in step.source_path.glob(pattern):
            relative = f.relative_to(step.source_path)
            if target:
                dest = step.build_path / target / relative
            else:
                dest = step.build_path / relative

            dest_parent = dest.parent
            if not dest_parent.is_dir():
                log("Mkdir {}".format(dest_parent), VERBOSE)
                dest_parent.mkdir(parents=True)
                dirs += 1
            if f.is_file():
                log("Copy  {}".format(f), VERBOSE)
                copy2(f, dest)
                files += 1
                file_per_pattern += 1
        log("Copied {} files matching '{}'".format(file_per_pattern, pattern), VERBOSE * 2)
    # TODO: Expand capabilities to capture files/dirs per pattern, helpful to get lookup counts
    log("Completed copying {} patterns.  Created {} files in {} directories".format(
        len(patterns), files, dirs))


def _get_python_info_rename(path):
    """ Figure out the name of the package, without the version for renaming the directory.
    Why do all this?  Well, (1) it's tricky to figure the boundary between package name and version
    for some packages, and this approach removes the guesswork, (2) sometimes you want to distribute
    this metadata about the upstream packages bundled with a Splunk app, but you don't want to leave
    a mess behind after app upgrades.  Or, sometime packages need access to entrypoints stored
    within these folders.   But whenever possible, just delete 'em.
    """
    # args: (str) -> str
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


def pip_install(step, requirements_file="requirements.txt", dest="lib",
                python_path=None, isolated=True, dependencies=True,
                handle_dist_info="remove",  # or 'rename'
                remove_console_scripts=True):
    # args: (BuildStep, str, str, str, bool, bool, str, bool) -> None
    dist_info_options = ("remove", "rename", "keep")
    if handle_dist_info not in dist_info_options:
        raise ValueError("Expecting 'handle_dist_info' to be one of {}".format(dist_info_options))

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
        log("Remove unwanted {}".format(unwanted), VERBOSE * 2)
        unwanted.unlink()

    # Remove any console-script entry points files (bin|Script); depends on package
    if remove_console_scripts:
        for folder in ("bin", "Scripts"):
            path = target / folder
            if path.is_dir():
                log("Removing console-script folder: {}".format(path))
                rmtree(path)

    if handle_dist_info == "keep":
        return

    log("Handling {{dist,egg}}-info folders:  mode={} folder={}".format(handle_dist_info, target), VERBOSE)
    di_handled = 0
    for path in target.iterdir():
        if path.is_dir() and path.suffix in (".dist-info", ".egg-info"):
            if handle_dist_info == "remove":
                log("Remove unwanted dist-info folder: {}".format(path.name), VERBOSE * 2)
                rmtree(path)
                di_handled += 1
            elif handle_dist_info == "rename":
                try:
                    new_name = _get_python_info_rename(path)

                    if new_name:
                        log("Replacing dist-info {} with {}".format(path, new_name), VERBOSE * 2)
                        path.rename(path.with_name(new_name))
                        di_handled += 1
                    else:
                        log("Dist-info rename failed.  Unable to determine package name for "
                            "{}".format(path), QUIET)
                except Exception as e:
                    log("Exception during Dist-info rename for {}:  {}".format(path, e), QUIET * 2)
    if di_handled:
        log("Dist info:  {}d {} directories".format(handle_dist_info, di_handled))


# We use this for typing, but otherwise don't directly reference.  Keep this line to avoid automatic import removal
_ = BuildStep
