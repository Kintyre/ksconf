import os
import re
import sys
from collections import defaultdict

from ksconf.commands import ConfFileProxy
from ksconf.conf.delta import show_text_diff
from ksconf.conf.merge import merge_conf_files
from ksconf.conf.parser import PARSECONF_MID, PARSECONF_STRICT
from ksconf.consts import EXIT_CODE_MISSING_ARG, EXIT_CODE_COMBINE_MARKER_MISSING, SMART_NOCHANGE
from ksconf.util.compare import file_compare
from ksconf.util.file import _expand_glob_list, relwalk, _is_binary_file, smart_copy

CONTROLLED_DIR_MARKER = ".ksconf_controlled"


def do_combine(args):
    # Ignores case sensitivity.  If you're on Windows, name your files right.
    conf_file_re = re.compile("([a-z]+\.conf|(default|local)\.meta)$")

    if args.target is None:
        sys.stderr.write("Must provide the '--target' directory.\n")
        return EXIT_CODE_MISSING_ARG

    sys.stderr.write("Combining conf files into {}\n".format(args.target))
    args.source = list(_expand_glob_list(args.source))
    for src in args.source:
        sys.stderr.write("Reading conf files from {}\n".format(src))

    marker_file = os.path.join(args.target, CONTROLLED_DIR_MARKER)
    if os.path.isdir(args.target):
        if not os.path.isfile(os.path.join(args.target, CONTROLLED_DIR_MARKER)):
            sys.stderr.write("Target directory already exists, but it appears to have been created "
                             "by some other means.  Marker file missing.\n")
            return EXIT_CODE_COMBINE_MARKER_MISSING
    elif args.dry_run:
        sys.stderr.write("Skipping creating destination folder {0} (dry-run)\n".format(args.target))
    else:
        sys.stderr.write("Creating destination folder {0}\n".format(args.target))
        os.mkdir(args.target)
        open(marker_file, "w").write("This directory is managed by KSCONF.  Don't touch\n")

    # Build a common tree of all src files.
    src_file_index = defaultdict(list)
    for src_root in args.source:
        for (root, dirs, files) in relwalk(src_root):
            for fn in files:
                # Todo: Add blacklist CLI support:  defaults to consider: *sw[po], .git*, .bak, .~
                if fn.endswith(".swp") or fn.endswith("*.bak"):
                    continue  # pragma: no cover  (peephole optimization)
                src_file = os.path.join(root, fn)
                src_path = os.path.join(src_root, root, fn)
                src_file_index[src_file].append(src_path)

    # Find a set of files that exist in the target folder, but in NO source folder (for cleanup)
    target_extra_files = set()
    for (root, dirs, files) in relwalk(args.target):
        for fn in files:
            tgt_file = os.path.join(root, fn)
            if tgt_file not in src_file_index:
                # Todo:  Add support for additional blacklist wildcards (using fnmatch)
                if fn == CONTROLLED_DIR_MARKER or fn.endswith(".bak"):
                    continue  # pragma: no cover (peephole optimization)
                target_extra_files.add(tgt_file)

    for (dest_fn, src_files) in sorted(src_file_index.items()):
        dest_path = os.path.join(args.target, dest_fn)

        # Make missing destination folder, if missing
        dest_dir = os.path.dirname(dest_path)
        if not os.path.isdir(dest_dir) and not args.dry_run:
            os.makedirs(dest_dir)

        # Handle conf files and non-conf files separately
        if not conf_file_re.search(dest_fn):
            # sys.stderr.write("Considering {0:50}  NON-CONF Copy from source:  {1!r}\n".format(dest_fn, src_files[-1]))
            # Always use the last file in the list (since last directory always wins)
            src_file = src_files[-1]
            if args.dry_run:
                if os.path.isfile(dest_path):
                    if file_compare(src_file, dest_path):
                        smart_rc = SMART_NOCHANGE
                    else:
                        if (_is_binary_file(src_file) or _is_binary_file(dest_path)):
                            # Binary files.  Can't compare...
                            smart_rc = "DRY-RUN (NO-DIFF=BIN)"
                        else:
                            show_text_diff(sys.stdout, dest_path, src_file)
                            smart_rc = "DRY-RUN (DIFF)"
                else:
                    smart_rc = "DRY-RUN (NEW)"
            else:
                smart_rc = smart_copy(src_file, dest_path)
            if smart_rc != SMART_NOCHANGE:
                sys.stderr.write(
                    "Copy <{0}>   {1:50}  from {2}\n".format(smart_rc, dest_path, src_file))
        else:
            # Handle merging conf files
            dest = ConfFileProxy(os.path.join(args.target, dest_fn), "r+",
                                 parse_profile=PARSECONF_MID)
            srcs = [ConfFileProxy(sf, "r", parse_profile=PARSECONF_STRICT) for sf in src_files]
            # sys.stderr.write("Considering {0:50}  CONF MERGE from source:  {1!r}\n".format(dest_fn, src_files[0]))
            smart_rc = merge_conf_files(dest, srcs, dry_run=args.dry_run,
                                        banner_comment=args.banner)
            if smart_rc != SMART_NOCHANGE:
                sys.stderr.write("Merge <{0}>   {1:50}  from {2!r}\n".format(smart_rc, dest_path,
                                                                             src_files))

    if True and target_extra_files:  # Todo: Allow for cleanup to be disabled via CLI
        sys.stderr.write("Cleaning up extra files not part of source tree(s):  {0} files.\n".format(
            len(target_extra_files)))
        for dest_fn in target_extra_files:
            sys.stderr.write("Remove unwanted file {0}\n".format(dest_fn))
            os.unlink(os.path.join(args.target, dest_fn))
