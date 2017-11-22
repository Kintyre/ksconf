#!/usr/bin/env python
"""
Script to consistently sort Splunk .conf files.

Supports:
 * Basic comment preservation (always moved to the top of a conf file)
 * Continuation lines
 * Global entries


Todo:
 * Add a mode that allows sorting stanzas as-is (without sorting keys within the stanza)

"""

import os
import re
import sys
from StringIO import StringIO


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


def parse_conf(stream, keys_lower=False, handle_conts=True, keep_comments=False):
    if not hasattr(stream, "read"):
        # Assume it's a filename
        stream = open(stream)

    sections = {}
    for section, entry in section_reader(stream):
        if not section:
            continue
        s = sections[section] = {}
        if handle_conts:
            entry = cont_handler(entry)
        for key, value in splitup_kvpairs(entry, keep_comments=keep_comments):
            if keys_lower:
                key = key.lower()
            s[key] = value
    return sections


def sort_conf(instream, outstream, stanza_delim="\n"):
    conf = parse_conf(instream, keep_comments=True)
    for (section, cfg) in sorted(conf.iteritems()):
        outstream.write("[%s]\n" % section)
        for (key, value) in sorted(cfg.iteritems()):
            if key.startswith("#"):
                outstream.write(value + "\n")
            else:
                outstream.write("%s = %s\n" % (key, value.replace("\n", "\\\n")))
        outstream.write(stanza_delim)


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


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("conf", metavar="FILE", nargs="+",
                        type=argparse.FileType('r'), default=[sys.stdin],
                        help="Input file to sort, or standard input.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--inplace", "-i",
                       action="store_true", default=False,
                       help="Replace the input file with a sorted version.  Warning this a "
                            "potentially destructive operation that may move/remove comments.")
    group.add_argument("--output", "-o", metavar="FILE",
                       type=argparse.FileType('w'), default=sys.stdout,
                       help="File to write results to.  Defaults to stdout.")
    parser.add_argument("-n", "--newlines", metavar="LINES", type=int, default=1,
                        help="Lines between stanzas.")
    args = parser.parse_args()

    stanza_delims = "\n" * args.newlines
    if args.inplace:
        for conf in args.conf:
            temp = StringIO()
            sort_conf(conf, temp, stanza_delim=stanza_delims)
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
                args.output.write("---------------- [ {0} ] ----------------\n\n".format(conf.name))
            sort_conf(conf, args.output, stanza_delim=stanza_delims)
