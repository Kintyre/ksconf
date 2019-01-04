""" SUBCOMMAND:  ksconf minimize --target=<CONF> <CONF> [ <CONF-n> ... ]

Usage example:

    ksconf minimize --target=local/inputs.conf default/inputs.conf

Example workflow:
   1. cp default/props.conf local/props.conf
   2. vi local/props.conf (edit JUST the lines you want to change)
   3. splconf minimize --target=local/props.conf default/props.conf
      (You could take this a step further by appending "$SPLUNK_HOME/system/default/props.conf"
      and removing any SHOULD_LINEMERGE = true entries (for example)

"""
from __future__ import absolute_import, unicode_literals

import six

from ksconf.commands import KsconfCmd, dedent, ConfFileType
from ksconf.conf.delta import compare_cfgs, DIFF_OP_DELETE, DIFF_OP_EQUAL, DiffStanza, \
    DIFF_OP_INSERT, DIFF_OP_REPLACE, show_diff
from ksconf.conf.merge import merge_conf_dicts
from ksconf.conf.parser import GLOBAL_STANZA, _drop_stanza_comments
from ksconf.conf.parser import PARSECONF_STRICT, PARSECONF_LOOSE
from ksconf.util.completers import conf_files_completer
from ksconf.util.file import match_bwlist


def explode_default_stanza(conf, default_stanza=None):
    """ Take the GLOBAL stanza, (aka [default]) and apply it's settings underneath ALL other
    stanzas.  This is mostly only useful in minimizing and other comparison operations. """
    if default_stanza is None:
        default_stanza = conf.get(GLOBAL_STANZA, conf.get("default"))
        if not default_stanza:
            return conf
    default_stanza = _drop_stanza_comments(default_stanza)
    n = {}
    for (stanza, content) in six.iteritems(conf):
        new_content = dict(default_stanza)
        new_content.update(content)
        n[stanza] = new_content
    return n


class MinimizeCmd(KsconfCmd):
    help = "Minimize the target file by removing entries duplicated in the default conf(s)"
    description = dedent("""\
    Minimize a conf file by removing the default settings

    Reduce local conf file to only your indented changes without manually tracking
    which entries you've edited.  Minimizing local conf files makes your local
    customizations easier to read and often results in cleaner add-on upgrades.

    A typical scenario & why does this matter:

    To customizing a Splunk app or add-on, start by copying the conf file from
    default to local and then applying your changes to the local file.  That's good.
    But stopping here may complicated future upgrades, because the local file
    doesn't contain *just* your settings, it contains all the default settings too.
    Fixes published by the app creator may be masked by your local settings.  A
    better approach is to reduce the local conf file leaving only the stanzas and
    settings that you indented to change.  This make your conf files easier to read
    and makes upgrades easier, but it's tedious to do by hand.

    For special cases, the '--explode-default' mode reduces duplication between
    entries normal stanzas and global/default entries.  If 'disabled = 0' is a
    global default, it's technically safe to remove that setting from individual
    stanzas.  But sometimes it's preferable to be explicit, and this behavior may be
    too heavy-handed for general use so it's off by default.  Use this mode if your
    conf file that's been fully-expanded.  (i.e., conf entries downloaded via REST,
    or the output of "btool list").  This isn't perfect, since many apps push their
    settings into the global namespace, but it can help.


    Example usage:

        cd Splunk_TA_nix
        cp default/inputs.conf local/inputs.conf

        # Edit 'disabled' and 'interval' settings in-place
        vi local/inputs.conf

        # Remove all the extra (unmodified) bits
        ksconf minimize --target=local/inputs.conf default/inputs.conf
    """)
    format = "manual"
    maturity = "beta"


    ''' Make sure this works before advertising (same file as target and source????)
    # Note:  Use the 'merge' command to "undo"
    ksconf merge --target=local/inputs.conf default/inputs local/inputs.conf
    '''

    def register_args(self, parser):
        parser.add_argument("conf", metavar="FILE", nargs="+",
                            type=ConfFileType("r", "load", parse_profile=PARSECONF_LOOSE), help="""
            The default configuration file(s) used to determine what base settings are "
            unnecessary to keep in the target file."""
                            ).completer = conf_files_completer
        parser.add_argument("--target", "-t", metavar="FILE",
                            type=ConfFileType("r+", "load", parse_profile=PARSECONF_STRICT),
                            help="""
            This is the local file that you with to remove the duplicate settings from.
            By default, this file will be read and the updated with a minimized version."""
                            ).completer = conf_files_completer
        grp1 = parser.add_mutually_exclusive_group()
        grp1.add_argument("--dry-run", "-D", default=False, action="store_true", help="""
            Enable dry-run mode.
            Instead of writing the minimizing the TARGET file, preview what what be removed in
            the form of a 'diff'.""")
        grp1.add_argument("--output",
                          type=ConfFileType("w", "none", parse_profile=PARSECONF_STRICT),
                          default=None, help="""
            Write the minimized output to a separate file instead of updating TARGET.
            This can be use to preview changes if dry-run produces a large diff.
            This may also be helpful in other workflows."""
                          ).completer = conf_files_completer
        parser.add_argument("--explode-default", "-E", default=False, action="store_true", help="""
            Enable minimization across stanzas as well as files for special use-cases.
            This mode will not only minimize the same stanza across multiple config files,
            it will also attempt to minimize default any values stored in the [default] or global
            stanza as well.
            Example:  Trim out cruft in savedsearches.conf by pointing to
            etc/system/default/savedsearches.conf""")
        parser.add_argument("-k", "--preserve-key", action="append", default=[], help="""
            Specify a key that should be allowed to be a duplication but should be preserved
            within the minimized output.  For example, it may be desirable keep the
            'disabled' settings in the local file, even if it's enabled by default.""")

    def run(self, args):
        if args.explode_default:
            # Is this the SAME as exploding the defaults AFTER the merge?;
            # I think NOT.  Needs testing
            cfgs = [explode_default_stanza(conf.data) for conf in args.conf]
        else:
            cfgs = [conf.data for conf in args.conf]
        # Merge all config files:
        default_cfg = merge_conf_dicts(*cfgs)
        del cfgs
        local_cfg = args.target.data
        orig_cfg = dict(args.target.data)

        if args.explode_default:
            # Make a skeleton default dict; at the highest level, that ensure that all default
            default_stanza = default_cfg.get(GLOBAL_STANZA, default_cfg.get("default"))
            skeleton_default = dict([(k, {}) for k in args.target.data])
            skeleton_default = explode_default_stanza(skeleton_default, default_stanza)
            default_cfg = merge_conf_dicts(skeleton_default, default_cfg)

            local_cfg = explode_default_stanza(local_cfg)
            local_cfg = explode_default_stanza(local_cfg, default_stanza)

        minz_cfg = dict(local_cfg)

        # This may be a bit too simplistic.  Weird interplay may exit between if [default] stanza
        # and ocal [Upstream] stanza line up, but [Upstream] in our default file does not.
        # XXX:  Add a unit test!

        diffs = compare_cfgs(default_cfg, local_cfg, allow_level0=False)

        for op in diffs:
            if op.tag == DIFF_OP_DELETE:
                # This is normal.  Don't expect all default content to be mirrored into local
                continue
            elif op.tag == DIFF_OP_EQUAL:
                if isinstance(op.location, DiffStanza):
                    del minz_cfg[op.location.stanza]
                else:
                    # Todo: Only preserve keys for stanzas where at least 1 key has been modified
                    if match_bwlist(op.location.key, args.preserve_key):
                        '''
                        self.stderr.write("Skipping key [PRESERVED]  [{0}] key={1} value={2!r}\n"
                                     "".format(op.location.stanza, op.location.key, op.a))
                        '''
                        continue  # pragma: no cover  (peephole optimization)
                    del minz_cfg[op.location.stanza][op.location.key]
                    # If that was the last remaining key in the stanza, delete the entire stanza
                    if not _drop_stanza_comments(minz_cfg[op.location.stanza]):
                        del minz_cfg[op.location.stanza]
            elif op.tag == DIFF_OP_INSERT:
                '''
                self.stderr.write("Keeping local change:  <{0}> {1!r}\n-{2!r}\n+{3!r}\n\n\n".format(
                    op.tag, op.location, op.b, op.a))
                '''
                continue
            elif op.tag == DIFF_OP_REPLACE:
                '''
                self.stderr.write("Keep change:  <{0}> {1!r}\n-{2!r}\n+{3!r}\n\n\n".format(
                    op.tag, op.location, op.b, op.a))
                '''
                continue

        if args.dry_run:
            if args.explode_default:
                rc = show_diff(self.stdout, compare_cfgs(orig_cfg, minz_cfg),
                               headers=(args.target.name, args.target.name + "-new"))
            else:
                rc = show_diff(self.stdout, compare_cfgs(local_cfg, default_cfg),
                               headers=(args.target.name, args.target.name + "-new"))
            return rc

        if args.output:
            args.output.dump(minz_cfg)
        else:
            args.target.dump(minz_cfg)
            '''
            # Makes it really hard to test if you keep overwriting the source file...
            print "Writing config to STDOUT...."
            write_conf(self.stdout, minz_cfg)
            '''
        # Todo:  return ?  Should only be updating target if there's a change; RC should reflect this
