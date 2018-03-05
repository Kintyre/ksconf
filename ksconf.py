#!/usr/bin/env python
"""ksconf - Kintyre Splunk CONFig tool

kast - Kintyre's Awesome Splunk Tool

splconf - SPLunk CONFig tool

splkt - Splunk Konfig tool (K for Kintyre/Config...  yeah, it's bad.  why geeks shouldn't name things)

kasc - Kintyre's Awesome Splunk Tool for Configs

kasct - Kintyre's Awesome Splunk Config Tool

ksconf - Kintyre Splunk CONFig tool

kscfg - Kintyre Splunk ConFiG tool

ksc - Kintyre Splunk Config tool


Design goals:

 * Multi-purpose go-to .conf tool.
 * Dependability
 * Simplicity
 * No eternal dependencies (single source file, if possible; or packable as single file.)
 * Stable CLI
 * Good scripting interface for deployment scripts and/or git hooks




Merge magic:

 * Allow certain keys to be suppressed by subsequent layers by using some kind of sentinel value,
   like "<<BLANK>>" or something.  Use case:  Disabling a transformer defined in the upstream layer.
   So instead of "TRANSFORMS-class=" being shown in the output, the entire key is removed from the
   destination.)
 * Allow stanzas to be suppressed with some kind of special key value token.  Use case:  Removing
   unwanted eventgen related source matching stanza's like "[source::...(osx.*|sample.*.osx)]"
   instead of having to suppress individual keys (difficult to maintain).
 * Allow a special wildcard stanzas that globally apply one or more keys to all subsequent stanzas.
   Use Case:  set "index=os_<ORG>" on all existing stanzas in an inputs.conf file.  Perhaps this
   could be setup like [*] index=os_prod;  or [<<COPY_TO_ALL>>] index=os_prod
 * (Maybe) allow list augmentation (or subtraction?) to comma or semicolon separated lists.
        TRANSFORMS-syslog = <<APPEND>> ciso-asa-sourcetype-rewrite   OR
        TRANSFORMS-syslog = <<REMOVE>> ciso-asa-sourcetype-rewrite

   Possible filter operators include:
        <<APPEND>> string           Pure string concatenation
        <<APPEND(sep=",")>> i1,i2   Handles situation where parent may be empty (no leading ",")
        <<REMOVE>> string           Removes "string" from parent value; empty if no parent
        <<ADD(sep=";")>> i1;i2      Does SET addition.  Preserves order where possible, squash dups.
        <<SUBTRACT(sep=",")>> i1    Does SET reduction.  Preserves order where possible, squash dups.

    Down the road stuff:        (Let's be careful NOT to build yet another template language...)
        <<LOOKUP(envvar="HOSTNAME")>>               <<-- setting host in inputs.conf, part of a monitor stanza
                                                         NOTE:  This is possibly bad or misleading example as HOSTAME maybe on a deployer not on the SHC memeber, for example.
        <<LOOKUP(file="../regex.txt", line=2)>>     <<-- Can't thing of a legitimate use, currently
        <<RE_SUB("pattern", "replace", count=2)>>   <<-- Parsing this will be a challenge, possibly allow flexible regex start/stop characters?
        <<INTROSPECT(key, stanza="default")>>       <<-- Reference another value located within the current config file.

    # May just make these easily registered via decorator; align with python function calling norms
    @register_filter("APPEND")
    def filter_op_APPEND(context, sep=","):
        # context.op is the name of the filter, "APPEND" in this case.
        # context.stanza is name of the current stanza
        # context.key is the name of the key who's value is being operated on
        # context.parent is the original string value.
        # context.payload is the raw value of the current key, without magic text (may be blank)
        #
        # Allow for standard python style function argument passing; allowing for both positional
        # and named parameters.            *args, **kwargs


To do (Someday):

 * Separate the concepts of global and empty (anonymous) stanzas.  Entries at the top of the
   file, vs stuff literally under a "[]" stanza (e.g., metadata files)
 * Add automatic metadata merging support so that when patching changes from local to default,
   for example, the appropriate local metadata settings move from local.meta to default.meta.
   There are quite a few complications to this idea.
 * Build a proper conf parser that tracks things correctly.  (Preferably one that has a dict-like
   interface so existing code doesn't break, but that's a lower-priority).  This is necessary to
   (1) improve comment handling, (2) edit a single stanza or key without rewrite the entire file,
   (3) improve syntax error reporting (line numbers), and (4) preserve original ordering.
   For example, it would be nice to run patch in away that only applies changes and doesn't re-sort
   and loose/mangle all comments.
 * Allow config stanzas to be sorted without sorting the stanza content.  Useful for typically 
   hand-created file like props.conf or transforms.conf where there's mixed comments and keys and a
   preferred reading order.
 * Find a good way to unit test this.  Probably requires a stub class (based on the above)
   Keep unit-test in a separate file (keep size under control.)


"""



import os
import re
import sys
import difflib
from collections import namedtuple, defaultdict, Counter
from copy import deepcopy
from StringIO import StringIO



class Token(object):
    """ Immutable token object.  deepcopy returns the same object """
    def __deepcopy__(self, memo):
        memo[id(self)] = self
        return self

GLOBAL_STANZA = Token()

DUP_OVERWRITE = "overwrite"
DUP_EXCEPTION = "exception"
DUP_MERGE = "merge"



class ConfParserException(Exception):
    pass

class DuplicateKeyException(ConfParserException):
    pass

class DuplicateStanzaException(ConfParserException):
    pass


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
            if buf:
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


def splitup_kvpairs(lines, comments_re=re.compile(r"^\s*#"), keep_comments=False, strict=False):
    for (i, entry) in enumerate(lines):
        if comments_re.search(entry):
            if keep_comments:
                yield ("#-%06d" % i, entry)
            continue
        if "=" in entry:
            k, v = entry.split("=", 1)
            yield k.rstrip(), v.lstrip()
            continue
        if strict and entry.strip():
            raise ConfParserException("Unexpected entry:  {0}".format(entry))


def parse_conf(stream, keys_lower=False, handle_conts=True, keep_comments=False,
               dup_stanza=DUP_EXCEPTION, dup_key=DUP_OVERWRITE, strict=False):
    if not hasattr(stream, "read"):
        # Assume it's a filename
        stream = open(stream)

    sections = {}
    # Q: What's the value of allowing line continuations to be disabled?
    if handle_conts:
        reader = section_reader(cont_handler(stream))
    else:
        reader = section_reader(stream)
    for section, entry in reader:
        if section is None:
            section = GLOBAL_STANZA
        if section in sections:
            if dup_stanza == DUP_OVERWRITE:
               s = sections[section] = {}
            elif dup_stanza == DUP_EXCEPTION:
                raise DuplicateStanzaException("Stanza [{0}] found more than once in config "
                                               "file {1}".format(_format_stanza(section),
                                                                 stream.name))
            elif dup_stanza == DUP_MERGE:
                s = sections[section]
        else:
            s = sections[section] = {}
        local_stanza = {}
        for key, value in splitup_kvpairs(entry, keep_comments=keep_comments, strict=strict):
            if keys_lower:
                key = key.lower()
            if key in local_stanza:
                if dup_key in (DUP_OVERWRITE, DUP_MERGE):
                    s[key] = value
                    local_stanza[key] = value
                elif dup_key == DUP_EXCEPTION:
                    raise DuplicateKeyException("Stanza [{0}] has duplicate key '{1}' in file "
                                                "{2}".format(_format_stanza(section),
                                                             key, stream.name))
            else:
                local_stanza[key] = value
                s[key] = value
    return sections


def write_conf(stream, conf, stanza_delim="\n"):
    conf = dict(conf)

    def write_stanza_body(items):
        for (key, value) in sorted(items.iteritems()):
            if key.startswith("#"):
                stream.write("{0}\n".format(value))
            else:
                stream.write("{0} = {1}\n".format(key, value.replace("\n", "\\\n")))
        stream.write(stanza_delim)

    # Global MUST be written first
    if GLOBAL_STANZA in conf:
        write_stanza_body(conf[GLOBAL_STANZA])
        # Remove from our shallow copy of conf, to prevent dup output
        del conf[GLOBAL_STANZA]
    for (section, cfg) in sorted(conf.iteritems()):
        stream.write("[{0}]\n".format(section))
        write_stanza_body(cfg)


def sort_conf(instream, outstream, stanza_delim="\n", parse_args=None):
    if parse_args is None:
        parse_args = {}
    if "keep_comments" not in parse_args:
        parse_args["keep_comments"] = True
    conf = parse_conf(instream, **parse_args)
    write_conf(outstream, conf, stanza_delim=stanza_delim)


# TODO: Replace this with "<<DROP_STANZA>>" on ANY key.  Let's use just ONE mechanism for all of
# these merge hints/customizations
STANZA_MAGIC_KEY = "_stanza"
STANZA_OP_DROP = "<<DROP>>"


def _merge_conf_dicts(base, new_layer):
    """ Merge new_layer on top of base.  It's up to the caller to deal with any necessary object
    copying to avoid odd referencing between the base and new_layer"""
    for (section, items) in new_layer.iteritems():
        if STANZA_MAGIC_KEY in items:
            magic_op = items[STANZA_MAGIC_KEY]
            if STANZA_OP_DROP in magic_op:
                # If this section exist in a parent (base), then drop it now
                if section in base:
                    del base[section]
                continue
        if section in base:
            # TODO:  Support other magic here...
            base[section].update(items)
        else:
            # TODO:  Support other magic here too..., though with no parent info
            base[section] = items
    # Nothing to return, base is updated in-place


def merge_conf_dicts(*dicts):
    result = {}
    for d in dicts:
        d = deepcopy(d)
        if not result:
            result = d
        else:
            # Merge each subsequent layer on one at a time
            _merge_conf_dicts(result, d)
    return result


def _cmp_sets(a, b):
    """ Result tuples in format (a-only, common, b-only) """
    set_a = set(a)
    set_b = set(b)
    a_only = sorted(set_a.difference(set_b))
    common = sorted(set_a.intersection(set_b))
    b_only = sorted(set_b.difference(set_a))
    return (a_only, common, b_only)


DIFF_OP_INSERT  = "insert"
DIFF_OP_DELETE  = "delete"
DIFF_OP_REPLACE = "replace"
DIFF_OP_EQUAL   = "equal"


DiffOp = namedtuple("DiffOp", ("tag", "location", "a", "b"))

def compare_cfgs(a, b):
    '''
    Opcode tags borrowed from difflib.SequenceMatcher

    Return list of 5-tuples describing how to turn a into b. Each tuple is of the form

        (tag, location, a, b)

    tag:

    Value	    Meaning
    'replace'	same element in both, but different values.
    'delete'	remove value b
    'insert'    insert value a
    'equal'	    same values in both

    location is a tuple that can take the following forms:

    (level, pos0, ... posN)
    (0)                 Global file level context (e.g., both files are the same)
    (1, stanza)         Stanzas are the same, or completely different (no shared keys)
    (2, stanza, key)    Key level, indicating


    Possible alternatives:

    https://dictdiffer.readthedocs.io/en/latest/#dictdiffer.patch

    '''

    # Level 1 - Compare entire file
    stanza_a, stanza_common, stanza_b = _cmp_sets(a.keys(), b.keys())
    delta = []
    if a == b:
        return [DiffOp(DIFF_OP_EQUAL, (0,), a, b)]

    if not stanza_common:
        # Q:  Does this specific output make the consumer's job more difficult?
        # Nothing in common between these two files
        # Note:  Stanza renames are not detected and are out of scope.
        return [DiffOp(DIFF_OP_REPLACE, (0,), a, b)]

    # Level 2 - Compare stanzas

    # Make sure GLOBAL stanza is output first
    all_stanzas = set(a.keys()).union(b.keys())
    if GLOBAL_STANZA in all_stanzas:
        all_stanzas.remove(GLOBAL_STANZA)
        all_stanzas = [GLOBAL_STANZA] + list(all_stanzas)
    else:
        all_stanzas = list(all_stanzas)
    all_stanzas.sort()

    for stanza in all_stanzas:
        if stanza in a and stanza in b:
            a_ = a[stanza]
            b_ = b[stanza]
            # Note: make sure that '==' operator continues work with custom conf parsing classes.
            if a_ == b_:
                delta.append(DiffOp(DIFF_OP_EQUAL, (1, stanza), a_, b_))
                continue
            kv_a, kv_common, kv_b = _cmp_sets(a_.keys(), b_.keys())
            if not kv_common:
                # No keys in common, just swap
                delta.append(DiffOp(DIFF_OP_REPLACE, (1, stanza), a_, b_))
                continue

            # Level 3 - Key comparisons
            for key in kv_a:
                delta.append(DiffOp(DIFF_OP_DELETE, (2, stanza, key), None, a_[key]))
            for key in kv_b:
                delta.append(DiffOp(DIFF_OP_INSERT, (2, stanza, key), b_[key], None))
            for key in kv_common:
                a__ = a_[key]
                b__ = b_[key]
                if a__ == b__:
                    delta.append(DiffOp(DIFF_OP_EQUAL, (2, stanza, key), a__, b__))
                else:
                    delta.append(DiffOp(DIFF_OP_REPLACE, (2, stanza, key), a__, b__))
        elif stanza in a:
            # A only
            delta.append(DiffOp(DIFF_OP_DELETE, (1, stanza), None, a[stanza]))
        else:
            # B only
            delta.append(DiffOp(DIFF_OP_INSERT, (1, stanza), b[stanza], None))
    return delta


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


def _stdin_iter(stream=None):
    if stream is None:
        stream = sys.stdin
    for line in stream:
        yield line.rstrip()


def _format_stanza(stanza):
    """ Return a more human readable stanza name."""
    if stanza is GLOBAL_STANZA:
        return "GLOBAL"
    else:
        return stanza

# ==================================================================================================


def do_check(args):
    parse_args = dict(dup_stanza=args.duplicate_stanza, dup_key=args.duplicate_key,
                      keep_comments=False, strict=True)

    # Should we read a list of conf files from STDIN?
    if len(args.conf) == 1 and args.conf[0] == "-":
        confs = _stdin_iter()
    else:
        confs = args.conf
    c = Counter()
    exit_code = 0
    for conf in confs:
        c["checked"] += 1
        if not os.path.isfile(conf):
            sys.stderr.write("Skipping missing file:  {0}\n".format(conf))
            c["missing"] += 1
        try:
            parse_conf(conf, **parse_args)
            c["okay"] += 1
            if True:    # verbose
                sys.stdout.write("Successfully parsed {0}\n".format(conf))
                sys.stdout.flush()
        except ConfParserException, e:
            sys.stderr.write("Error in file {0}:  {1}\n".format(conf, e))
            sys.stderr.flush()
            exit_code = 1
            # TODO:  Break out counts by error type/category (there's only a few of them)
            c["error"] += 1
        except Exception, e:
            sys.stderr.write("Unhandled top-level exception while parsing {0}.  "
                             "Aborting.\n{1}".format(conf, e))
            exit_code = 2
            c["error"] += 1
            break
    if True:    #show stats or verbose
        sys.stdout.write("Completed checking {0[checked]} files.  rc={1} Breakdown:\n"
                         "   {0[okay]} files were parsed successfully.\n"
                         "   {0[error]} files failed.\n".format(c, exit_code))
    sys.exit(exit_code)


def do_merge(args):
    ''' Merge multiple configuration files into one '''
    parse_args = dict(dup_stanza=args.duplicate_stanza, dup_key=args.duplicate_key,
                      keep_comments=True, strict=True)
    # Parse all config files
    cfgs = [ parse_conf(conf, **parse_args) for conf in args.conf ]
    # Merge all config files:
    merged_cfg = merge_conf_dicts(*cfgs)
    write_conf(args.target, merged_cfg)


def do_diff(args):
    ''' Compare two configuration files. '''

    stream = args.output

    parse_args = dict(dup_stanza=args.duplicate_stanza, dup_key=args.duplicate_key,
                      keep_comments=False, strict=True)  #args.comments)
    # Parse all config files
    cfg1 = parse_conf(args.conf1, **parse_args)
    cfg2 = parse_conf(args.conf2, **parse_args)

    import datetime

    def header(sign, filename):
        ts = datetime.datetime.fromtimestamp(os.stat(filename).st_mtime)
        stream.write("{0} {1:19} {2}\n".format(sign*3, filename, ts))

    def show_value(value, stanza, key, prefix=""):
        if isinstance(value, dict):
            stream.write("{0}[{1}]\n".format(prefix, _format_stanza(stanza)))
            lines = [ "{0}{1} = {2}".format(prefix, x, y) for x, y in value.iteritems() ]
            stream.write("\n".join(lines) + "\n\n")
        else:
            if "\n" in value:
                lines = value.replace("\n", "\\\n").split("\n")
                stream.write("{0}{1} = {2}\n".format(prefix, key, lines.pop(0)))
                for line in lines:
                    stream.write(" {0}\n".format(line))
            else:
                stream.write("{0}{1} = {2}\n".format(prefix, key, value))

    def show_multiline_diff(value_a, value_b, key):
        def f(v):
            r = "{0} = {1}".format(key, v)
            r = r.replace("\n", "\\\n")
            return r.splitlines()
        a = f(value_a)
        b = f(value_b)
        differ = difflib.Differ()
        for d in differ.compare(a, b):
            stream.write(d)
            stream.write("\n")

    diffs = compare_cfgs(cfg1, cfg2)

    # No changes between files
    if len(diffs) == 1 and diffs[0].tag == DIFF_OP_EQUAL:
        return

    header("-", args.conf1)
    header("+", args.conf2)

    last_stanza = None
    for op in diffs:
        l = op.location[0]
        if l == 1:
            t = "stanza"
            stanza = op.location[1]
            key = None
        elif l == 2:
            t = "key"
            stanza, key = op.location[1:]

        if t == "stanza":
            if op.tag in (DIFF_OP_DELETE, DIFF_OP_REPLACE):
                show_value(op.b, stanza, key, "-")
            if op.tag in (DIFF_OP_INSERT, DIFF_OP_REPLACE):
                show_value(op.a, stanza, key, "+")
            continue

        if stanza != last_stanza:
            if last_stanza is not None:
                # Line break after last stanza
                stream.write("\n")
                stream.flush()
            stream.write(" [{0}]\n".format(_format_stanza(stanza)))
            last_stanza = stanza

        if op.tag == DIFF_OP_INSERT:
            show_value(op.a, stanza, key, "+")
        elif op.tag == DIFF_OP_DELETE:
            show_value(op.b, stanza, key, "-")
        elif op.tag == DIFF_OP_REPLACE:
            if "\n" in op.a or "\n" in op.b:
                show_multiline_diff(op.a, op.b, key)
            else:
                show_value(op.b, stanza, key, "-")
                show_value(op.a, stanza, key, "+")
        elif op.tag == DIFF_OP_EQUAL:
            show_value(op.b, stanza, key, " ")

        '''
        if key:
            print "{0} {1}={2}".format(p, key, v)
        else:
            v = "\n".join(["{0}{1} = {2}".format(p, x,y) for x, y in v.iteritems()])
            print "{0} {1}={2}".format(p, op.location[-1], v)
        '''
        '''
        if key:
            prefix = "{0} = ".format(key)
        else:
            prefix = " "
        '''
    """
    for op in diffs:
        p = prefix[op.tag]
        print "{0} {1:40}    {2:20} <=> {3:20}".format(op.tag, op.location[1:], op.a, op.b)
    """
    stream.flush()


def do_patch(args):
    ''' Interactively "patch" settings from one configuration file into another '''
    # Todo: Implement
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
                print "Replacing file %s with sorted content." % (dest,)
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



def do_unarchive(args):
    """ Install / upgrade a Splunk app from an archive file """
    # Must support tgz, tar, and zip
    # TODO: Make this work well if git hold many apps, or if the destination folder IS the git app.
    # TODO: Have git check for a clean status before doing anything (if in a git working tree)
    # Handle ignored files by preserving them as much as possible.
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

    # SUBCOMMAND:  splconf check <CONF>
    sp_chck = subparsers.add_parser("check",
                                    help="Perform a basic syntax and sanity check on .conf files")
    sp_chck.set_defaults(funct=do_check)
    sp_chck.add_argument("conf", metavar="FILE", nargs="+",
                         help="One or more configuration files to check.  If the special value of "
                              "'-' is given, then the list of files to validate is read from "
                              "standard input")
    ''' # Do we really need this?
    sp_chck.add_argument("--max-errors", metavar="INT", type=int, default=0,
                         help="Abort check if more than this many files fail validation.  Useful 
                         for a pre-commit hook where any failure is unacceptable.")
    '''
    # Usage example:   find . -name '*.conf' | splconf check -  (Nice little pre-commit script)

    # SUBCOMMAND:  splconf combine --target=<DIR> <SRC1> [ <SRC-n> ]
    sp_comb = subparsers.add_parser("combine",
                                    help="Combine .conf settings from across multiple directories "
                                         "into a single consolidated target directory.  This is "
                                         "similar to running 'merge' recursively against a set of "
                                         "directories.")
    sp_comb.set_defaults(funct=do_combine)

    # SUBCOMMAND:  splconf diff <CONF> <CONF>
    sp_diff = subparsers.add_parser("diff",
                                    help="Compares settings differences of two .conf files.  "
                                         "This command ignores textual differences (like order, "
                                         "spacing, and comments) and focuses strictly on comparing "
                                         "stanzas, keys, and values.  Note that spaces within any "
                                         "given value will be compared.")
    sp_diff.set_defaults(funct=do_diff)
    sp_diff.add_argument("conf1", metavar="FILE", help="Left side of the comparison")
    sp_diff.add_argument("conf2", metavar="FILE", help="Right side of the comparison")
    sp_diff.add_argument("-o", "--output", metavar="FILE",
                         type=argparse.FileType('w'), default=sys.stdout,
                         help="File where difference is stored.  Defaults to standard out.")
    sp_diff.add_argument("--comments", "-C",
                         action="store_true", default=False,
                         help="Enable comparison of comments.  (Unlikely to work consistently.")


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
            Skip/Keep:        Don't move content from
    
    
    sp_ptch.add_argument("--preview", action="store_true", default=False,
                         help="")
    sp_ptch.add_argument("--copy", action="store_true", default=False,
                         help="Copy settings from the source configuration file instead of "
                              "migrating the selected settings from the source to the target, "
                              "which is the default behavior if the target is a file rather than "
                              "standard out.")
    sp_ptch.add_argument("--keep-empty")
    """

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


    # SUBCOMMAND:  splconf minimize --target=<CONF> <CONF> [ <CONF-n> ... ]
    # Example workflow:
    #   1. cp default/props.conf local/props.conf
    #   2. vi local/props.conf (edit JUST the lines you want to change)
    #   3. splconf minimize --target=local/props.conf default/props.conf
    #  (You could take this a step further by appending "$SPLUNK_HOME/system/default/props.conf"
    # and removing any SHOULD_LINEMERGE = true entries (for example)
    sp_minz = subparsers.add_parser("minimize",
                                    help="Minimize the target file by removing entries duplicated "
                                         "in the default conf(s) provided.  ")


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

    # SUBCOMMAND:  splconf upgrade tarball
    sp_upgr = subparsers.add_parser("unarchive",
                                    help="Install or overwrite an existing app in a git-friendly "
                                         "way.  If the app already exist, steps will be taken to "
                                         "upgrade it in a sane way.")
    # Q:  Should this also work for fresh installs?
    sp_upgr.set_defaults(funct=do_unarchive)
    sp_upgr.add_argument("tarball", metavar="SPL",
                         help="The path to the archive to install.")
    sp_upgr.add_argument("--dest", metavar="DIR", default=".",
                         help="Set the destination path where the archive will be extracted.  "
                              "By default the current directory is used, but sane values include "
                              "etc/apps, etc/deployment-apps, and so on.  This could also be a "
                              "git repository working tree where splunk apps are stored.")
    sp_upgr.add_argument("--app-name", metavar="NAME", default=None,
                         help="The app name to use when expanding the archive.  By default, the "
                              "app name is taken from the archive as the top-level path included "
                              "in the archive (by convention)  Expanding archives that contain "
                              "multiple (ITSI) or nested apps (NIX, ES) is not supported.")
    sp_upgr.add_argument("--default-dir", default="default", metavar="DIR",
                         help="Name of the directory where the default contents will be stored.  "
                              "This is a useful feature for apps that use a dynamic default "
                              "directory that's created by the 'combine' mode.")
    sp_upgr.add_argument("--git-sanity-check",
                         choices=["all", "disable", "changes", "untracked"],
                         default="all",
                         help="By default a 'git status' is run on the destination folder to see "
                              "if the working tree has any modifications before the unarchive "
                              "process starts.  "
                              "(This check is automatically disabled if git is not in use or " 
                              "not installed.)")
    args = parser.parse_args()



    try:
        args.funct(args)
    except Exception, e:
        sys.stderr.write("Unhandled top-level exception.  {0}\n".format(e))
        raise
        sys.exit(99)




if __name__ == '__main__':
    cli()
