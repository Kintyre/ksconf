# -*- coding: utf-8 -*-
"""
"""

from __future__ import absolute_import, annotations, unicode_literals

import os
import re
import sys
from os import fspath
from pathlib import Path
from typing import Callable

from ksconf.commands import ConfFileProxy
from ksconf.compat import List, Tuple
from ksconf.conf.delta import show_text_diff
from ksconf.conf.merge import merge_conf_files
from ksconf.conf.parser import PARSECONF_MID, PARSECONF_STRICT
from ksconf.consts import SMART_CREATE, SMART_NOCHANGE, SMART_UPDATE
from ksconf.layer import (DirectLayerRoot, DotDLayerRoot, LayerContext,
                          LayerFile, LayerFilter, LayerRootBase)
from ksconf.util.compare import file_compare
from ksconf.util.file import _is_binary_file, smart_copy


class LayerCombinerException(Exception):
    pass


class LayerCombiner:
    """
    Class to recursively combine layers (directories) into a single rendered output target directory.
    This is heavily used by the ``ksconf combine`` command as well as by the ``package`` command.


    Typical class use case:

    ::
        lc = LayerCombiner()

        # Setup source, either
            (1) lc.set_source_dirs()  OR
            (2) lc.set_layer_root()

    Call hierarch:

    ::

        lc.combine()                    Entry point
            -> prepare()                Directory, layer prep
                -> prepare_target_dir() Make dir; subclass handles marker here (combine CLI)
            -> pre_combine_inventory()  Hook for pre-processing (or alerting) the set of files to combine
            -> combine_files()          Main worker function
            -> post_combine()           Optional, cleanup leftover files
    """

    # Note this is case sensitive.  Don't be lazy, name your files correctly  :-)
    conf_file_re = re.compile(r"([a-z_-]+\.conf|(default|local)\.meta)$")
    spec_file_re = re.compile(r"\.conf\.spec$")

    filetype_handlers: List[Tuple[Callable, Callable]] = []

    def __init__(self,
                 follow_symlink: bool = False,
                 banner: str = "",
                 dry_run: bool = False,
                 quiet: bool = False):
        self.layer_root: LayerRootBase = None
        self.context = LayerContext()
        self.layer_filter = LayerFilter()
        self.banner = banner
        self.dry_run = dry_run
        self.quiet = quiet

        self.context.follow_symlink = follow_symlink

        # Internal tracking variables
        self.layer_names_all = set()
        self.layer_names_used = set()

        # Not a great long-term design, but good enough for initial conversion from command-based design
        self.stdout = sys.stdout
        self.stderr = sys.stderr

    @classmethod
    def register_handler(cls, regex_match):
        """ Decorator that registers a new file type handler.  The handler is
        used if a file name matches a regex.  Regex 'search' mode is used.
        """
        cre = re.compile(regex_match)

        def match_f(file: Path):
            if cre.search(file.name):
                return True
            return False

        def wrapper(handle_f):
            cls.filetype_handlers.append((match_f, handle_f))
            return handle_f

        return wrapper

    def log(self, message):
        # For historic reasons (idk) we send all messages to stderr, and diffs to stdout
        if message:
            self.stderr.write(f"{message}\n")

    def debug(self, message):
        if not self.quiet:
            self.log(message)

    def set_source_dirs(self, sources: List[Path]):
        self.layer_root = DirectLayerRoot(context=self.context)
        for src in sources:
            self.layer_root.add_layer(Path(src))

    def set_layer_root(self, root: LayerRootBase.Layer):
        layer_root = DotDLayerRoot(context=self.context)
        layer_root.set_root(root)
        self.layer_root = layer_root

    def add_layer_filter(self, action, pattern):
        self.layer_filter.add_rule(action, pattern)

    def combine(self, target):
        """
        Combine layers into ``target`` directory.
        """
        layer_root = self.layer_root
        if layer_root is None:
            raise TypeError("Call either set_source_dirs() or set_layer_root() before calling combine()")
        self.prepare(target)
        # Build a common tree of all src files.
        src_file_listing = layer_root.list_files()
        src_file_listing = self.pre_combine_inventory(target, src_file_listing)
        self.combine_files(target, src_file_listing)
        self.post_combine(target)

    def prepare(self, target: Path):
        """ Start the combine process.  This includes directory checking,
        applying layer filtering, and marker file handling. """
        layer_root, layer_filter = self.layer_root, self.layer_filter
        target = Path(target)

        self.prepare_target_dir(target)

        self.layer_names_all.update(layer_root.list_layer_names())
        if layer_root.apply_filter(layer_filter):
            self.layer_names_used.update(layer_root.list_layer_names())
        else:
            self.layer_names_used.update(self.layer_names_all)

    def prepare_target_dir(self, target: Path):
        """ Hook to ensure destination directory is ready for use.  This can be overridden
        to adder marker file handling for use cases that need it (e.g., the 'combine' command)
        """
        if not target.is_dir():
            target.mkdir()

    def pre_combine_inventory(self, target: Path, src_files: List[LayerFile]) -> List[LayerFile]:
        """ Hook point for pre-processing before any files are copied/merged """
        del target
        return src_files

    def post_combine(self, target):
        """ Hook point for post-processing after all copy/merge operations have been completed. """
        del target

    def combine_files(self, target: Path, src_files: List[LayerFile]):
        layer_root = self.layer_root
        for src_file in sorted(src_files):
            do_copy = True
            sources = list(layer_root.get_file(src_file))
            try:
                dest_fn = sources[0].logical_path
            except IndexError:
                raise LayerCombinerException(f"File disappeared during execution?  {src_file}\n")

            dest_path: Path = target / dest_fn

            # Make missing destination folder, if missing
            dest_dir: Path = dest_path.parent
            if not dest_dir.is_dir() and not self.dry_run:
                dest_dir.mkdir(parents=True)

            # Determine handling method based on source count and filename pattern
            if len(sources) > 1:
                for matcher, handler in self.filetype_handlers:
                    if matcher(dest_fn):
                        handler(self, dest_path, sources, self.dry_run)
                        do_copy = False

            if do_copy:
                # self.debug((f"Considering {fspath(dest_fn):50}  NON-CONF Copy from source:  "
                #             f"{sources[-1].physical_path!r}")
                # Always use the last file in the list (since last directory always wins)
                src_file = sources[-1].resource_path
                if self.dry_run:
                    if dest_path.is_file():
                        if file_compare(src_file, dest_path):
                            smart_rc = SMART_NOCHANGE
                        else:
                            if (_is_binary_file(src_file) or _is_binary_file(dest_path)):
                                # Binary files.  Can't compare...
                                smart_rc = "DRY-RUN (NO-DIFF=BIN)"
                            else:
                                show_text_diff(self.stdout, dest_path, src_file)
                                smart_rc = "DRY-RUN (DIFF)"
                    else:
                        smart_rc = "DRY-RUN (NEW)"
                else:
                    smart_rc = smart_copy(src_file, dest_path)
                if smart_rc != SMART_NOCHANGE:
                    self.debug(f"Copy <{smart_rc}>   {fspath(dest_path):50}  from {src_file}")
                del src_file


# registration decorator
register_handler = LayerCombiner.register_handler


#
# Combine handlers for specific file types
#

@register_handler(r"([a-z_-]+\.conf|(default|local)\.meta)$")
def handle_merge_conf_files(combiner: LayerCombiner,
                            dest_path: Path,
                            sources: List[LayerFile],
                            dry_run):
    """
    Handle merging two or more ``.conf`` files.
    """
    sources_physical = [fspath(p.physical_path) for p in sources]
    # Note that latest mtime logic is handled by merge_conf_files()
    srcs = []
    try:
        # Handle merging conf files
        dest = ConfFileProxy(dest_path, "r+", parse_profile=PARSECONF_MID)
        srcs = [ConfFileProxy(s.resource_path, "r", parse_profile=PARSECONF_STRICT) for s in sources]
        # combiner.debug(f"Considering {dest_fn:50}  CONF MERGE from source:  "
        #                f"{1!sources[0].physical_path}")
        smart_rc = merge_conf_files(dest, srcs, dry_run=dry_run,
                                    banner_comment=combiner.banner)
        if smart_rc != SMART_NOCHANGE:
            combiner.debug(f"Merge <{smart_rc}>   {fspath(dest_path):50}  from {sources_physical!r}")
        return smart_rc
    finally:
        # Protect against any dangling open files:  (ResourceWarning: unclosed file)
        dest.close()
        for src in srcs:
            src.close()


@register_handler(r"\.conf\.spec$")
def handle_spec_concatenate(combiner: LayerCombiner,
                            dest_path: Path,
                            sources: List[LayerFile],
                            dry_run):
    """
    Concatenate multiple ``.spec`` files.  Likely a ``README.d`` situation.
    """
    sources_physical = []
    combined_content = ""
    last_mtime = max(src.mtime for src in sources)
    for src in sources:
        sources_physical.append(src.physical_path)
        content = src.resource_path.read_text()
        if not content.endswith("\n"):
            content += "\n"
        combined_content += content
    smart_rc = SMART_CREATE
    if dest_path.is_file():
        dest_content = dest_path.read_text()
        if dest_content == combined_content:
            smart_rc = SMART_NOCHANGE
        else:
            smart_rc = SMART_UPDATE

    if not dry_run:
        dest_path.write_text(combined_content)

    os.utime(dest_path, (last_mtime, last_mtime))
    if smart_rc != SMART_NOCHANGE:
        combiner.debug(f"Concatenate <{smart_rc}>   {fspath(dest_path):50}  from {sources_physical!r}")
    return smart_rc
