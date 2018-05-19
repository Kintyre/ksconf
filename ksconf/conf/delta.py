import datetime
import difflib
import os
from collections import namedtuple, defaultdict, Counter

from ksconf.conf.parser import GLOBAL_STANZA, _format_stanza
from ksconf.consts import EXIT_CODE_DIFF_EQUAL, EXIT_CODE_DIFF_CHANGE, EXIT_CODE_DIFF_NO_COMMON
from ksconf.util.compare import _cmp_sets
from ksconf.util.terminal import ANSI_RESET, ANSI_GREEN, ANSI_RED, tty_color, ANSI_YELLOW, ANSI_BOLD

####################################################################################################
## Diff logic

DIFF_OP_INSERT = "insert"
DIFF_OP_DELETE = "delete"
DIFF_OP_REPLACE = "replace"
DIFF_OP_EQUAL = "equal"

DiffOp = namedtuple("DiffOp", ("tag", "location", "a", "b"))
DiffGlobal = namedtuple("DiffGlobal", ("type",))
DiffStanza = namedtuple("DiffStanza", ("type", "stanza"))
DiffStzKey = namedtuple("DiffStzKey", ("type", "stanza", "key"))


def compare_cfgs(a, b, allow_level0=True):
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

    delta = []

    # Level 0 - Compare entire file
    if allow_level0:
        stanza_a, stanza_common, stanza_b = _cmp_sets(a.keys(), b.keys())
        if a == b:
            return [DiffOp(DIFF_OP_EQUAL, DiffGlobal("global"), a, b)]
        if not stanza_common:
            # Q:  Does this specific output make the consumer's job more difficult?
            # Nothing in common between these two files
            # Note:  Stanza renames are not detected and are out of scope.
            return [DiffOp(DIFF_OP_REPLACE, DiffGlobal("global"), a, b)]

    # Level 1 - Compare stanzas

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
                delta.append(DiffOp(DIFF_OP_EQUAL, DiffStanza("stanza", stanza), a_, b_))
                continue
            kv_a, kv_common, kv_b = _cmp_sets(a_.keys(), b_.keys())
            if not kv_common:
                # No keys in common, just swap
                delta.append(DiffOp(DIFF_OP_REPLACE, DiffStanza("stanza", stanza), a_, b_))
                continue

            # Level 2 - Key comparisons
            for key in kv_a:
                delta.append(DiffOp(DIFF_OP_DELETE, DiffStzKey("key", stanza, key), None, a_[key]))
            for key in kv_b:
                delta.append(DiffOp(DIFF_OP_INSERT, DiffStzKey("key", stanza, key), b_[key], None))
            for key in kv_common:
                a__ = a_[key]
                b__ = b_[key]
                if a__ == b__:
                    delta.append(DiffOp(DIFF_OP_EQUAL, DiffStzKey("key", stanza, key), a__, b__))
                else:
                    delta.append(DiffOp(DIFF_OP_REPLACE, DiffStzKey("key", stanza, key), a__, b__))
        elif stanza in a:
            # A only
            delta.append(DiffOp(DIFF_OP_DELETE, DiffStanza("stanza", stanza), None, a[stanza]))
        else:
            # B only
            delta.append(DiffOp(DIFF_OP_INSERT, DiffStanza("stanza", stanza), b[stanza], None))
    return delta


def summarize_cfg_diffs(delta, stream):
    """ Summarize a delta into a human readable format.   The input `delta` is in the format
    produced by the compare_cfgs() function.
    """
    stanza_stats = defaultdict(set)
    key_stats = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    c = Counter()
    for op in delta:
        c[op.tag] += 1
        if isinstance(op.location, DiffStanza):
            stanza_stats[op.tag].add(op.location.stanza)
        elif isinstance(op.location, DiffStzKey):
            key_stats[op.tag][op.location.stanza][op.location.key].add(op.location.key)

    for tag in sorted(c.keys()):
        stream.write("Have {0} '{1}' operations:\n".format(c[tag], tag))
        for entry in sorted(stanza_stats[tag]):
            stream.write("\t[{0}]\n".format(_format_stanza(entry)))
        for entry in sorted(key_stats[tag]):
            stream.write("\t[{0}]  {1} keys\n".format(_format_stanza(entry),
                                                      len(key_stats[tag][entry])))
        stream.write("\n")


# Color mapping
_diff_color_mapping = {
    " ": ANSI_RESET,
    "+": ANSI_GREEN,
    "-": ANSI_RED,
}


def _show_diff_header(stream, files, diff_line=None):
    def header(sign, filename):
        try:
            mtime = os.stat(filename).st_mtime
        except OSError:
            mtime = 0
        ts = datetime.datetime.fromtimestamp(mtime)
        stream.write("{0} {1:50} {2}\n".format(sign * 3, filename, ts))
        tty_color(stream, ANSI_RESET)

    tty_color(stream, ANSI_YELLOW, ANSI_BOLD)
    if diff_line:
        stream.write("diff {} {} {}\n".format(diff_line, files[0], files[1]))
    tty_color(stream, ANSI_RESET)
    header("-", files[0])
    header("+", files[1])


def show_diff(stream, diffs, headers=None):
    def write_key(key, value, prefix_=" "):
        if "\n" in value:
            write_multiline_key(key, value, prefix_)
        else:
            if key.startswith("#-"):
                template = "{0}{2}\n"
            else:
                template = "{0}{1} = {2}\n"
            stream.write(template.format(prefix_, key, value))

    def write_multiline_key(key, value, prefix_=" "):
        lines = value.replace("\n", "\\\n").split("\n")
        tty_color(stream, _diff_color_mapping.get(prefix_))
        stream.write("{0}{1} = {2}\n".format(prefix_, key, lines.pop(0)))
        for line in lines:
            stream.write("{0}{1}\n".format(prefix_, line))
        tty_color(stream, ANSI_RESET)

    def show_value(value, stanza_, key, prefix_=""):
        tty_color(stream, _diff_color_mapping.get(prefix_))
        if isinstance(value, dict):
            if stanza_ is not GLOBAL_STANZA:
                stream.write("{0}[{1}]\n".format(prefix_, stanza_))
            for x, y in sorted(value.iteritems()):
                write_key(x, y, prefix_)
            stream.write("\n")
        else:
            write_key(key, value, prefix_)
        tty_color(stream, ANSI_RESET)

    def show_multiline_diff(value_a, value_b, key):
        def f(v):
            r = "{0} = {1}".format(key, v)
            r = r.replace("\n", "\\\n")
            return r.splitlines()

        a = f(value_a)
        b = f(value_b)
        differ = difflib.Differ()
        for d in differ.compare(a, b):
            # Someday add "?" highlighting.  Trick is this should change color mid-line on the
            # previous (one or two) lines.  (Google and see if somebody else solved this one already)
            # https://stackoverflow.com/questions/774316/python-difflib-highlighting-differences-inline
            tty_color(stream, _diff_color_mapping.get(d[0], 0))
            stream.write(d)
            tty_color(stream, ANSI_RESET)
            stream.write("\n")

    # Global result:  no changes between files or no commonality between files
    if len(diffs) == 1 and isinstance(diffs[0].location, DiffGlobal):
        op = diffs[0]
        if op.tag == DIFF_OP_EQUAL:
            return EXIT_CODE_DIFF_EQUAL
        else:
            if headers:
                _show_diff_header(stream, headers, "--ksconf -global")
            # This is the only place where a gets '-' and b gets '+'
            for (prefix, data) in [("-", op.a), ("+", op.b)]:
                for (stanza, keys) in sorted(data.items()):
                    show_value(keys, stanza, None, prefix)
            stream.flush()
            return EXIT_CODE_DIFF_NO_COMMON

    if headers:
        _show_diff_header(stream, headers, "--ksconf")

    last_stanza = None
    for op in diffs:
        if isinstance(op.location, DiffStanza):
            if op.tag in (DIFF_OP_DELETE, DIFF_OP_REPLACE):
                show_value(op.b, op.location.stanza, None, "-")
            if op.tag in (DIFF_OP_INSERT, DIFF_OP_REPLACE):
                show_value(op.a, op.location.stanza, None, "+")
            continue  # pragma: no cover  (peephole optimization)

        if op.location.stanza != last_stanza:
            if last_stanza is not None:
                # Line break after last stanza
                stream.write("\n")
                stream.flush()
            if op.location.stanza is not GLOBAL_STANZA:
                stream.write(" [{0}]\n".format(op.location.stanza))
            last_stanza = op.location.stanza

        if op.tag == DIFF_OP_INSERT:
            show_value(op.a, op.location.stanza, op.location.key, "+")
        elif op.tag == DIFF_OP_DELETE:
            show_value(op.b, op.location.stanza, op.location.key, "-")
        elif op.tag == DIFF_OP_REPLACE:
            if "\n" in op.a or "\n" in op.b:
                show_multiline_diff(op.a, op.b, op.location.key)
            else:
                show_value(op.b, op.location.stanza, op.location.key, "-")
                show_value(op.a, op.location.stanza, op.location.key, "+")
        elif op.tag == DIFF_OP_EQUAL:
            show_value(op.b, op.location.stanza, op.location.key, " ")
    stream.flush()
    return EXIT_CODE_DIFF_CHANGE


def show_text_diff(stream, a, b):
    _show_diff_header(stream, (a, b), "--text")
    differ = difflib.Differ()
    lines_a = open(a, "rb").readlines()
    lines_b = open(b, "rb").readlines()
    for d in differ.compare(lines_a, lines_b):
        # Someday add "?" highlighting.  Trick is this should change color mid-line on the
        # previous (one or two) lines.  (Google and see if somebody else solved this one already)
        # https://stackoverflow.com/questions/774316/python-difflib-highlighting-differences-inline
        tty_color(stream, _diff_color_mapping.get(d[0], 0))
        stream.write(d)
        tty_color(stream, ANSI_RESET)
