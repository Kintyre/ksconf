"""

Design goals:

 * Multi-purpose go-to .conf tool.
 * Dependability
 * Simplicity
 * No eternal dependencies (single source file, if possible; or packable as single file.)
 * Stable CLI
 * Good scripting interface for deployment scripts and/or git hooks



-------------------------------------------------

Git configuration tweaks


Setup ksconf as an external difftool provider:

    ~/.gitconfig:

        [difftool "ksconf"]
            cmd = "ksconf --force-color diff \"$LOCAL\" \"$REMOTE\" | less -R"
        [difftool]
            prompt = false
        [alias]
            ksdiff = "difftool --tool=ksconf"

    Now can run:  git ksdiff props.conf
    Test command: git config diff.conf.xfuncname



Make normal diffs show the 'stanza' on the @@ output lines

    ~/.gitconfig

        [diff "conf"]
            xfuncname = "^(\\[.*\\])$"

    attributes:
        *.conf diff=conf
        *.meta diff=conf

    Test command:

    git check-attr -a -- *.conf

"""

import os
import shutil
import sys
from StringIO import StringIO
from collections import defaultdict, Counter
from copy import deepcopy
from subprocess import list2cmdline

from ksconf.archive import extract_archive, gaf_filter_name_like, sanity_checker, \
    gen_arch_file_remapper
from ksconf.vc.git import git_cmd, git_cmd_iterable, git_is_working_tree, git_is_clean, \
    git_ls_files, git_status_ui
from .conf.parser import GLOBAL_STANZA, \
    PARSECONF_STRICT, PARSECONF_STRICT_NC, PARSECONF_MID, PARSECONF_LOOSE, \
    ConfParserException, parse_conf, write_conf, \
    smart_write_conf, _drop_stanza_comments
from ksconf.conf.merge import merge_conf_dicts, merge_conf_files
from ksconf.conf.delta import DIFF_OP_INSERT, DIFF_OP_DELETE, DIFF_OP_REPLACE, DIFF_OP_EQUAL, \
    DiffStanza, compare_cfgs, summarize_cfg_diffs, show_diff, \
    show_text_diff
from ksconf.util.file import _is_binary_file, dir_exists, smart_copy, _stdin_iter, \
    file_fingerprint, _expand_glob_list, match_bwlist, relwalk, file_hash, _samefile
from ksconf.util.compare import file_compare, _cmp_sets


CONTROLLED_DIR_MARKER = ".ksconf_controlled"

from .consts import *


####################################################################################################
## CLI do_*() functions


def do_check(args):
    # Should we read a list of conf files from STDIN?
    if len(args.conf) == 1 and args.conf[0] == "-":
        confs = _stdin_iter()
    else:
        confs = args.conf
    c = Counter()
    exit_code = EXIT_CODE_SUCCESS
    for conf in confs:
        c["checked"] += 1
        if not os.path.isfile(conf):
            sys.stderr.write("Skipping missing file:  {0}\n".format(conf))
            c["missing"] += 1
            continue
        try:
            parse_conf(conf, profile=PARSECONF_STRICT_NC)
            c["okay"] += 1
            if not args.quiet:
                sys.stdout.write("Successfully parsed {0}\n".format(conf))
                sys.stdout.flush()
        except ConfParserException, e:
            sys.stderr.write("Error in file {0}:  {1}\n".format(conf, e))
            sys.stderr.flush()
            exit_code = EXIT_CODE_BAD_CONF_FILE
            # TODO:  Break out counts by error type/category (there's only a few of them)
            c["error"] += 1
        except Exception, e:        # pragma: no cover
            sys.stderr.write("Unhandled top-level exception while parsing {0}.  "
                             "Aborting.\n{1}\n".format(conf, e))
            exit_code = EXIT_CODE_INTERNAL_ERROR
            c["error"] += 1
            break
    if True:    #show stats or verbose
        sys.stdout.write("Completed checking {0[checked]} files.  rc={1} Breakdown:\n"
                         "   {0[okay]} files were parsed successfully.\n"
                         "   {0[error]} files failed.\n".format(c, exit_code))
    sys.exit(exit_code)




def do_merge(args):
    ''' Merge multiple configuration files into one '''
    merge_conf_files(args.target, args.conf, dry_run=args.dry_run, banner_comment=args.banner)
    return EXIT_CODE_SUCCESS


def do_diff(args):
    ''' Compare two configuration files. '''
    args.conf1.set_parser_option(keep_comments=args.comments)
    args.conf2.set_parser_option(keep_comments=args.comments)

    cfg1 = args.conf1.data
    cfg2 = args.conf2.data

    diffs = compare_cfgs(cfg1, cfg2)
    rc = show_diff(args.output, diffs, headers=(args.conf1.name, args.conf2.name))
    if rc == EXIT_CODE_DIFF_EQUAL:
        sys.stderr.write("Files are the same.\n")
    elif rc == EXIT_CODE_DIFF_NO_COMMON:
        sys.stderr.write("No common stanzas between files.\n")
    return rc


def explode_default_stanza(conf, default_stanza=None):
    """ Take the GLOBAL stanza, (aka [default]) and apply it's settings underneath ALL other
    stanzas.  This is mostly only useful in minimizing and other comparison operations. """
    if default_stanza is None:
        default_stanza = conf.get(GLOBAL_STANZA, conf.get("default"))
        if not default_stanza:
            return conf
    default_stanza = _drop_stanza_comments(default_stanza)
    n = {}
    for (stanza, content) in conf.iteritems():
        new_content = dict(default_stanza)
        new_content.update(content)
        n[stanza] = new_content
    return n


def do_minimize(args):
    if args.explode_default:
        # Is this the SAME as exploding the defaults AFTER the merge?;  I think NOT.  Needs testing
        cfgs = [ explode_default_stanza(conf.data) for conf in args.conf ]
    else:
        cfgs = [ conf.data for conf in args.conf ]
    # Merge all config files:
    default_cfg = merge_conf_dicts(*cfgs)
    del cfgs
    local_cfg = args.target.data
    orig_cfg = dict(args.target.data)

    if args.explode_default:
        # Make a skeleton default dict; at the highest level, that ensure that all default
        default_stanza = default_cfg.get(GLOBAL_STANZA, default_cfg.get("default"))
        skeleton_default = dict([ (k,{}) for k in args.target.data])
        skeleton_default = explode_default_stanza(skeleton_default, default_stanza)
        default_cfg = merge_conf_dicts(skeleton_default, default_cfg)

        local_cfg = explode_default_stanza(local_cfg)
        local_cfg = explode_default_stanza(local_cfg, default_stanza)

    minz_cfg = dict(local_cfg)

    # This may be a bit too simplistic.  Weird interplay may exit between if [default] stanza and
    # local [Upstream] stanza line up, but [Upstream] in our default file does not.  Unit test!

    diffs = compare_cfgs(default_cfg, local_cfg, allow_level0=False)

    for op in diffs:
        if op.tag == DIFF_OP_DELETE:
            # This is normal.  We don't expect all the content in default to be mirrored into local.
            continue
        elif op.tag == DIFF_OP_EQUAL:
            if isinstance(op.location, DiffStanza):
                del minz_cfg[op.location.stanza]
            else:
                # Todo: Only preserve keys for stanzas where at least 1 key has been modified
                if match_bwlist(op.location.key, args.preserve_key):
                    '''
                    sys.stderr.write("Skipping key [PRESERVED]  [{0}] key={1} value={2!r}\n"
                                 "".format(op.location.stanza, op.location.key, op.a))
                    '''
                    continue        # pragma: no cover  (peephole optimization)
                del minz_cfg[op.location.stanza][op.location.key]
                # If that was the last remaining key in the stanza, delete the entire stanza
                if not _drop_stanza_comments(minz_cfg[op.location.stanza]):
                    del minz_cfg[op.location.stanza]
        elif op.tag == DIFF_OP_INSERT:
            '''
            sys.stderr.write("Keeping local change:  <{0}> {1!r}\n-{2!r}\n+{3!r}\n\n\n".format(
                op.tag, op.location, op.b, op.a))
            '''
            continue
        elif op.tag == DIFF_OP_REPLACE:
            '''
            sys.stderr.write("Keep change:  <{0}> {1!r}\n-{2!r}\n+{3!r}\n\n\n".format(
                op.tag, op.location, op.b, op.a))
            '''
            continue

    if args.dry_run:
        if args.explode_default:
            rc = show_diff(sys.stdout, compare_cfgs(orig_cfg, minz_cfg),
                           headers=(args.target.name, args.target.name + "-new"))
        else:
            rc = show_diff(sys.stdout, compare_cfgs(local_cfg, default_cfg),
                           headers=(args.target.name, args.target.name + "-new"))
        return rc

    if args.output:
        args.output.dump(minz_cfg)
    else:
        args.target.dump(minz_cfg)
        '''
        # Makes it really hard to test if you keep overwriting the source file...
        print "Writing config to STDOUT...."
        write_conf(sys.stdout, minz_cfg)
        '''
    # Todo:  return ?  Should only be updating target if there's a change; RC should reflect this


def do_promote(args):
    if isinstance(args.target, ConfDirProxy):
        # If a directory is given instead of a target file, then assume the source filename is the
        # same as the target filename.
        args.target = args.target.get_file(os.path.basename(args.source.name))

    if not os.path.isfile(args.target.name):
        sys.stdout.write("Target file {} does not exist.  Moving source file {} to the target."
                         .format(args.target.name, args.source.name))
        # For windows:  Close out any open file descriptors first
        args.target.close()
        args.source.close()
        if args.keep:
            shutil.copy2(args.source.name, args.target.name)
        else:
            shutil.move(args.source.name, args.target.name)
        return

    # If src/dest are the same, then the file ends up being deleted.  Whoops!
    if _samefile(args.source.name, args.target.name):
        sys.stderr.write("Aborting.  SOURCE and TARGET are the same file!\n")
        return EXIT_CODE_FAILED_SAFETY_CHECK

    fp_source = file_fingerprint(args.source.name)
    fp_target = file_fingerprint(args.target.name)

    # Todo: Add a safety check prevent accidental merge of unrelated files.
    # Scenario: promote local/props.conf into default/transforms.conf
    # Possible check (1) Are basenames are different?  (props.conf vs transforms.conf)
    # Possible check (2) Are there key's in common? (DEST_KEY vs REPORT)
    # Using #1 for now, consider if there's value in #2
    bn_source = os.path.basename(args.source.name)
    bn_target = os.path.basename(args.target.name)
    if bn_source.endswith(".meta") and bn_target.endswith(".meta"):
        # Allow local.meta -> default.meta without --force or a warning message
        pass
    elif bn_source != bn_target:
        # Todo: Allow for interactive prompting when in interactive but not force mode.
        if args.force:
            sys.stderr.write("Promoting content across conf file types ({0} --> {1}) because the "
                             "'--force' CLI option was set.\n".format(bn_source, bn_target))
        else:
            sys.stderr.write("Refusing to promote content between different types of configuration "
                             "files.  {0} --> {1}  If this is intentional, override this safety"
                             "check with '--force'\n".format(bn_source, bn_target))
            return EXIT_CODE_FAILED_SAFETY_CHECK

    # Todo:  Preserve comments in the TARGET file.  Worry with promoting of comments later...
    # Parse all config files
    cfg_src = args.source.data
    cfg_tgt = args.target.data

    if not cfg_src:
        sys.stderr.write("No settings in {0}.  No content to promote.\n".format(args.source.name))
        return EXIT_CODE_NOTHING_TO_DO

    if args.mode == "ask":
        # Show a summary of how many new stanzas would be copied across; how many key changes.
        # ANd either accept all (batch) or pick selectively (batch)
        delta = compare_cfgs(cfg_tgt, cfg_src, allow_level0=False)
        delta = [op for op in delta if op.tag != DIFF_OP_DELETE]
        summarize_cfg_diffs(delta, sys.stderr)

        while True:
            input = raw_input("Would you like to apply ALL changes?  (y/n/d/q)")
            input = input[:1].lower()
            if input == 'q':
                return EXIT_CODE_USER_QUIT
            elif input == 'd':
                show_diff(sys.stdout, delta, headers=(args.source.name, args.target.name))
            elif input == 'y':
                args.mode = "batch"
                break
            elif input == 'n':
                args.mode = "interactive"
                break

    if args.mode == "interactive":
        (cfg_final_src, cfg_final_tgt) = _do_promote_interactive(cfg_src, cfg_tgt, args)
    else:
        (cfg_final_src, cfg_final_tgt) = _do_promote_automatic(cfg_src, cfg_tgt, args)

    # Minimize race condition:  Do file mtime/hash check here.  Abort if external change detected.
    # Todo: Eventually use temporary files and atomic renames to further minimize the risk
    # Todo: Make backup '.bak' files (user configurable)
    # Todo: Avoid rewriting files if NO changes were made. (preserve prior backups)
    # Todo: Restore file modes and such

    if file_fingerprint(args.source.name, fp_source):
        sys.stderr.write("Aborting!  External source file changed: {0}\n".format(args.source.name))
        return EXIT_CODE_EXTERNAL_FILE_EDIT
    if file_fingerprint(args.target.name, fp_target):
        sys.stderr.write("Aborting!  External target file changed: {0}\n".format(args.target.name))
        return EXIT_CODE_EXTERNAL_FILE_EDIT
    # Reminder:  conf entries are being removed from source and promoted into target
    args.target.dump(cfg_final_tgt)
    if not args.keep:
        # If --keep is set, we never touch the source file.
        if cfg_final_src:
            args.source.dump(cfg_final_src)
        else:
            # Config file is empty.  Should we write an empty file, or remove it?
            if args.keep_empty:
                args.source.dump(cfg_final_src)
            else:
                args.source.unlink()


def _do_promote_automatic(cfg_src, cfg_tgt, args):
    # Promote ALL entries;  simply, isn't it...  ;-)
    final_cfg = merge_conf_dicts(cfg_tgt, cfg_src)
    return ({}, final_cfg)


def _do_promote_interactive(cfg_src, cfg_tgt, args):
    ''' Interactively "promote" settings from one configuration file into another

    Model after git's "patch" mode, from git docs:

    This lets you choose one path out of a status like selection. After choosing the path, it
    presents the diff between the index and the working tree file and asks you if you want to stage
    the change of each hunk. You can select one of the following options and type return:

       y - stage this hunk
       n - do not stage this hunk
       q - quit; do not stage this hunk or any of the remaining ones
       a - stage this hunk and all later hunks in the file
       d - do not stage this hunk or any of the later hunks in the file
       g - select a hunk to go to
       / - search for a hunk matching the given regex
       j - leave this hunk undecided, see next undecided hunk
       J - leave this hunk undecided, see next hunk
       k - leave this hunk undecided, see previous undecided hunk
       K - leave this hunk undecided, see previous hunk
       s - split the current hunk into smaller hunks
       e - manually edit the current hunk
       ? - print help


    Note:  In git's "edit" mode you are literally editing a patch file, so you can modify both the
    working tree file as well as the file that's being staged.  While this is nifty, as git's own
    documentation points out (in other places), that "some changes may have confusing results".
    Therefore, it probably makes sense to let the user edit ONLY the what is going to

    ================================================================================================

    Options we may be able to support:

       Pri k   Description
       --- -   -----------
       [1] y - stage this section or key
       [1] n - do not stage this section or key
       [1] q - quit; do not stage this or any of the remaining sections or keys
       [2] a - stage this section or key and all later sections in the file
       [2] d - do not stage this section or key or any of the later section or key in the file
       [1] s - split the section into individual keys
       [3] e - edit the current section or key
       [2] ? - print help

    Q:  Is it less confusing to the user to adopt the 'local' and 'default' paradigm here?  Even
    though we know that change promotions will not *always* be between default and local.  (We can
    and should assume some familiarity with Splunk conf, less so than familiarity with git lingo.)
    '''


    def prompt_yes_no(prompt):
        while True:
            r = raw_input(prompt + " (y/n)")
            if r.lower().startswith("y"):
                return True
            elif r.lower().startswith("n"):
                return False

    out_src = deepcopy(cfg_src)
    out_cfg = deepcopy(cfg_tgt)
    ### IMPLEMENT A MANUAL MERGE/DIFF HERE:
    # What ever is migrated, move it OUT of cfg_src, and into cfg_tgt

    diff = compare_cfgs(cfg_tgt, cfg_src, allow_level0=False)
    for op in diff:
        if op.tag == DIFF_OP_DELETE:
            # This is normal.  We don't expect all the content in default to be mirrored into local.
            continue
        elif op.tag == DIFF_OP_EQUAL:
            # Q:  Should we simply remove everything from the source file that already lines
            #     up with the target?  (Probably?)  For now just skip...
            if prompt_yes_no("Remove matching entry {0}  ".format(op.location)):
                if isinstance(op.location, DiffStanza):
                    del out_src[op.location.stanza]
                else:
                    del out_src[op.location.stanza][op.location.key]
        else:
            '''
            sys.stderr.write("Found change:  <{0}> {1!r}\n-{2!r}\n+{3!r}\n\n\n".format(op.tag,
                                                                                      op.location,
                                                                                      op.b, op.a))
            '''
            if isinstance(op.location, DiffStanza):
                # Move entire stanza
                show_diff(sys.stdout, [op])
                if prompt_yes_no("Apply  [{0}]".format(op.location.stanza)):
                    out_cfg[op.location.stanza] = op.a
                    del out_src[op.location.stanza]
            else:
                show_diff(sys.stdout, [op])
                if prompt_yes_no("Apply [{0}] {1}".format(op.location.stanza, op.location.key)):
                    # Move key
                    out_cfg[op.location.stanza][op.location.key] = op.a
                    del out_src[op.location.stanza][op.location.key]
                    # If that was the last remaining key in the src stanza, delete the entire stanza
                    if not out_src[op.location.stanza]:
                        del out_src[op.location.stanza]
    return (out_src, out_cfg)


def do_sort(args):
    ''' Sort a single configuration file. '''
    stanza_delims = "\n" * args.newlines
    if args.inplace:
        failure = False
        changes = 0
        for conf in args.conf:
            try:
                # KISS:  Look for the KSCONF-NO-SORT string in the first 4k of this file.
                if not args.force and "KSCONF-NO-SORT" in open(conf.name).read(4096):
                    if not args.quiet:
                        sys.stderr.write("Skipping blacklisted file {}\n".format(conf.name))
                    continue
                data = parse_conf(conf, profile=PARSECONF_STRICT)
                conf.close()
                smart_rc = smart_write_conf(conf.name, data, stanza_delim=stanza_delims, sort=True)
            except ConfParserException, e:
                smart_rc = None
                sys.stderr.write("Error trying to process file {0}.  "
                                 "Error:  {1}\n".format(conf.name, e))
                failure = True
            if smart_rc == SMART_NOCHANGE:
                if not args.quiet:
                    sys.stderr.write("Nothing to update.  "
                                    "File {0} is already sorted\n".format(conf.name))
            else:
                sys.stderr.write("Replaced file {0} with sorted content.\n".format(conf.name))
                changes += 1
        if failure:
            return EXIT_CODE_BAD_CONF_FILE
        if changes:
            return EXIT_CODE_SORT_APPLIED
    else:
        for conf in args.conf:
            if len(args.conf) > 1:
                args.target.write("---------------- [ {0} ] ----------------\n\n".format(conf.name))
            try:
                data = parse_conf(conf, profile=PARSECONF_STRICT)
                write_conf(args.target, data, stanza_delim=stanza_delims, sort=True)
            except ConfParserException, e:
                sys.stderr.write("Error trying processing {0}.  Error:  {1}\n".format(conf.name, e))
                return EXIT_CODE_BAD_CONF_FILE


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
                    continue    # pragma: no cover  (peephole optimization)
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
                    continue     # pragma: no cover (peephole optimization)
                target_extra_files.add(tgt_file)

    for (dest_fn, src_files) in sorted(src_file_index.items()):
        dest_path = os.path.join(args.target, dest_fn)

        # Make missing destination folder, if missing
        dest_dir = os.path.dirname(dest_path)
        if not os.path.isdir(dest_dir) and not args.dry_run:
            os.makedirs(dest_dir)

        # Handle conf files and non-conf files separately
        if not conf_file_re.search(dest_fn):
            #sys.stderr.write("Considering {0:50}  NON-CONF Copy from source:  {1!r}\n".format(dest_fn, src_files[-1]))
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
                sys.stderr.write("Copy <{0}>   {1:50}  from {2}\n".format(smart_rc, dest_path, src_file))
        else:
            # Handle merging conf files
            dest = ConfFileProxy(os.path.join(args.target, dest_fn), "r+",
                                 parse_profile=PARSECONF_MID)
            srcs = [ConfFileProxy(sf, "r", parse_profile=PARSECONF_STRICT) for sf in src_files]
            #sys.stderr.write("Considering {0:50}  CONF MERGE from source:  {1!r}\n".format(dest_fn, src_files[0]))
            smart_rc = merge_conf_files(dest, srcs, dry_run=args.dry_run,
                                        banner_comment=args.banner)
            if smart_rc != SMART_NOCHANGE:
                sys.stderr.write("Merge <{0}>   {1:50}  from {2!r}\n".format(smart_rc, dest_path,
                                                                             src_files))

    if True and target_extra_files:     # Todo: Allow for cleanup to be disabled via CLI
        sys.stderr.write("Cleaning up extra files not part of source tree(s):  {0} files.\n".format(
            len(target_extra_files)))
        for dest_fn in target_extra_files:
            sys.stderr.write("Remove unwanted file {0}\n".format(dest_fn))
            os.unlink(os.path.join(args.target, dest_fn))



def do_unarchive(args):
    """ Install / upgrade a Splunk app from an archive file """
    # Handle ignored files by preserving them as much as possible.
    # Add --dry-run mode?  j/k - that's what git is for!

    if not os.path.isfile(args.tarball):
        sys.stderr.write("No such file or directory {}\n".format(args.tarball))
        return EXIT_CODE_FAILED_SAFETY_CHECK

    if not os.path.isdir(args.dest):
        sys.stderr.write("Destination directory does not exist: {}\n".format(args.dest))
        return EXIT_CODE_FAILED_SAFETY_CHECK

    f_hash = file_hash(args.tarball)
    sys.stdout.write("Inspecting archive:               {}\n".format(args.tarball))

    new_app_name = args.app_name
    # ARCHIVE PRE-CHECKS:  Archive must contain only one app, no weird paths, ...
    app_name = set()
    app_conf = {}
    files = 0
    local_files = set()
    a = extract_archive(args.tarball, extract_filter=gaf_filter_name_like("app.conf"))
    for gaf in sanity_checker(a):
        gaf_app, gaf_relpath = gaf.path.split("/", 1)
        files += 1
        if gaf.path.endswith("app.conf") and gaf.payload:
            conffile = StringIO(gaf.payload)
            conffile.name = os.path.join(args.tarball, gaf.path)
            app_conf = parse_conf(conffile, profile=PARSECONF_LOOSE)
            del conffile
        elif gaf_relpath.startswith("local") or gaf_relpath.endswith("local.meta"):
            local_files.add(gaf_relpath)
        app_name.add(gaf.path.split("/", 1)[0])
        del gaf_app, gaf_relpath
    if len(app_name) > 1:
        sys.stderr.write("The 'unarchive' command only supports extracting a single splunk app at "
                         "a time.\nHowever the archive {} contains {} apps:  {}\n"
                         "".format(args.tarball, len(app_name), ", ".join(app_name)))
        return EXIT_CODE_FAILED_SAFETY_CHECK
    else:
        app_name = app_name.pop()
    del a
    if local_files:
        sys.stderr.write("Local {} files found in the archive.  ".format(len(local_files)))
        if args.allow_local:
            sys.stderr.write("Keeping these due to the '--allow-local' flag\n")
        else:
            sys.stderr.write("Excluding these files by default.  Use '--allow-local' to override.")

    if not new_app_name and True:        # if not --no-app-name-fixes
        if app_name.endswith("-master"):
            sys.stdout.write("Automatically dropping '-master' from the app name.  This is often "
                             "the result of a github export.\n")
            # Trick, but it works...
            new_app_name = app_name[:-7]
        mo = re.search(r"(.*)-\d+\.[\d.-]+$", app_name)
        if mo:
            sys.stdout.write("Automatically removing the version suffix from the app name.  '{}' "
                             "will be extracted as '{}'\n".format(app_name, mo.group(1)))
            new_app_name = mo.group(1)

    app_basename = new_app_name or app_name
    dest_app = os.path.join(args.dest, app_basename)
    sys.stdout.write("Inspecting destination folder:    {}\n".format(os.path.abspath(dest_app)))

    # FEEDBACK TO THE USER:   UPGRADE VS INSTALL, GIT?, APP RENAME, ...
    app_name_msg = app_name
    vc_msg = "without version control support"

    old_app_conf = {}
    if os.path.isdir(dest_app):
        mode = "upgrade"
        is_git = git_is_working_tree(dest_app)
        try:
            # Ignoring the 'local' entries since distributed apps should never modify local anyways
            old_app_conf_file = os.path.join(dest_app, args.default_dir or "default", "app.conf")
            old_app_conf = parse_conf(old_app_conf_file, profile=PARSECONF_LOOSE)
        except ConfParserException:
            sys.stderr.write("Unable to read app.conf from existing install.\n")
    else:
        mode = "install"
        is_git = git_is_working_tree(args.dest)
    if is_git:
        vc_msg = "with git support"
    if new_app_name and new_app_name != app_name:
        app_name_msg = "{} (renamed from {})".format(new_app_name, app_name)

    def show_pkg_info(conf, label):
        sys.stdout.write("{} packaging info:    '{}' by {} (version {})\n".format(
            label,
            conf.get("ui", {}).get("label", "Unknown"),
            conf.get("launcher", {}).get("author", "Unknown"),
            conf.get("launcher", {}).get("version", "Unknown")))
    if old_app_conf:
        show_pkg_info(old_app_conf, " Installed app")
    if app_conf:
        show_pkg_info(app_conf, "   Tarball app")

    sys.stdout.write("About to {} the {} app {}.\n".format(mode, app_name_msg, vc_msg))

    existing_files = set()
    if mode == "upgrade":
        if is_git:
            existing_files.update(git_ls_files(dest_app))
            if not existing_files:
                sys.stderr.write("App appears to be in a git repository but no files have been "
                                 "staged or committed.  Either commit or remove '{}' and try "
                                 "again.\n".format(dest_app))
                return EXIT_CODE_FAILED_SAFETY_CHECK
            if args.git_sanity_check == "off":
                sys.stdout.write("The 'git status' safety checks have been disabled via CLI"
                                 "argument.  Skipping.\n")
            else:
                d = {
                #                untracked, ignored
                    "changed" :     (False, False),
                    "untracked" :   (True, False),
                    "ignored":      (True, True)
                }
                is_clean = git_is_clean(dest_app, *d[args.git_sanity_check])
                del d
                if is_clean:
                    sys.stdout.write("Git folder is clean.   Okay to proceed with the upgrade.\n")
                else:
                    sys.stderr.write("Unable to move forward without a clean working directory.\n"
                                     "Clean up and try again.  Modifications are listed below.\n\n")
                    sys.stderr.flush()
                    if args.git_sanity_check == "changed":
                        git_status_ui(dest_app, "--untracked-files=no")
                    elif args.git_sanity_check == "ignored":
                        git_status_ui(dest_app, "--ignored")
                    else:
                        git_status_ui(dest_app)
                    return EXIT_CODE_FAILED_SAFETY_CHECK
        else:
            for (root, dirs, filenames) in os.walk(dest_app):
                for fn in filenames:
                    existing_files.add(os.path.join(root, fn))
        sys.stdout.write("Before upgrade.  App has {} files\n".format(len(existing_files)))
    elif is_git:
        sys.stdout.write("Git clean check skipped.  Not needed for a fresh app install.\n")

    def fixup_pattern_bw(patterns, prefix=None):
        modified = []
        for pattern in patterns:
            if pattern.startswith("./"):
                if prefix:
                    pattern = "{0}/{1}".format(prefix, pattern[2:])
                else:
                    pattern = pattern[2:]
                modified.append(pattern)
            # If a pattern like 'tags.conf' or '*.bak' is provided, assume basename match (any dir)
            elif "/" not in pattern:
                modified.append("(^|.../)" + pattern)
            else:
                modified.append(pattern)
        return modified

    # PREP ARCHIVE EXTRACTION
    installed_files = set()
    excludes = list(args.exclude)
    '''
    for pattern in args.exclude:
        # If a pattern like 'default.meta' or '*.bak' is provided, assume it's a basename match.
        if "/" not in pattern:
            excludes.append(".../" + pattern)
        else:
            excludes.append(pattern)
    '''
    if not args.allow_local:
        for pattern in local_files:
            excludes.append("./" + pattern)
    excludes = fixup_pattern_bw(excludes, app_basename)
    sys.stderr.write("Extraction exclude patterns:  {!r}\n".format(excludes))
    path_rewrites = []
    files_iter = extract_archive(args.tarball)
    if True:
        files_iter = sanity_checker(files_iter)
    if args.default_dir:
        rep = "/{}/".format(args.default_dir.strip("/"))
        path_rewrites.append(("/default/", rep))
        del rep
    if new_app_name:
        # We do have the "app_name" extracted from our first pass above, but
        regex = re.compile(r'^([^/]+)(?=/)')
        path_rewrites.append((regex, new_app_name))
    if path_rewrites:
        files_iter = gen_arch_file_remapper(files_iter, path_rewrites)

    sys.stdout.write("Extracting app now...\n")
    for gaf in files_iter:
        if match_bwlist(gaf.path, excludes, escape=False):
            print "Skipping [blacklist] {}".format(gaf.path)
            continue
        if not is_git or args.git_mode in ("nochange", "stage"):
            print "{0:60s} {2:o} {1:-6d}".format(gaf.path, gaf.size, gaf.mode)
        installed_files.add(gaf.path.split("/",1)[1])
        full_path = os.path.join(args.dest, gaf.path)
        dir_exists(os.path.dirname(full_path))
        with open(full_path, "wb") as fp:
            fp.write(gaf.payload)
        os.chmod(full_path, gaf.mode)
        del fp, full_path

    files_new, files_upd, files_del = _cmp_sets(installed_files, existing_files)
    '''
    print "New: \n\t{}".format("\n\t".join(sorted(files_new)))
    print "Existing: \n\t{}".format("\n\t".join(sorted(files_upd)))
    print "Removed:  \n\t{}".format("\n\t".join(sorted(files_del)))
    '''

    sys.stdout.write("Extracted {} files:  {} new, {} existing, and {} removed\n".format(
        len(installed_files), len(files_new), len(files_upd), len(files_del)))

    # Filer out "removed" files; and let us keep some based on a keep-whitelist:  This should
    # include things like local, ".gitignore", ".gitattributes" and so on

    keep_list = [ ".git*" ]
    keep_list.extend(args.keep)
    if not args.allow_local:
        keep_list += [ "local/...", "local.meta" ]
    keep_list = fixup_pattern_bw(keep_list)
    sys.stderr.write("Keep file patterns:  {!r}\n".format(keep_list))

    files_to_delete = []
    files_to_keep = []
    for fn in files_del:
        if match_bwlist(fn, keep_list, escape=False):
            # How to handle a keep of "default.d/..." when we DO want to cleanup the default
            # redirect folder of "default.d/10-upstream"?
            # Practially this probably isn't mucn of an issue since most apps will continue to send
            # an ever increasing list of default files (to mask out old/unused ones)
            sys.stdout.write("Keeping {}\n".format(fn))
            files_to_keep.append(fn)
        else:
            files_to_delete.append(fn)
    if files_to_keep:
        sys.stdout.write("Keeping {} of {} files marked for deletion due to whitelist.\n"
                         .format(len(files_to_keep), len(files_del)))
    git_rm_queue = []

    if files_to_delete:
        sys.stdout.write("Removing files that are no longer in the upgraded version of the app.\n")
    for fn in files_to_delete:
        path = os.path.join(dest_app, fn)
        if is_git and args.git_mode in ("stage", "commit"):
            print "git rm -f {}".format(path)
            git_rm_queue.append(fn)
        else:
            print "rm -f {}".format(path)
            os.unlink(path)

    if git_rm_queue:
        # Run 'git rm file1 file2 file3 ..." (using an xargs like mechanism)
        git_cmd_iterable(["rm"], git_rm_queue, cwd=dest_app)
    del git_rm_queue

    if is_git:
        if args.git_mode in ("stage", "commit"):
            git_cmd(["add", os.path.basename(dest_app)], cwd=os.path.dirname(dest_app))
            #sys.stdout.write("git add {}\n".format(os.path.basename(dest_app)))
        '''
        else:
            sys.stdout.write("git add {}\n".format(dest_app))
        '''

        # Is there anything to stage/commit?
        if git_is_clean(os.path.dirname(dest_app), check_untracked=False):
            sys.stderr.write("No changes detected.  Nothing to {}\n".format(args.git_mode))
            return

        git_commit_app_name = app_conf.get("ui", {}).get("label", os.path.basename(dest_app))
        git_commit_new_version = app_conf.get("launcher", {}).get("version", None)
        if mode == "install":
            git_commit_message = "Install {}".format(git_commit_app_name)

            if git_commit_new_version:
                git_commit_message += " version {}".format(git_commit_new_version)
        else:
            # Todo:  Specify Upgrade/Downgrade/Refresh
            git_commit_message = "Upgrade {}".format(
                git_commit_app_name)
            git_commit_old_version = old_app_conf.get("launcher", {}).get("version", None)
            if git_commit_old_version and git_commit_new_version:
                git_commit_message += " version {} (was {})".format(git_commit_new_version,
                                                                    git_commit_old_version)
            elif git_commit_new_version:
                git_commit_message += " to version {}".format(git_commit_new_version)
        # Could possibly include some CLI arg details, like what file patterns were excluded
        git_commit_message += "\n\nSHA256 {} {}\n\nSplunk-App-managed-by: ksconf" \
                                .format(f_hash, os.path.basename(args.tarball))
        git_commit_cmd = [ "commit", os.path.basename(dest_app), "-m", git_commit_message ]

        if not args.no_edit:
            git_commit_cmd.append("--edit")

        git_commit_cmd.extend(args.git_commit_args)

        if args.git_mode == "commit":
            capture_std = True if args.no_edit else False
            proc = git_cmd(git_commit_cmd, cwd=os.path.dirname(dest_app), capture_std=capture_std)
            if proc.returncode == 0:
                sys.stderr.write("You changes have been committed.  Please review before pushing "
                                 "If you find any issues, here are some helpful options:\n\n"
                                 "To fix some minor issues in the last commit, edit and add the "
                                 "files to be fixed, then run:\n"
                                 "\tgit commit --amend\n\n"
                                 "To roll back the last commit but KEEP the app upgrade, run:\n"
                                 "\t git reset --soft HEAD^1\n\n"
                                 "To roll back the last commit and REVERT the app upgrade, run:\n"
                                 "\tgit reset --hard HEAD^1\n\n")
            else:
                sys.stderr.write("Git commit failed.  Return code {}. Git args:  git {}\n"
                                 .format(proc.returncode, list2cmdline(git_commit_cmd)))
                return EXIT_CODE_GIT_FAILURE
        elif args.git_mode == "stage":
            sys.stdout.write("To commit later, use the following\n")
            sys.stdout.write("\tgit {}\n".format(list2cmdline(git_commit_cmd).replace("\n", "\\n")))
        # When in 'nochange' mode, no point in even noting these options to the user.


class ConfDirProxy(object):
    def __init__(self, name, mode, parse_profile=None):
        self.name = name
        self._mode = mode
        self._parse_profile = parse_profile

    def get_file(self, relpath):
        path = os.path.join(self.name, relpath)
        return ConfFileProxy(path, self._mode, parse_profile=self._parse_profile, is_file=True)


class ConfFileProxy(object):
    def __init__(self, name, mode, stream=None, parse_profile=None, is_file=None):
        self.name = name
        if is_file is not None:
            self._is_file = is_file
        elif stream:
            self._is_file = False
        else:
            self._is_file = True
        self._stream = stream
        self._mode = mode
        # Not sure if there's a good reason to keep a copy of the data locally?
        self._data = None
        self._parse_profile = parse_profile or {}

    def is_file(self):
        return self._is_file

    def _type(self):
        if self._is_file:
            return "file"
        else:
            return "stream"

    def close(self):
        if self._stream:
            if not self._stream.closed:
                try:
                    self._stream.close()
                finally:
                    del self._stream
        self._stream = None

    def reset(self):
        if self._data is not None:
            self._data = None
            if self.is_file():
                self.close()
            else:
                try:
                    self.stream.seek(0)
                except:
                    raise

    def set_parser_option(self, **kwargs):
        """ Setting a key to None will remove that setting. """
        profile = dict(self._parse_profile)
        for (k, v) in kwargs.items():
            if v is None:
                if k in profile:
                    del profile[k]
            else:
                cv = profile.get(k, None)
                if cv != v:
                    profile[k] = v
        if self._parse_profile != profile:
            self._parse_profile = profile
            self.reset()

    @property
    def stream(self):
        if self._stream is None:
            self._stream = open(self.name, self._mode)
        return self._stream

    @property
    def data(self):
        if self._data is None:
            self._data = self.load()
        return self._data

    def load(self, profile=None):

        if "r" not in self._mode:
            # Q: Should we mimic the exception caused by doing a read() on a write-only file object?
            raise ValueError("Unable to load() from {} with mode '{}'".format(self._type(),
                                                                              self._mode))
        parse_profile = dict(self._parse_profile)
        if profile:
            parse_profile.update(profile)
        data = parse_conf(self.stream, profile=parse_profile)
        return data

    def dump(self, data):
        if "+" not in self._mode and "w" not in self._mode:
            raise ValueError("Unable to dump() to {} with mode '{}'".format(self._type(),
                                                                            self._mode))
        # Feels like the right thing to do????  OR self._data = data
        self._data = None
        # write vs smart write here ----
        if self._is_file:
            self.close()
            return smart_write_conf(self.name, data)
        else:
            write_conf(self._stream, data)
            return SMART_CREATE

    def unlink(self):
        # Eventually this could trigger some kind of backup or recovery mechanism
        self.close()
        return os.unlink(self.name)

    def backup(self, bkname=None):
        # One option:  Write this file directly to the git object store.  Just need to store some
        # kind of index to allow the users to pull it back.   (Sill, would need of fall-back
        # mechanism).  Git shouldn't be a hard-dependency
        raise NotImplementedError

    def checksum(self, hash="sha256"):
        raise NotImplementedError



class ConfFileType(object):
    """Factory for creating conf file object types;  returns a lazy-loader ConfFile proxy class

    Started from argparse.FileType() and then changed everything.   With our use case, it's often
    necessary to delay writing, or read before writing to a conf file (depending on weather or not
    --dry-run mode is enabled, for example.)

    Instances of FileType are typically passed as type= arguments to the
    ArgumentParser add_argument() method.

    Keyword Arguments:
        - mode      A string indicating how the file is to be opened.  Accepts "r", "w", and "r+".
        - action    'none', 'open', 'load'.   'none' means no preparation or tests;  'open' means
                    make sure the file exists/openable;  'load' means make sure the file can be
                    opened and parsed successfully.
    """

    def __init__(self, mode='r', action="open", parse_profile=None, accept_dir=False):
        self._mode = mode
        self._action = action
        self._parse_profile = parse_profile or {}
        self._accept_dir = accept_dir

    def __call__(self, string):
        from argparse import ArgumentTypeError
        # the special argument "-" means sys.std{in,out}
        if string == '-':
            if 'r' in self._mode:
                cfp = ConfFileProxy("<stdin>", "r", stream=sys.stdin, is_file=False)
                if self._action == "load":
                    try:
                        d = cfp.data
                        del d
                    except ConfParserException, e:
                        raise ArgumentTypeError("failed to parse <stdin>: {}".format(e))
                return cfp
            elif 'w' in self._mode:
                return ConfFileProxy("<stdout>", "w", stream=sys.stdout, is_file=False)
            else:
                raise ValueError('argument "-" with mode {}'.format(self._mode))
        if self._accept_dir and os.path.isdir(string):
            return ConfDirProxy(string, self._mode, parse_profile=self._parse_profile)
        if self._action == "none":
            return ConfFileProxy(string, self._mode, parse_profile=self._parse_profile)
        else:
            try:
                stream = open(string, self._mode)
                cfp = ConfFileProxy(string, self._mode, stream=stream,
                                    parse_profile=self._parse_profile, is_file=True)
                if self._action == "load":
                    # Force file to be parsed by accessing the 'data' property
                    d = cfp.data
                    del d
                return cfp
            except IOError as e:
                message = "can't open '%s': %s"
                raise ArgumentTypeError(message % (string, e))
            except ConfParserException, e:
                raise ArgumentTypeError("failed to parse '%s': %s" % (string, e))
            except TypeError, e:
                raise ArgumentTypeError("Parser config error '%s': %s" % (string, e))

    def __repr__(self):     # pragma: no cover
        args = self._mode, self._action, self._parse_profile
        args_str = ', '.join(repr(arg) for arg in args if arg != -1)
        return '%s(%s)' % (type(self).__name__, args_str)
