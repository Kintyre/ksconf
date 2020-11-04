from __future__ import absolute_import, unicode_literals

import datetime
import difflib
import os
from collections import namedtuple, defaultdict, Counter
from io import open

import ksconf.ext.six as six

from ksconf.conf.parser import GLOBAL_STANZA, _format_stanza, default_encoding
from ksconf.consts import EXIT_CODE_DIFF_EQUAL, EXIT_CODE_DIFF_CHANGE, EXIT_CODE_DIFF_NO_COMMON
from ksconf.util.compare import _cmp_sets
from ksconf.util.terminal import TermColor, ANSI_RESET, ANSI_GREEN, ANSI_RED, ANSI_YELLOW, ANSI_BOLD

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


class DiffHeader(object):
    def __init__(self, name, mtime=None):
        self.name = name
        if mtime:
            self.mtime = mtime
        else:
            self.detect_mtime()

    def detect_mtime(self):
        try:
            self.mtime = os.stat(self.name).st_mtime
        except OSError:
            self.mtime = 0

    def __str__(self):
        if isinstance(self.mtime, (int, float)):
            ts = datetime.datetime.fromtimestamp(self.mtime)
        else:
            ts = self.mtime
        return "{0:50} {1}".format(self.name, ts)


def compare_stanzas(a, b, stanza_name, preserve_empty=False):
    if preserve_empty:
        is_empty = lambda v: v is None
    else:
        is_empty = lambda v: not v

    if a == b:
        return [DiffOp(DIFF_OP_EQUAL, DiffStanza("stanza", stanza_name), a, b) ]
    elif is_empty(b):
        # A only
        return [ DiffOp(DIFF_OP_DELETE, DiffStanza("stanza", stanza_name), a, None) ]
    elif is_empty(a):
        # B only
        return [ DiffOp(DIFF_OP_INSERT, DiffStanza("stanza", stanza_name), None, b) ]
    else:
        return list(_compare_stanzas(a, b, stanza_name))


def _compare_stanzas(a, b, stanza_name):
    kv_a, kv_common, kv_b = _cmp_sets(list(a.keys()), list(b.keys()))

    if not kv_common:
        # No keys in common, just swap
        yield DiffOp(DIFF_OP_REPLACE, DiffStanza("stanza", stanza_name), a, b)
        return

    # Level 2 - Key comparisons
    for key in kv_a:
        yield DiffOp(DIFF_OP_DELETE, DiffStzKey("key", stanza_name, key), a[key], None)
    for key in kv_b:
        yield DiffOp(DIFF_OP_INSERT, DiffStzKey("key", stanza_name, key), None, b[key])
    for key in kv_common:
        a_ = a[key]
        b_ = b[key]
        if a_ == b_:
            yield DiffOp(DIFF_OP_EQUAL, DiffStzKey("key", stanza_name, key), a_, b_)
        else:
            yield DiffOp(DIFF_OP_REPLACE, DiffStzKey("key", stanza_name, key), a_, b_)


def compare_cfgs(a, b, allow_level0=True, preserve_empty=False):
    '''
    Return list of 5-tuples describing how to turn a into b.

    .. note:: The `Opcode` tags borrowed from :class:`SequenceMatcher` class in the :mod:`difflib`
              standard Python module.

    Each tuple takes the form:

        (tag, location, a, b)

    *tag:*

    =========   ============================================
    Value	    Meaning
    =========   ============================================
    'replace'	same element in both, but different values.
    'delete'	remove value b
    'insert'    insert value a
    'equal'	    same values in both
    =========   ============================================

    *location* is a tuple that can take the following forms:

    ===================  ===============================================================
    Tuple form           Description
    ===================  ===============================================================
    `(0)`                Global file level context (e.g., both files are the same)
    `(1, stanza)`        Stanzas are the same, or completely different (no shared keys)
    `(2, stanza, key)`   Key level, indicating
    ===================  ===============================================================


    Possible alternatives:

    https://dictdiffer.readthedocs.io/en/latest/#dictdiffer.patch

    '''

    delta = []

    # Level 0 - Compare entire file
    if allow_level0:
        stanza_a, stanza_common, stanza_b = _cmp_sets(list(a.keys()), list(b.keys()))
        if a == b:
            return [DiffOp(DIFF_OP_EQUAL, DiffGlobal("global"), a, b)]
        if not stanza_common:
            # Q:  Does this specific output make the consumer's job more difficult?
            # Nothing in common between these two files
            # Note:  Stanza renames are not detected and are out of scope.
            return [DiffOp(DIFF_OP_REPLACE, DiffGlobal("global"), a, b)]

    # Level 1 - Compare stanzas

    # Make sure GLOBAL stanza is output first
    all_stanzas = set(a.keys()).union(list(b.keys()))
    if GLOBAL_STANZA in all_stanzas:
        all_stanzas.remove(GLOBAL_STANZA)
        all_stanzas = [GLOBAL_STANZA] + list(all_stanzas)
    else:
        all_stanzas = list(all_stanzas)
    all_stanzas = sorted(all_stanzas)
    for stanza in all_stanzas:
        delta.extend(compare_stanzas(a.get(stanza), b.get(stanza), stanza, preserve_empty))
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


def is_equal(delta):
    """ Is the delta output show that the compared objects are identical """
    # type: (list(DiffOp)) -> bool
    return len(delta) == 1 and delta[0].tag == DIFF_OP_EQUAL


# Color mapping
_diff_color_mapping = {
    " ": ANSI_RESET,
    "+": ANSI_GREEN,
    "-": ANSI_RED,
}


def _show_diff_header(stream, files, diff_line=None):
    headers = []

    for f in files:
        if isinstance(f, DiffHeader):
            headers.append(f)
        else:
            headers.append(DiffHeader(f))

    with TermColor(stream) as tc:
        tc.color(ANSI_YELLOW, ANSI_BOLD)
        if diff_line:
            stream.write("diff {} {} {}\n".format(diff_line, headers[0].name, headers[1].name))
        tc.reset()
        stream.write("--- {0}\n".format(headers[0]))
        stream.write("+++ {0}\n".format(headers[1]))


def show_diff(stream, diffs, headers=None):
    tc = TermColor(stream)

    def is_multiline(v):
        if v and "\n" in v:
            return True
        else:
            return False

    def write_key(key, value, prefix_=" "):
        if is_multiline(value):
            write_multiline_key(key, value, prefix_)
        else:
            with tc:
                tc.color(_diff_color_mapping.get(prefix_))
                if key.startswith("#-"):
                    template = "{0}{2}\n"
                else:
                    template = "{0}{1} = {2}\n"
                stream.write(template.format(prefix_, key, value))

    def write_multiline_key(key, value, prefix_=" "):
        with tc:
            lines = value.replace("\n", "\\\n").split("\n")
            tc.color(_diff_color_mapping.get(prefix_))
            stream.write("{0}{1} = {2}\n".format(prefix_, key, lines.pop(0)))
            for line in lines:
                stream.write("{0}{1}\n".format(prefix_, line))

    def show_value(value, stanza_, key, prefix_=""):
        with tc:
            tc.color(_diff_color_mapping.get(prefix_))
            if isinstance(value, dict):
                if stanza_ is not GLOBAL_STANZA:
                    stream.write("{0}[{1}]\n".format(prefix_, stanza_))
                for x, y in sorted(six.iteritems(value)):
                    write_key(x, y, prefix_)
                stream.write("\n")
            else:
                write_key(key, value, prefix_)

    def show_multiline_diff(value_a, value_b, key):
        def f(v):
            r = "{0} = {1}".format(key, v)
            r = r.replace("\n", "\\\n")
            return r.splitlines()

        a = f(value_a)
        b = f(value_b)
        differ = difflib.Differ()
        with tc:
            for d in differ.compare(a, b):
                # Someday add "?" highlighting.  Trick is this should change color mid-line on the
                # previous (one or two) lines.  (Google and see if somebody else solved this one already)
                # https://stackoverflow.com/questions/774316/python-difflib-highlighting-differences-inline
                tc.color(_diff_color_mapping.get(d[0], 0))
                # Differences in how difflib returns bytes/unicode?
                if not isinstance(d, six.text_type):
                    d = d.decode(default_encoding)
                stream.write(d)
                tc.reset()
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
                show_value(op.a, op.location.stanza, None, "-")
            if op.tag in (DIFF_OP_INSERT, DIFF_OP_REPLACE):
                show_value(op.b, op.location.stanza, None, "+")
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
            show_value(op.b, op.location.stanza, op.location.key, "+")
        elif op.tag == DIFF_OP_DELETE:
            show_value(op.a, op.location.stanza, op.location.key, "-")
        elif op.tag == DIFF_OP_REPLACE:
            if is_multiline(op.a) or is_multiline(op.b):
                show_multiline_diff(op.a, op.b, op.location.key)
            else:
                show_value(op.a, op.location.stanza, op.location.key, "-")
                show_value(op.b, op.location.stanza, op.location.key, "+")
        elif op.tag == DIFF_OP_EQUAL:
            show_value(op.b, op.location.stanza, op.location.key, " ")
    stream.flush()
    return EXIT_CODE_DIFF_CHANGE


def show_text_diff(stream, a, b):
    _show_diff_header(stream, (a, b), "--text")
    differ = difflib.Differ()
    lines_a = open(a, "r", encoding=default_encoding).readlines()
    lines_b = open(b, "r", encoding=default_encoding).readlines()
    with TermColor(stream) as tc:
        for d in differ.compare(lines_a, lines_b):
            # Someday add "?" highlighting.  Trick is this should change color mid-line on the
            # previous (one or two) lines.  (Google and see if somebody else solved this one already)
            # https://stackoverflow.com/questions/774316/python-difflib-highlighting-differences-inline
            tc.color(_diff_color_mapping.get(d[0], 0))
            stream.write(d)
            tc.reset()

def reduce_stanza(stanza, keep_attrs):
    """ Pre-process a stanzas so that only a common set of keys will be compared.
    :param stanza: Stanzas containing attributes and values
    :type stanza: dict
    :param keep_attrs: Listing of
    :type keep_attrs: (list, set, tuple, dict)
    :return: a reduced copy of ``stanza``.
    """
    return {attr: value for attr, value in six.iteritems(stanza) if attr in keep_attrs}
