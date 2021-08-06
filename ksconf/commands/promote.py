""" SUBCOMMAND:  ``ksconf promote <SOURCE> <TARGET>``

Usage example:  Promote local props changes (made via the UI) to the 'default' folder

.. code-block:: sh

    ksconf local/props.conf default/props.conf

"""

from __future__ import absolute_import, unicode_literals

import argparse
import os
import shutil
from copy import deepcopy

from ksconf.ext.six.moves import input

from ksconf.commands import ConfDirProxy, ConfFileType, KsconfCmd, dedent
from ksconf.conf.delta import (DIFF_OP_DELETE, DIFF_OP_EQUAL, DIFF_OP_INSERT,
                               DIFF_OP_REPLACE, DiffStanza, DiffStzKey,
                               compare_cfgs, show_diff, summarize_cfg_diffs)
from ksconf.conf.merge import merge_conf_dicts
from ksconf.conf.parser import PARSECONF_STRICT, PARSECONF_STRICT_NC
from ksconf.consts import (EXIT_CODE_EXTERNAL_FILE_EDIT,
                           EXIT_CODE_FAILED_SAFETY_CHECK,
                           EXIT_CODE_NOTHING_TO_DO, EXIT_CODE_USER_QUIT)
from ksconf.filter import FilteredList, create_filtered_list
from ksconf.util.completers import conf_files_completer
from ksconf.util.file import _samefile, file_fingerprint

""" Possible behaviors.... thinking through what CLI options make the most sense...

 Things we may want to control:

     Q: What mode of operation?
         1.)  Automatic (merge all)
         2.)  Interactive (user guided / sub-shell)
         3.)  Batch mode:  CLI driven based on a stanza or key using either a name or pattern to
              select which content should be integrated.

     Q: What happens to the original?
         1.)  Updated
           a.)  Only remove source content that has been integrated into the target.
           b.)  Let the user pick
         2.)  Preserved  (Dry-run, or don't delete the original mode);  if output is stdout.
         3.)  Remove
           a.)  Only if all content was integrated.
           b.)  If user chose to discard entry.
           c.)  Always (--always-remove)
     Q: What to do with discarded content?
         1.)  Remove from the original (destructive)
         2.)  Place in a "discard" file.  (Allow the user to select the location of the file.)
         3.)  Automatically backup discards to a internal store, and/or log.  (More difficult to
              recover, but content is always logged/recoverable with some effort.)


 Interactive approach:

     3 action options:
         Integrate/Accept: Move content from the source to the target  (e.g., local to default)
         Reject/Remove:    Discard content from the source; destructive (e.g., rm local setting)
         Skip/Keep:        Don't push to target or remove from source (no change)

"""


def empty_dict(d):
    # Or just   d == {}?   Not sure which is better
    return isinstance(d, dict) and len(d) == 0


class PromoteCmd(KsconfCmd):
    help = dedent("""\
    Promote .conf settings between layers using either batch or interactive mode.

    Frequently this is used to promote conf changes made via the UI (stored in
    the ``local`` folder) to a version-controlled directory, such as ``default``.
    """)
    description = dedent("""\
    Propagate .conf settings applied in one file to another.  Typically this is used
    to move ``local`` changes (made via the UI) into another layer, such as the
    ``default`` or a named ``default.d/50-xxxxx``) folder.

    Promote has two modes:  batch and interactive.  In batch mode, all changes are
    applied automatically and the (now empty) source file is removed.  In interactive
    mode, the user is prompted to select stanzas to promote.  This way local changes
    can be held without being promoted.

    NOTE: Changes are *MOVED* not copied, unless ``--keep`` is used.
    """)
    format = "manual"
    maturity = "beta"

    def register_args(self, parser):
        # type: (argparse.ArgumentParser) -> None
        parser.set_defaults(mode="ask")
        parser.add_argument("source", metavar="SOURCE",
                            type=ConfFileType("r+", "load", parse_profile=PARSECONF_STRICT_NC),
                            help="The source configuration file to pull changes from. "
                                 "(Typically the :file:`local` conf file)"
                            ).completer = conf_files_completer
        parser.add_argument("target", metavar="TARGET",
                            type=ConfFileType("r+", "none", accept_dir=True,
                                              parse_profile=PARSECONF_STRICT), help=dedent("""\
            Configuration file or directory to push the changes into.
            (Typically the :file:`default` folder)
            """)
                            ).completer = conf_files_completer
        grp1 = parser.add_mutually_exclusive_group()
        grp1.add_argument("--batch", "-b", action="store_const",
                          dest="mode", const="batch", help=dedent("""\
            Use batch mode where all configuration settings are automatically promoted.
            All changes are removed from source and applied to target.
            The source file will be removed unless
            ``--keep-empty`` is used."""))
        grp1.add_argument("--interactive", "-i",
                          action="store_const",
                          dest="mode", const="interactive", help=dedent("""\
            Enable interactive mode where the user will be prompted to approve
            the promotion of specific stanzas and attributes.
            The user will be able to apply, skip, or edit the changes being promoted."""))
        grp1.add_argument("--summary", "-s",
                          action="store_const",
                          dest="mode", const="summary",
                          help="Summarize content that could be promoted.")
        grp1.add_argument("--diff", "-d",
                          action="store_const",
                          dest="mode", const="diff",
                          help="Show the diff of what would be promoted.")

        parser.add_argument("--verbose", action="store_true", default=False,
                            help="Enable additional output.")

        pg_ftr = parser.add_argument_group("Automatic filtering options", dedent("""\
            Include or exclude stanzas to promote using these filter options.
            Stanzas selected by these filters will be promoted.

            All filter options can be provided multiple times.
            If you have a long list of filters, they can be saved in a file and
            referenced using the special ``file://`` prefix.  One entry per line."""))
        pg_ftr.add_argument("--match", "-m",
                            choices=["regex", "wildcard", "string"],
                            default="wildcard",
                            help=dedent("""\
            Specify pattern matching mode.
            Defaults to 'wildcard' allowing for ``*`` and  ``?`` matching.
            Use 'regex' for more power but watch out for shell escaping.
            Use 'string' to enable literal matching."""))
        pg_ftr.add_argument("--ignore-case", action="store_true",
                            help=dedent("""\
            Ignore case when comparing or matching strings.
            By default matches are case-sensitive."""))
        pg_ftr.add_argument("--invert-match", "-v", action="store_true",
                            help=dedent("""\
            Invert match results.
            This can be used to prevent content from being promoted."""))
        pg_ftr.add_argument("--stanza", metavar="PATTERN", action="append", default=[],
                            help=dedent("""\
            Promote any stanza with a name matching the given pattern.
            PATTERN supports bulk patterns via the ``file://`` prefix."""))

        parser.add_argument("--force", "-f",
                            action="store_true", default=False,
                            help="Disable safety checks. "
                            "Don't check to see if SOURCE and TARGET share the same basename.")
        parser.add_argument("--keep", "-k",
                            action="store_true", default=False, help=dedent("""\
            Keep conf settings in the source file.
            All changes will be copied into the TARGET file instead of being moved there.
            This is typically a bad idea since local always overrides default."""))
        parser.add_argument("--keep-empty",
                            action="store_true", default=False, help=dedent("""\
            Keep the source file, even if after the settings promotions the file has no content.
            By default, SOURCE will be removed after all content has been moved into TARGET.
            Splunk will re-create any necessary local files on the fly."""))

    def run(self, args):
        if isinstance(args.target, ConfDirProxy):
            # If a directory is given instead of a target file, then assume the source filename
            # and target filename are the same.
            # Also handle local/default meta:     e.g.:   ksconf promote local.meta .
            source_basename = os.path.basename(args.source.name)
            if source_basename == "local.meta":
                args.target = args.target.get_file("default.meta")
            else:
                args.target = args.target.get_file(source_basename)
            del source_basename

        if not os.path.isfile(args.target.name):
            self.stdout.write("Target file {} does not exist.  "
                              "Moving source file {} to the target.\n"
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
            self.stderr.write("Aborting.  SOURCE and TARGET are the same file!\n")
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
            if args.mode in ("summary", "diff"):
                pass
            # Todo: Allow for interactive prompting when in interactive but not force mode.
            elif args.force:
                self.stderr.write(
                    "Promoting content across conf file types ({0} --> {1}) because the "
                    "'--force' CLI option was set.\n".format(bn_source, bn_target))
            else:
                self.stderr.write(
                    "Refusing to promote content between different types of configuration "
                    "files.  {0} --> {1}  If this is intentional, override this safety "
                    "check with '--force'\n".format(bn_source, bn_target))
                return EXIT_CODE_FAILED_SAFETY_CHECK

        # Todo:  Preserve comments in the TARGET file.  Worry with promoting of comments later...
        # Parse all config files
        cfg_src = args.source.data
        cfg_tgt = args.target.data

        if not cfg_src:
            self.stderr.write("No settings in {}.  Nothing to promote.\n".format(args.source.name))
            return EXIT_CODE_NOTHING_TO_DO

        # Prep filters and determine if there's any automatic work that can be done
        if self.prep_filters(args):
            # Run filter and then return control back
            delta, cfg_src, cfg_tgt = self._do_promote_list(cfg_src, cfg_tgt, args)
        else:
            delta = compare_cfgs(cfg_tgt, cfg_src, replace_level="key")
            delta = [op for op in delta if op.tag != DIFF_OP_DELETE]

        if args.mode == "diff":
            self.stderr.write("\n")
            show_diff(self.stderr, delta)
            return

        if args.mode in ("ask", "summary"):
            # Show a summary of how many new stanzas would be copied across; how many key changes.
            # And either accept all (batch) or pick selectively (batch)
            summarize_cfg_diffs(delta, self.stderr)
            if args.mode == "summary":
                return

            while True:
                resp = input("Would you like to apply ALL changes?  (y/n/d/q) ")
                resp = resp[:1].lower()
                if resp == 'q':
                    return EXIT_CODE_USER_QUIT
                elif resp == 'd':
                    show_diff(self.stdout, delta, headers=(args.source.name, args.target.name))
                elif resp == 'y':
                    args.mode = "batch"
                    break
                elif resp == 'n':
                    args.mode = "interactive"
                    break

        if args.mode == "interactive":
            (cfg_final_src, cfg_final_tgt) = self._do_promote_interactive(cfg_src, cfg_tgt, args)
        elif args.stanza:
            # We already applied changes above.
            cfg_final_src, cfg_final_tgt = cfg_src, cfg_tgt
        else:
            (cfg_final_src, cfg_final_tgt) = self._do_promote_automatic(cfg_src, cfg_tgt, args)

        # Minimize race condition:  Do file mtime/hash check here.  Abort on external change.
        # Todo: Eventually use temporary files and atomic renames to further minimize the risk
        # Todo: Make backup '.bak' files (user configurable)
        # Todo: Avoid rewriting files if NO changes were made. (preserve prior backups)
        # Todo: Restore file modes and such

        if file_fingerprint(args.source.name, fp_source):
            self.stderr.write("Aborting!  External source file changed: {0}\n".
                              format(args.source.name))
            return EXIT_CODE_EXTERNAL_FILE_EDIT
        if file_fingerprint(args.target.name, fp_target):
            self.stderr.write("Aborting!  External target file changed: {0}\n".
                              format(args.target.name))
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

    def prep_filters(self, args):
        flags = 0
        if args.ignore_case:
            flags |= FilteredList.IGNORECASE
        if args.verbose:
            flags |= FilteredList.VERBOSE
        self.stanza_filters = create_filtered_list(args.match, flags).feedall(args.stanza)
        if args.stanza:
            return True

    def apply_filters(self, delta, invert_match=False):
        for op in delta:
            if self.stanza_filters.match_stanza(op.location.stanza) ^ invert_match:
                yield op

    @staticmethod
    def combine_stanza(a, b):
        if a is None:
            return b
        d = dict(a)
        d.update(b)
        return d

    def _do_promote_automatic(self, cfg_src, cfg_tgt, args):
        # Promote ALL entries;  simply, isn't it...  ;-)
        final_cfg = merge_conf_dicts(cfg_tgt, cfg_src)
        return ({}, final_cfg)

    def _do_promote_interactive(self, cfg_src, cfg_tgt, args):
        ''' Interactively "promote" settings from one configuration file into another

        Model after git's "patch" mode, from git docs:

        This lets you choose one path out of a status like selection. After choosing the path, it
        presents the diff between the index and the working tree file and asks you if you want to
        stage the change of each hunk. You can select one of the following options and type return:

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


        Note:  In git's "edit" mode you are literally editing a patch file, so you can modify both
        the working tree file as well as the file that's being staged.  While this is nifty, as
        git's own documentation points out (in other places), that "some changes may have confusing
        results".  Therefore, it probably makes sense to limit what the user can edit.

        ============================================================================================

        Options we may be able to support:

           Pri k   Description
           --- -   -----------
           [1] y - stage this section or key
           [1] n - do not stage this section or key
           [1] q - quit; do not stage this or any of the remaining sections or attributes
           [2] a - stage this section or key and all later sections in the file
           [2] d - do not stage this section or key or any of the later section or key in the file
           [1] s - split the section into individual attributes
           [3] e - edit the current section or key
           [2] ? - print help

        Q:  Is it less confusing to the user to adopt the 'local' and 'default' paradigm here?
        Even though we know that change promotions will not *always* be between default and local.
        (We can and should assume some familiarity with Splunk conf terms, less so than familiarity
        with git lingo.)
        '''

        def prompt_yes_no(prompt):
            print("")
            while True:
                r = input(prompt + " (y/n) ")
                if r.lower().startswith("y"):
                    return True
                elif r.lower().startswith("n"):
                    return False

        out_src = deepcopy(cfg_src)
        out_cfg = deepcopy(cfg_tgt)
        # Todo:  IMPLEMENT A MANUAL MERGE/DIFF HERE:
        # What ever is migrated, move it OUT of cfg_src, and into cfg_tgt

        diff = compare_cfgs(cfg_tgt, cfg_src, replace_level="key")
        for op in diff:
            if op.tag == DIFF_OP_DELETE:
                # This is normal.   Only changed attributes are copied & updated in local.
                continue
            elif op.tag == DIFF_OP_EQUAL:
                # Q:  Should we simply remove everything from the source file that already lines
                #     up with the target?  Just ask
                if isinstance(op.location, DiffStzKey):
                    msg = "[{0.stanza}]  {0.key}".format(op.location)
                elif isinstance(op.location, DiffStanza):
                    msg = "[{0.stanza}]".format(op.location)
                if prompt_yes_no("Remove matching entry {0}  ".format(msg)):
                    if isinstance(op.location, DiffStanza):
                        del out_src[op.location.stanza]
                    else:
                        del out_src[op.location.stanza][op.location.key]
            else:
                '''
                self.stderr.write("Found change:  <{0}> {1!r}\n-{2!r}\n+{3!r}\n\n\n"
                    .format(op.tag, op.location, op.b, op.a))
                '''
                if isinstance(op.location, DiffStanza):
                    # Move entire stanza
                    """ ----  If we need to support empty stanza promotion.....
                    print("OP:   {!r}".format(op))
                    if empty_dict(op.b):
                        print("Empty stanza [{}]".format(op.location.stanza))
                    else:
                    """
                    if True:
                        show_diff(self.stdout, [op])
                    if prompt_yes_no("Apply [{0}]".format(op.location.stanza)):
                        out_cfg[op.location.stanza] = self.combine_stanza(op.a, op.b)
                        del out_src[op.location.stanza]
                else:
                    show_diff(self.stdout, [op])
                    # Logically, this must be either an INSERT or REPLACE
                    if prompt_yes_no("Apply [{0}] {1}".format(op.location.stanza, op.location.key)):
                        # Move key
                        out_cfg[op.location.stanza][op.location.key] = op.b
                        del out_src[op.location.stanza][op.location.key]
                        # If last remaining key in the src stanza?  Then delete the entire stanza
                        if not out_src[op.location.stanza]:
                            del out_src[op.location.stanza]
        return (out_src, out_cfg)

    def _do_promote_list(self, cfg_src, cfg_tgt, args):
        out_src = deepcopy(cfg_src)
        out_cfg = deepcopy(cfg_tgt)
        diff = compare_cfgs(cfg_tgt, cfg_src, replace_level="key")
        diff = [op for op in self.apply_filters(diff, args.invert_match)
                if op.tag in (DIFF_OP_INSERT, DIFF_OP_REPLACE)]
        for op in diff:
            if args.verbose:
                show_diff(self.stdout, [op])
            if isinstance(op.location, DiffStanza):
                # Move entire stanza
                out_cfg[op.location.stanza] = self.combine_stanza(op.a, op.b)
                del out_src[op.location.stanza]
            else:
                # Move key
                out_cfg[op.location.stanza][op.location.key] = op.b
                del out_src[op.location.stanza][op.location.key]
                # If last remaining key in the src stanza?  Then delete the entire stanza
                if not out_src[op.location.stanza]:
                    del out_src[op.location.stanza]
        return (diff, out_src, out_cfg)
