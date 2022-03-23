import datetime
import difflib
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
from io import open
from os import PathLike
from typing import List, NamedTuple, Sequence, TextIO, Union

from ksconf.conf.parser import GLOBAL_STANZA, ConfType, StanzaType, _format_stanza, default_encoding
from ksconf.consts import EXIT_CODE_DIFF_CHANGE, EXIT_CODE_DIFF_EQUAL, EXIT_CODE_DIFF_NO_COMMON
from ksconf.util.compare import _cmp_sets
from ksconf.util.terminal import ANSI_BOLD, ANSI_GREEN, ANSI_RED, ANSI_RESET, ANSI_YELLOW, TermColor

####################################################################################################
# DiffVerb logic


class DiffVerb(Enum):
    INSERT = "insert"
    DELETE = "delete"
    REPLACE = "replace"
    EQUAL = "equal"

    # Allow sorting
    def __gt__(self, other):
        return self.value > other.value

    def __lt__(self, other):
        return self.value < other.value


# Legacy names
DIFF_OP_INSERT = DiffVerb.INSERT
DIFF_OP_DELETE = DiffVerb.DELETE
DIFF_OP_REPLACE = DiffVerb.REPLACE
DIFF_OP_EQUAL = DiffVerb.EQUAL


'''
from typing import NamedTuple
DiffOp = NamedTuple("DiffOp", (["tag", DiffVerb], ["location", Union[DiffGlobal, DiffStanza, DiffStzKey]], ["a", Union[ConfType, StanzaType, str]], ["b", Union[ConfType, StanzaType, str]]))
DiffGlobal = NamedTuple("DiffGlobal", (["type", str],))
DiffStanza = NamedTuple("DiffStanza", (["type", str], ["stanza", str]))
DiffStzKey = NamedTuple("DiffStzKey", (["type", str], ["stanza", str], ["key", str]))
'''


class DiffLevel(Enum):
    GLOBAL = "global"
    STANZA = "stanza"
    KEY = "key"


class DiffGlobal(NamedTuple):
    type: DiffLevel


class DiffStanza(NamedTuple):
    type: DiffLevel
    stanza: str


class DiffStzKey(NamedTuple):
    type: DiffLevel
    stanza: str
    key: str


class DiffOp(NamedTuple):
    tag: DiffVerb
    location: Union[DiffGlobal, DiffStanza, DiffStzKey]
    a: Union[ConfType, StanzaType, str, None]
    b: Union[ConfType, StanzaType, str, None]


@dataclass
class DiffHeader:
    name: str
    mtime: float = None

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


def compare_stanzas(a: StanzaType, b: StanzaType,
                    stanza_name: str,
                    replace_level: DiffLevel = DiffLevel.GLOBAL
                    ) -> List[DiffOp]:
    """
    :param replace_level: If a and b have no common keys, is a single stanza-level
                      'replace' is issue unless ``replace_level="key"``
    :type replace_level: bool
    """
    if a == b:
        return [DiffOp(DiffVerb.EQUAL, DiffStanza(DiffLevel.STANZA, stanza_name), a, b)]
    elif b is None:
        # A only
        return [DiffOp(DiffVerb.DELETE, DiffStanza(DiffLevel.STANZA, stanza_name), a, None)]
    elif a is None:
        # B only
        return [DiffOp(DiffVerb.INSERT, DiffStanza(DiffLevel.STANZA, stanza_name), None, b)]
    else:
        return list(_compare_stanzas(a, b, stanza_name, replace_level))


def _compare_stanzas(a: StanzaType, b: StanzaType,
                     stanza_name: str,
                     replace_level: DiffLevel) -> List[DiffOp]:
    kv_a, kv_common, kv_b = _cmp_sets(list(a.keys()), list(b.keys()))

    if replace_level in (DiffLevel.GLOBAL, DiffLevel.STANZA) and not kv_common:
        # No keys in common, just swap
        yield DiffOp(DiffVerb.REPLACE, DiffStanza(DiffLevel.STANZA, stanza_name), a, b)
        return

    # Level 2 - Key comparisons
    for key in kv_a:
        yield DiffOp(DIFF_OP_DELETE, DiffStzKey(DiffLevel.KEY, stanza_name, key), a[key], None)
    for key in kv_b:
        yield DiffOp(DIFF_OP_INSERT, DiffStzKey(DiffLevel.KEY, stanza_name, key), None, b[key])
    for key in kv_common:
        a_ = a[key]
        b_ = b[key]
        if a_ == b_:
            yield DiffOp(DiffVerb.EQUAL, DiffStzKey(DiffLevel.KEY, stanza_name, key), a_, b_)
        else:
            yield DiffOp(DiffVerb.REPLACE, DiffStzKey(DiffLevel.KEY, stanza_name, key), a_, b_)


def compare_cfgs(a: ConfType, b: ConfType,
                 replace_level: DiffLevel = DiffLevel.GLOBAL
                 ) -> List[DiffOp]:
    """
    Calculate a set of deltas which describes how to transform a into b.

    :param a: the first/original configuration entity
    :type a: dict
    :param b: the second/target configuration entity
    :type b: dict
    :param replace_level: The highest level 'replace' event that can be returned.
        Acceptable values are ``global``, ``stanza``, and ``key``.
        These examples may help:

            *   Using 'global' with identical inputs will report a single global-level equal op.
            *   Using 'stanza' with identical inputs will return all stanzas as equal.
            *   Using 'key' will ensure that two stanzas with no common keys will be reported in
                terms of key changes.  Whereas 'global' or 'stanza' would result in a single giant replace op.

    :type replace_level: str: ``global``, ``stanza``, or ``key``
    :return: a sequence of differences in tuples
    :rtype: [DiffOp]

    .. note:: The :py:class:`DiffOp` output idea was borrowed from
              :class:`SequenceMatcher` class in the :mod:`difflib`
              in the standard Python module.

    This function returns a sequence of 5 element tuples describing the
    transformation based on the detail level specified in `replace_level`.

    Each :py:class:`DiffOp` (named tuple) takes the form:

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

    *location* is a namedtuple that can take the following forms:

    ====================== ========== ==============================================================
    Tuple form             Type       Description
    ====================== ========== ==============================================================
    `("global")`           DiffGlobal Global file level context (e.g., both files are the same)
    `("stanza", stanza)`   DiffStanza Stanzas are the same, or completely different (no shared keys)
    `("key", stanza, key)` DiffStzKey Key level change
    ====================== ========== ==============================================================

    .. versionchanged:: v0.8.8
        The ``preserve_empty`` argument was origionally introduced to preserve backwards
        compatibility, but it ended up introducing new bugs.
        Additionally, no use cases were found where better to automatically discarding empty stanzas.

    .. versionchanged:: v0.8.8
        The ``allow_level0`` argument was replaced with ``replace_level``.
        Instead of using ``allow_level0=False`` use ``replace_level="stanza"``.
        At the same time a new feature was added to support ``replace_level="key"``.
        The default behavior remains the same.

    """
    # Possible alternatives:
    # https://dictdiffer.readthedocs.io/en/latest/#dictdiffer.patch

    if replace_level not in (DiffLevel.GLOBAL, DiffLevel.STANZA, DiffLevel.KEY):
        if isinstance(replace_level, str):
            replace_level = DiffLevel(replace_level)
        else:
            raise TypeError(f"Invalid value '{replace_level}' given for "
                            f"replace_level.  Choose 'global', 'stanza', or 'key'")

    delta = []

    # Level 0 - Compare entire file
    if replace_level == DiffLevel.GLOBAL:
        stanza_a, stanza_common, stanza_b = _cmp_sets(list(a.keys()), list(b.keys()))
        if a == b:
            return [DiffOp(DiffVerb.EQUAL, DiffGlobal(DiffLevel.GLOBAL), a, b)]
        if not stanza_common:
            # Q:  Does this specific output make the consumer's job more difficult?
            # Nothing in common between these two files
            # Note:  Stanza renames are not detected and are out of scope.
            return [DiffOp(DiffVerb.REPLACE, DiffGlobal(DiffLevel.GLOBAL), a, b)]

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
        delta.extend(compare_stanzas(a.get(stanza), b.get(stanza), stanza, replace_level))
    return delta


def summarize_cfg_diffs(delta: List[DiffOp], stream: TextIO):
    """ Summarize a delta into a human-readable format.   The input `delta` is in the format
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


def is_equal(delta: List[DiffOp]) -> bool:
    """ Is the delta output show that the compared objects are identical """
    return len(delta) == 1 and delta[0].tag == DiffVerb.EQUAL


# Color mapping
_diff_color_mapping = {
    " ": ANSI_RESET,
    "+": ANSI_GREEN,
    "-": ANSI_RED,
}


def _show_diff_header(stream: TextIO,
                      files: List[Union[DiffHeader, str]],
                      diff_line: Union[str, None] = None):
    headers = []

    for f in files:
        if isinstance(f, DiffHeader):
            headers.append(f)
        else:
            headers.append(DiffHeader(f))

    with TermColor(stream) as tc:
        tc.color(ANSI_YELLOW, ANSI_BOLD)
        if diff_line:
            stream.write(f"diff {diff_line} {headers[0].name} {headers[1].name}\n")
        tc.reset()
        stream.write(f"--- {headers[0]}\n")
        stream.write(f"+++ {headers[1]}\n")


def show_diff(stream: TextIO, diffs: List[DiffOp], headers=None) -> int:
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
                    line = value
                else:
                    line = f"{key} = {value}"
                stream.write(f"{prefix_}{line}\n")

    def write_multiline_key(key, value, prefix_=" "):
        with tc:
            lines = value.replace("\n", "\\\n").split("\n")
            tc.color(_diff_color_mapping.get(prefix_))
            stream.write(f"{prefix_}{key} = {lines.pop(0)}\n")
            for line in lines:
                stream.write(f"{prefix_}{line}\n")

    def show_value(value, stanza_, key, prefix_=""):
        with tc:
            tc.color(_diff_color_mapping.get(prefix_))
            if isinstance(value, dict):
                if stanza_ is not GLOBAL_STANZA:
                    stream.write(f"{prefix_}[{stanza_}]\n")
                for x, y in sorted(value.items()):
                    write_key(x, y, prefix_)
            else:
                write_key(key, value, prefix_)

    def show_multiline_diff(value_a, value_b, key):
        def f(v):
            r = f"{key} = {v}"
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
                ''' # Attempt to keep this disabled for Python 3
                # Differences in how difflib returns bytes/unicode?
                if isinstance(d, bytes):
                    d = d.decode(default_encoding)
                '''
                stream.write(d)
                tc.reset()
                stream.write("\n")

    # Global result:  no changes between files or no commonality between files
    if len(diffs) == 1 and isinstance(diffs[0].location, DiffGlobal):
        op = diffs[0]
        if op.tag == DiffVerb.EQUAL:
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
        if op.location.stanza != last_stanza:
            if last_stanza is not None:
                # Line break after last stanza
                stream.write("\n")
                stream.flush()
            if op.location.stanza is not GLOBAL_STANZA and not isinstance(op.location, DiffStanza):
                stream.write(f" [{op.location.stanza}]\n")
            last_stanza = op.location.stanza

        if isinstance(op.location, DiffStanza):
            if op.tag in (DIFF_OP_DELETE, DIFF_OP_REPLACE):
                show_value(op.a, op.location.stanza, None, "-")
            if op.tag in (DIFF_OP_INSERT, DIFF_OP_REPLACE):
                show_value(op.b, op.location.stanza, None, "+")
            continue

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


def show_text_diff(stream: TextIO, a: PathLike, b: PathLike):
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


def reduce_stanza(stanza: StanzaType, keep_attrs: Sequence) -> dict:
    """ Pre-process a stanzas so that only a common set of keys will be compared.

    :param stanza: Stanzas containing attributes and values
    :type stanza: dict
    :param keep_attrs: Listing of attributes to preserve
    :type keep_attrs: (list, set, tuple, dict)
    :return: a reduced copy of ``stanza``.
    """
    return {attr: value for attr, value in stanza.items() if attr in keep_attrs}


def write_diff_as_json(delta: List[DiffOp], stream, **dump_args):
    # XXX: Eventually support reversing this to import a json "patch"; and add an apply/reverse command.
    import json
    import sys

    from ksconf import __vcs_info__, __version__
    record = {
        "schema_version": 1,
        "software": {
            "name": "ksconf",
            "version": [__version__, __vcs_info__],
            "command": sys.argv,
            "cwd": os.getcwd(),
        }
    }
    record["records"] = [diff_obj_json_format(op) for op in delta]
    json.dump(record, stream, **dump_args)


def diff_obj_json_format(o):
    # Q: PY3 move.  Do any of the new fancy classes above help with this? (dataclass/NamedTuple)
    if isinstance(o, DiffOp):
        o = {
            "tag": o.tag,
            "location": diff_obj_json_format(o.location),
            "a": o.a,
            "b": o.b,
        }
    elif isinstance(o, DiffGlobal):
        o = {"type": o.type}
    elif isinstance(o, DiffStanza):
        o = {"type": o.type, "stanza": o.stanza}
    elif isinstance(o, DiffStzKey):
        o = {"type": o.type, "stanza": o.stanza, "key": o.key}
    return o
