import os
import shutil
import sys
from copy import deepcopy

from ksconf.commands import ConfDirProxy
from ksconf.conf.delta import compare_cfgs, DIFF_OP_DELETE, summarize_cfg_diffs, show_diff, \
    DIFF_OP_EQUAL, DiffStanza
from ksconf.conf.merge import merge_conf_dicts
from ksconf.consts import EXIT_CODE_FAILED_SAFETY_CHECK, EXIT_CODE_NOTHING_TO_DO, \
    EXIT_CODE_USER_QUIT, EXIT_CODE_EXTERNAL_FILE_EDIT
from ksconf.util.file import _samefile, file_fingerprint


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
