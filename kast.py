#!/usr/bin/env python
"""
kast - Kintyre's Awesome Splunk Tool

splconf - SPLunk CONFig tool

kast - Kintyre's Awesome Splunk Tool for Configs

kasct - Kintyre's Awesome Splunk Config Tool


Design goals:

 * Multi-purpose go-to .conf tool.
 * Dependability
 * Simplicity
 * No eternal dependencies (single source file, if possible; or packagable as single file.)
 * Stable CLI

"""

import os
import re
import sys
from StringIO import StringIO


GLOBAL_STANZA = object()

DUP_OVERWRITE = "overwrite"
DUP_EXCEPTION = "exception"
DUP_MERGE = "merge"

class ConfParserException(Exception): pass

class DuplicateKeyException(ConfParserException): pass

class DuplicateStanzaException(ConfParserException): pass


def section_reader(stream, section_re=re.compile(r'^\[(.*)\]\s*$')):
    """
    Break a configuration file stream into 2 components sections.  Each section is yielded as
    (section_name, lines_of_text)

    Sections that have no entries may be dropped.  Any lines before the first section are send back
    with the section name of None.
    """
    buf = []
    section = None
    for line in stream:
        line = line.rstrip("\r\n")
        match = section_re.match(line)
        if match:
            yield section, buf
            section = match.group(1)
            buf = []
        else:
            buf.append(line)
    if section or buf:
        yield section, buf


def cont_handler(iterable, continue_re=re.compile(r"^(.*)\\$"), breaker="\n"):
    buf = ""
    for line in iterable:
        mo = continue_re.match(line)
        if mo:
            buf += mo.group(1) + breaker
        elif buf:
            yield buf + line
            buf = ""
        else:
            yield line
    if buf:
        # Weird this generally shouldn't happen.
        yield buf


def splitup_kvpairs(lines, comments_re=re.compile(r"^\s*#"), keep_comments=False):
    for (i, entry) in enumerate(lines):
        if comments_re.search(entry):
            if keep_comments:
                yield ("#-%06d" % i, entry)
            continue
        if "=" in entry:
            k, v = entry.split("=", 1)
            yield k.rstrip(), v.lstrip()


def parse_conf(stream, keys_lower=False, handle_conts=True, keep_comments=False,
               dup_stanza=DUP_EXCEPTION, dup_key=DUP_OVERWRITE):
    if not hasattr(stream, "read"):
        # Assume it's a filename
        stream = open(stream)

    sections = {}
    for section, entry in section_reader(stream):
        if not section:
            section = GLOBAL_STANZA
        if section in sections:
            if dup_stanza == DUP_OVERWRITE:
               s = sections[section] = {}
            elif dup_stanza == DUP_EXCEPTION:
                raise DuplicateStanzaException("Stanza [{0}] found more than once in config "
                                               "file {1}".format(section, stream.name))
            elif dup_stanza == DUP_MERGE:
                s = sections[section]
        else:
            s = sections[section] = {}
        if handle_conts:
            entry = cont_handler(entry)
        local_stanza = {}
        for key, value in splitup_kvpairs(entry, keep_comments=keep_comments):
            if keys_lower:
                key = key.lower()
            if key in local_stanza:
                if dup_key in (DUP_OVERWRITE, DUP_MERGE):
                    s[key] = value
                    local_stanza[key] = value
                elif dup_key == DUP_EXCEPTION:
                    raise DuplicateKeyException("Stanza [{0}] has duplicate key '{1}' in file "
                                                "{2}".format(section, key, stream.name))
            else:
                local_stanza[key] = value
                s[key] = value
    return sections


def write_conf(stream, conf, stanza_delim="\n"):
    for (section, cfg) in sorted(conf.iteritems()):
        if section != GLOBAL_STANZA:
            stream.write("[%s]\n" % section)
        for (key, value) in sorted(cfg.iteritems()):
            if key.startswith("#"):
                stream.write(value + "\n")
            else:
                stream.write("%s = %s\n" % (key, value.replace("\n", "\\\n")))
        stream.write(stanza_delim)


def sort_conf(instream, outstream, stanza_delim="\n", parse_args=None):
    if parse_args is None:
        parse_args = {}
    if "keep_comments" not in parse_args:
        parse_args["keep_comments"] = True
    conf = parse_conf(instream, **parse_args)
    write_conf(outstream, conf, stanza_delim=stanza_delim)


def merge_conf_dicts(*dicts):
    result = dict()
    dicts = list(dicts)
    while dicts:
        d = dicts.pop(0)
        if not result:
            result.update(d)
        else:
            for (section, items) in d.iteritems():
                if section in result:
                    result[section].update(items)
                else:
                    result[section] = dict(items)
    return result


def _cmp_sets(a, b):
    set_a = set(a)
    set_b = set(b)
    a_only = set_a.difference(set_b)
    common = set_a.intersection(set_b)
    b_only = set_b.difference(set_a)
    return (a_only, common, b_only)


def compare_cfgs(a, b):
    """ Result tuples in format (a-only, common, b-only) """
    stanza_a, stanza_common, stanza_b = _cmp_sets(a.keys(), b.keys())
    for stanza in stanza_a:
        yield ((stanza, None), (a[stanza], None, None))
    for stanza in stanza_b:
        yield ((stanza, None), (None, None, b[stanza]))

    for stanza in stanza_common:
        ## Todo: If a==b, then we shoud yield a stanza level entry, ..((stanza,None)(None,DICT,None)) instead of dropping down into the key-by-key comparison
        a_ = a[stanza]
        b_ = b[stanza]
        kv_a, kv_common, kv_b = _cmp_sets(a_.keys(), b_.keys())

        t = {}
        for key in kv_a:
            yield ((stanza, key), (a_[key], None, None))
        for key in kv_b:
            yield ((stanza, key), (None, None, b_[key]))
        for key in kv_common:
            a__ = a_[key]
            b__ = b_[key]
            if a__ == b__:
                yield ((stanza, key), (None, a__, None))
            else:
                yield ((stanza, key), (a__, None, b__))



def do_cmp(f1, f2):
    # Borrowed from filecmp
    f1.seek(0)
    f2.seek(0)
    buffsize = 8192
    while True:
        b1 = f1.read(buffsize)
        b2 = f2.read(buffsize)
        if b1 != b2:
            return False
        if not b1:
            return True



# ==================================================================================================

def do_merge(args):
    ''' Merge multiple configuration files into one '''
    parse_args = dict(dup_stanza=args.duplicate_stanza, dup_key=args.duplicate_key,
                      keep_comments=True)
    # Parse all config files
    cfgs = [ parse_conf(conf, **parse_args) for conf in args.conf ]
    # Merge all config files:
    merged_cfg = merge_conf_dicts(*cfgs)
    write_conf(args.target, merged_cfg)


def do_diff(args):
    ''' Compare two configuration files. '''
    parse_args = dict(dup_stanza=args.duplicate_stanza, dup_key=args.duplicate_key,
                      keep_comments=args.comments)
    # Parse all config files
    cfg1 = parse_conf(args.conf1, **parse_args)
    cfg2 = parse_conf(args.conf2, **parse_args)

    last_stanza = None
    for ((stanza, key), (a, common, b)) in compare_cfgs(cfg1, cfg2):
        if stanza != last_stanza:
            if stanza is GLOBAL_STANZA:
                print "[DEFAULT]"
            else:
                print "[{0}]".format(stanza)
            last_stanza = stanza
        if key:
            prefix = "{0} = ".format(key)
        else:
            prefix = " "
        if a:
            print "+  {0} {1}".format(prefix, a)
        if common:
            print "   {0} {1}".format(prefix, common)
        if b:
            print "-  {0} {1}".format(prefix, b)


def do_patch(args):
    ''' Interactively "patch" settings from one configuration file into another '''
    pass

def do_sort(args):
    ''' Sort a single configuration file. '''
    stanza_delims = "\n" * args.newlines
    parse_args = dict(dup_stanza=args.duplicate_stanza, dup_key=args.duplicate_key,
                      keep_comments=True)
    if args.inplace:
        for conf in args.conf:
            temp = StringIO()
            try:
                sort_conf(conf, temp, stanza_delim=stanza_delims, parse_args=parse_args)
            except ConfParserException, e:
                print "Error trying to process file {0}.  Error:  {1}".format(conf.name, e)

            if do_cmp(conf, temp):
                print "Nothing to update.  File %s is already sorted." % (conf.name)
            else:
                dest = conf.name
                t = dest + ".tmp"
                conf.close()
                open(t, "w").write(temp.getvalue())
                print "Replacing file %s with sorted content." % (dest)
                os.unlink(dest)
                os.rename(t, dest)
    else:
        for conf in args.conf:
            if len(args.conf) > 1:
                args.target.write("---------------- [ {0} ] ----------------\n\n".format(conf.name))
            try:
                sort_conf(conf, args.target, stanza_delim=stanza_delims, parse_args=parse_args)
            except ConfParserException, e:
                print "Error trying processing {0}.  Error:  {1}".format(conf.name, e)
                sys.exit(-1)

def do_combine(args):
    pass




def cli():
    import argparse
    parser = argparse.ArgumentParser()

    # Common settings
    #'''
    parser.add_argument("-S", "--duplicate-stanza", default=DUP_EXCEPTION, metavar="MODE",
                        choices=[DUP_MERGE, DUP_OVERWRITE, DUP_EXCEPTION],
                        help="Set duplicate stanza handling mode.  If [stanza] exists more than "
                             "once in a single .conf file:  Mode 'overwrite' will keep the last "
                             "stanza found.  Mode 'merge' will merge keys from across all stanzas, "
                             "keeping the the value form the latest key.  Mode 'exception' "
                             "(default) will abort if duplicate stanzas are found.")
    parser.add_argument("-K", "--duplicate-key", default=DUP_EXCEPTION, metavar="MODE",
                        choices=[DUP_EXCEPTION, DUP_OVERWRITE],
                        help="Set duplicate key handling mode.  A duplicate key is a condition "
                             "that occurs when the same key (key=value) is set within the same "
                             "stanza.  Mode of 'overwrite' silently ignore duplicate keys, "
                             "keeping the latest.  Mode 'exception', the default, aborts if "
                             "duplicate keys are found.")
    #'''
    
    # Logging settings -- not really necessary for simple things like 'diff', 'merge', and 'sort';
    # more useful for 'patch', very important for 'combine'

    subparsers = parser.add_subparsers()

    # SUBCOMMAND:  splconf combine --target=<DIR> <SRC1> [ <SRC-n> ]
    sp_comb = subparsers.add_parser("combine",
                                    help="Combine .conf settings from across multiple directories "
                                         "into a single consolidated target directory.  This is "
                                         "similar to running 'merge' recursively against a set of "
                                         "directories.")
    sp_comb.set_defaults(funct=do_combine)

    # SUBCOMMAND:  splconf diff <CONF> <CONF>
    sp_diff = subparsers.add_parser("diff",
                                    help="Compare two .conf files")
    sp_diff.set_defaults(funct=do_diff)
    sp_diff.add_argument("conf1", metavar="FILE", help="Left side of the comparison")
    sp_diff.add_argument("conf2", metavar="FILE", help="Right side of the comparison")
    sp_diff.add_argument("--comments", "-C",
                         action="store_true", default=False,
                         help="Enable comparison of comments.  (Unlikely to work consitently.")


    # SUBCOMMAND:  splconf patch --target=<CONF> <CONF>
    sp_ptch = subparsers.add_parser("patch",
                                    help="Patch .conf settings from one file into another either "
                                         "automatically (all changes) or interactively allowing "
                                         "the user to pick which stanzas and keys to integrate")
    sp_ptch.set_defaults(funct=do_patch)
    sp_ptch.add_argument("source", metavar="FILE",
                         help="The source configuration file to pull changes from.")
    sp_ptch.add_argument("--target", "-t", metavar="FILE",
                         type=argparse.FileType('w'), default=sys.stdout,
                         help="Save the merged configuration files to this target file.  If not "
                              "given, the default is to write the merged conf to standard output.")
    sp_ptch.add_argument("--interactive", "-i",
                         action="store_true", default=False,
                         help="Enable interactive mode (like git '--patch' or add '-i' mode.)")
    sp_ptch.add_argument("--copy", action="store_true", default=False,
                         help="Copy settings from the source configuration file instead of "
                              "migrating the selected settings from the source to the target, "
                              "which is the default behavior if the target is a file rather than "
                              "standard out.")
    

    # SUBCOMMAND:  splconf merge --target=<CONF> <CONF> [ <CONF-n> ... ]
    sp_merg = subparsers.add_parser("merge",
                                    help="Merge two or more .conf files")
    sp_merg.set_defaults(funct=do_merge)
    sp_merg.add_argument("conf", metavar="FILE", nargs="+",
                         help="The source configuration file to pull changes from.")

    sp_merg.add_argument("--target", "-t", metavar="FILE",
                         type=argparse.FileType('w'), default=sys.stdout,
                         help="Save the merged configuration files to this target file.  If not "
                              "given, the default is to write the merged conf to standard output.")

    # SUBCOMMAND:  splconf sort <CONF>
    sp_sort = subparsers.add_parser("sort",
                                    help="Sort a Splunk .conf file")
    sp_sort.set_defaults(funct=do_sort)

    sp_sort.add_argument("conf", metavar="FILE", nargs="+",
                         type=argparse.FileType('r'), default=[sys.stdin],
                         help="Input file to sort, or standard input.")
    group = sp_sort.add_mutually_exclusive_group()
    group.add_argument("--target", "-t", metavar="FILE",
                       type=argparse.FileType('w'), default=sys.stdout,
                       help="File to write results to.  Defaults to standard output.")
    group.add_argument("--inplace", "-i",
                       action="store_true", default=False,
                       help="Replace the input file with a sorted version.  Warning this a "
                            "potentially destructive operation that may move/remove comments.")
    sp_sort.add_argument("-n", "--newlines", metavar="LINES", type=int, default=1,
                         help="Lines between stanzas.")
    args = parser.parse_args()


    try:
        args.funct(args)
    except Exception, e:
        sys.stderr.write("Unhandle top-level exception.  {0}\n".format(e))
        sys.exit(99)




if __name__ == '__main__':
    cli()
