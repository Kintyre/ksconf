import sys

from ksconf.conf.delta import compare_cfgs, DIFF_OP_DELETE, DIFF_OP_EQUAL, DiffStanza, \
    DIFF_OP_INSERT, DIFF_OP_REPLACE, show_diff
from ksconf.conf.merge import merge_conf_dicts
from ksconf.conf.parser import GLOBAL_STANZA, _drop_stanza_comments
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
    for (stanza, content) in conf.iteritems():
        new_content = dict(default_stanza)
        new_content.update(content)
        n[stanza] = new_content
    return n


def do_minimize(args):
    if args.explode_default:
        # Is this the SAME as exploding the defaults AFTER the merge?;  I think NOT.  Needs testing
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
                    continue  # pragma: no cover  (peephole optimization)
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
