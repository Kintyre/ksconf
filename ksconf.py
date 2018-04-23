#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PYTHON_ARGCOMPLETE_OK
"""ksconf - Kintyre Splunk CONFig tool


kast - Kintyre's Awesome Splunk Tool

splconf - SPLunk CONFig tool

kscfg - Kintyre Splunk ConFiG tool

ksc - Kintyre Splunk Config tool


Design goals:

 * Multi-purpose go-to .conf tool.
 * Dependability
 * Simplicity
 * No eternal dependencies (single source file, if possible; or packable as single file.)
 * Stable CLI
 * Good scripting interface for deployment scripts and/or git hooks



-------------------------------------------------

Git configuration tweaks


Setup ksconf as an external difftool provider:

    ~/.gitconfig:

        [difftool "ksconf"]
            cmd = "ksconf --force-color diff \"$LOCAL\" \"$REMOTE\" | less -R"
        [difftool]
            prompt = false
        [alias]
            ksdiff = "difftool --tool=ksconf"

    Now can run:  git ksdiff props.conf
    Test command: git config diff.conf.xfuncname



Make normal diffs show the 'stanza' on the @@ output lines

    ~/.gitconfig

        [diff "conf"]
            xfuncname = "^(\\[.*\\])$"

    attributes:
        *.conf diff=conf
        *.meta diff=conf

    Test command:

    git check-attr -a -- *.conf

"""



import os
import re
import sys
import difflib
import shutil
import datetime
from collections import namedtuple, defaultdict, Counter
from copy import deepcopy
from glob import glob
from StringIO import StringIO
from subprocess import list2cmdline


# EXIT_CODE_* constants:  Use consistent exit codes for scriptability
#
#   0-9    Normal/successful conditions
#   20-49  Error conditions (user caused)
#   50-59  Externally caused (should retry)
#   100+   Internal error (developer required)

# Success codes (no need to retry)
EXIT_CODE_SUCCESS = 0
EXIT_CODE_NOTHING_TO_DO = 1
EXIT_CODE_USER_QUIT = 2
EXIT_CODE_NO_SUCH_FILE = 5
EXIT_CODE_MISSING_ARG = 6

EXIT_CODE_DIFF_EQUAL = 0
EXIT_CODE_DIFF_CHANGE = 3
EXIT_CODE_DIFF_NO_COMMON = 4
EXIT_CODE_SORT_APPLIED = 9

# Errors caused by users
EXIT_CODE_BAD_CONF_FILE = 20
EXIT_CODE_FAILED_SAFETY_CHECK = 22
EXIT_CODE_COMBINE_MARKER_MISSING = 30

# Errors caused by GIT interactions
EXIT_CODE_GIT_FAILURE = 40

# Retry or temporary failure
EXIT_CODE_EXTERNAL_FILE_EDIT = 50

# Unresolvable issues (developer required)
EXIT_CODE_INTERNAL_ERROR = 100


class Token(object):
    """ Immutable token object.  deepcopy returns the same object """
    def __deepcopy__(self, memo):
        memo[id(self)] = self
        return self

GLOBAL_STANZA = Token()

DUP_OVERWRITE = "overwrite"
DUP_EXCEPTION = "exception"
DUP_MERGE = "merge"



CONTROLLED_DIR_MARKER = ".ksconf_controlled"



SMART_CREATE = "created"
SMART_UPDATE = "updated"
SMART_NOCHANGE = "unchanged"



####################################################################################################
## Core parsing / conf file writing logic

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
    comment = 0
    for entry in lines:
        if comments_re.search(entry):
            if keep_comments:
                comment += 1
                yield ("#-%06d" % comment, entry)
            continue
        if "=" in entry:
            k, v = entry.split("=", 1)
            yield k.rstrip(), v.lstrip()
            continue
        if strict and entry.strip():
            raise ConfParserException("Unexpected entry:  {0}".format(entry))


# Parsing configuration profiles
PARSECONF_STRICT = dict(
    keep_comments=True,
    dup_stanza=DUP_EXCEPTION,
    dup_key=DUP_EXCEPTION,
    strict=True)

PARSECONF_STRICT_NC = dict(
    keep_comments=False,        # No comment
    dup_stanza=DUP_EXCEPTION,
    dup_key=DUP_EXCEPTION,
    strict=True)

PARSECONF_MID = dict(
    keep_comments=True,
    dup_stanza=DUP_EXCEPTION,
    dup_key=DUP_OVERWRITE,
    strict=True)

PARSECONF_MID_NC = dict(
    keep_comments=False,         # No comments
    dup_stanza=DUP_EXCEPTION,
    dup_key=DUP_OVERWRITE,
    strict=True)

PARSECONF_LOOSE = dict(
    keep_comments=False,
    dup_stanza=DUP_MERGE,
    dup_key=DUP_MERGE,
    strict=False)



def parse_conf(stream, profile=PARSECONF_MID):
    # Placeholder stub for an eventual migration to proper class-oriented parser
    return _parse_conf(stream, **profile)

def _parse_conf(stream, keys_lower=False, handle_conts=True, keep_comments=False,
               dup_stanza=DUP_EXCEPTION, dup_key=DUP_OVERWRITE, strict=False):
    if not hasattr(stream, "read"):
        # Assume it's a filename
        stream = open(stream)
    if hasattr(stream, "name"):
        stream_name = stream.name
    else:
        stream_name = repr(stream)

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
                                                                 stream_name))
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
                                                             key, stream_name))
            else:
                local_stanza[key] = value
                s[key] = value
    return sections


def write_conf(stream, conf, stanza_delim="\n", sort=True):
    if not hasattr(stream, "write"):
        # Assume it's a filename
        stream = open(stream, "w")
    conf = dict(conf)

    if sort:
        sorter = sorted
    else:
        sorter = iter

    def write_stanza_body(items):
        for (key, value) in sorter(items.iteritems()):
            if key.startswith("#"):
                stream.write("{0}\n".format(value))
            elif value:
                stream.write("{0} = {1}\n".format(key, value.replace("\n", "\\\n")))
            else:
                # Avoid a trailing whitespace to keep the git gods happy
                stream.write("{0} =\n".format(key))

    keys = sorter(conf)
    # Global MUST be written first
    if GLOBAL_STANZA in keys:
        keys.remove(GLOBAL_STANZA)
        write_stanza_body(conf[GLOBAL_STANZA])
        if keys:
            stream.write(stanza_delim)
    while keys:
        section = keys.pop(0)
        cfg = conf[section]
        stream.write("[{0}]\n".format(section))
        write_stanza_body(cfg)
        if keys:
            stream.write(stanza_delim)


def smart_write_conf(filename, conf, stanza_delim="\n", sort=True, temp_suffix=".tmp"):
    if os.path.isfile(filename):
        temp = StringIO()
        write_conf(temp, conf, stanza_delim, sort)
        with open(filename, "rb") as dest:
            file_diff = fileobj_compare(temp, dest)
        if file_diff:
            return SMART_NOCHANGE
        else:
            tempfile = filename + temp_suffix
            with open(tempfile, "w") as dest:
                dest.write(temp.getvalue())
            os.unlink(filename)
            os.rename(tempfile, filename)
            return SMART_UPDATE
    else:
        tempfile = filename + temp_suffix
        with open(tempfile, "w") as dest:
            write_conf(dest, conf, stanza_delim, sort)
        os.rename(tempfile, filename)
        return SMART_CREATE



####################################################################################################
## Merging logic

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
            # Rip all the comments out of the new_layer, and prepend them (sequentially) to base
            comments = _extract_comments(items)
            if comments:
                inject_section_comments(base[section], prepend=comments)
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


def _extract_comments(section):
    "Return a sequental list of comments REMOVED from a section dictionary"
    comments = []
    for key, value in sorted(section.items()):
        if key.startswith("#-"):
            comments.append(value)
            del section[key]
    return comments


def inject_section_comments(section, prepend=None, append=None):
    # Extract existing comments from section dict (in order; and remove them)
    # Add in any prepend/append comments (if that comment isn't already present)
    # Re-inject comments back into the section dict with fresh numbering
    #
    # Yes, this is really hacky, but the only way to make the diffs work correctly ;-(
    comments = _extract_comments(section)
    new_comments = []
    if prepend:
        for c in prepend:
            if c not in comments:
                new_comments.append(c)
    new_comments.extend(comments)
    if append:
        for c in append:
            if c not in comments:
                new_comments.append(c)
    for (i, comment) in enumerate(new_comments, 1):
        section["#-%06d" % i] = comment


def merge_conf_files(dest, configs, dry_run=False, banner_comment=None):
    # Parse all config files
    cfgs = [conf.data for conf in configs]
    # Merge all config files:
    merged_cfg = merge_conf_dicts(*cfgs)
    if banner_comment:
        if not banner_comment.startswith("#"):
            banner_comment = "#" + banner_comment
        inject_section_comments(merged_cfg.setdefault(GLOBAL_STANZA, {}), prepend=[banner_comment])

    # Either show the diff (dry-run mode) or write to the destination file
    if dry_run and dest.is_file():
        if os.path.isfile(dest.name):
            dest_cfg = dest.data
        else:
            dest_cfg = {}
        show_diff(sys.stdout, compare_cfgs(dest_cfg, merged_cfg),
                  headers=(dest.name, dest.name + "-new"))
        return
    return dest.dump(merged_cfg)



####################################################################################################
## Diff logic

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

    for tag in sorted(c.keys()): # (DIFF_OP_EQUAL, DIFF_OP_REPLACE, DIFF_OP_INSERT, DIFF_OP_DELETE):
        stream.write("Have {0} '{1}' operations:\n".format(c[tag], tag))
        for entry in sorted(stanza_stats[tag]):
            stream.write("\t[{0}]\n".format(_format_stanza(entry)))
        for entry in sorted(key_stats[tag]):
            stream.write("\t[{0}]  {1} keys\n".format(_format_stanza(entry),
                                                      len(key_stats[tag][entry])))
        stream.write("\n")


def fileobj_compare(f1, f2):
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


def file_compare(fn1, fn2):
    with open(fn1, "rb") as f1,\
         open(fn2, "rb") as f2:
        return fileobj_compare(f1, f2)


def _is_binary_file(filename, peek=2048):
    # https://stackoverflow.com/a/7392391/315892; modified for Python 2.6 compatibility
    textchars = bytearray(set([7, 8, 9, 10, 12, 13, 27]) | set(range(0x20, 0x100)) - set([0x7f]))
    with open(filename, "rb") as f:
        b = f.read(peek)
        return bool(b.translate(None, textchars))


_dir_exists_cache = set()
def dir_exists(directory):
    """ Ensure that the directory exists """
    # This works as long as we never call os.chdir()
    if directory in _dir_exists_cache:
        return
    if not os.path.isdir(directory):
        os.makedirs(directory)
    _dir_exists_cache.add(directory)


def smart_copy(src, dest):
    """ Copy (overwrite) file only if the contents have changed. """
    ret = SMART_CREATE
    if os.path.isfile(dest):
        if file_compare(src, dest):
            # Files already match.  Nothing to do.
            return SMART_NOCHANGE
        else:
            ret = SMART_UPDATE
            os.unlink(dest)
    shutil.copy2(src, dest)
    return ret


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


def file_fingerprint(path, compare_to=None):
    stat = os.stat(path)
    fp = (stat.st_mtime, stat.st_size)
    if compare_to:
        return fp != compare_to
    else:
        return fp

def _expand_glob_list(iterable):
    for item in iterable:
        if "*" in item or "?" in item:
            for match in glob(item):
                yield match
        else:
            yield item


_glob_to_regex = {
    r"\*":   r"[^/\\]*",
    r"\?":   r".",
    r"\.\.\.": r".*",
}
_is_glob_re = re.compile("({})".format("|".join(_glob_to_regex.keys())))

def match_bwlist(value, bwlist, escape=True):
    # Return direct matches first  (most efficient)
    if value in bwlist:
        return True
    # Now see if anything in the bwlist contains a glob pattern
    for pattern in bwlist:
        if _is_glob_re.search(pattern):
            # Escape all characters.  And then replace the escaped "*" with a ".*"
            if escape:
                regex = re.escape(pattern)
            else:
                regex = pattern
            for (find, replace) in _glob_to_regex.items():
                regex = regex.replace(find, replace)
            if re.match(regex, value):
                return True
    return False

def relwalk(top, topdown=True, onerror=None, followlinks=False):
    """ Relative path walker
    Like os.walk() except that it doesn't include the "top" prefix in the resulting 'dirpath'.
    """
    if not top.endswith(os.path.sep):
        top += os.path.sep
    prefix = len(top)
    for (dirpath, dirnames, filenames) in os.walk(top, topdown, onerror, followlinks):
        dirpath = dirpath[prefix:]
        yield (dirpath, dirnames, filenames)


GenArchFile = namedtuple("GenericArchiveEntry", ("path", "mode", "size", "payload"))

def extract_archive(archive_name, extract_filter=None):
    if extract_filter is not None and not callable(extract_filter):
        raise ValueError("extract_filter must be a callable!")
    if archive_name.lower().endswith(".zip"):
        return _extract_zip(archive_name, extract_filter)
    else:
        return _extract_tar(archive_name, extract_filter)

def gaf_filter_name_like(pattern):
    from fnmatch import fnmatch
    def filter(gaf):
        filename = os.path.basename(gaf.path)
        return fnmatch(filename, pattern)
    return filter


def _extract_tar(path, extract_filter=None):
    import tarfile
    with tarfile.open(path, "r") as tar:
        for ti in tar:
            if not ti.isreg():
                '''
                print "Skipping {}  ({})".format(ti.name, ti.type)
                '''
                continue
            mode = ti.mode & 0777
            if extract_filter is None or \
               extract_filter(GenArchFile(ti.name, mode, ti.size, None)):
                tar_file_fp = tar.extractfile(ti)
                buf = tar_file_fp.read()
            else:
                buf = None
            yield GenArchFile(ti.name, mode, ti.size, buf)


def file_hash(path, algorithm="sha256"):
    import hashlib
    h = hashlib.new(algorithm)
    with open(path, "rb") as fp:
        buf = fp.read(4096)
        while buf:
            h.update(buf)
            buf = fp.read(4096)
    return h.hexdigest()


def _extract_zip(path, extract_filter=None, mode=0644):
    import zipfile
    with zipfile.ZipFile(path, mode="r") as zipf:
        for zi in zipf.infolist():
            if zi.filename.endswith('/'):
                # Skip directories
                continue
            if extract_filter is None or \
               extract_filter(GenArchFile(zi.filename, mode, zi.file_size, None)):
                payload = zipf.read(zi)
            else:
                payload = None
            yield GenArchFile(zi.filename, mode, zi.file_size, payload)

def sanity_checker(iter):
    for gaf in iter:
        if gaf.path.startswith("/") or ".." in gaf.path:
            raise ValueError("Bad path found in archive:  {}".format(gaf.path))
        yield gaf


# This gets properly supported in Python 3.6, but until then....
RegexType = type(re.compile(r'.'))

def gen_arch_file_remapper(iter, mapping):
    # Mapping is assumed to be a sequence of (find,replace) strings (may eventually support re.sub?)
    for gaf in iter:
        path = gaf.path
        for (find, replace) in mapping:
            if isinstance(find, RegexType):
                path = find.sub(replace, path)
            else:
                path = path.replace(find, replace)
        if gaf.path == path:
            yield gaf
        else:
            yield GenArchFile(path, gaf.mode, gaf.size, gaf.payload)


GIT_BIN = "git"
GitCmdOutput = namedtuple("GitCmdOutput", ["cmd", "returncode", "stdout", "stderr", "lines"])


def git_cmd(args, shell=False, cwd=None, combine_std=False, capture_std=True):
    if combine_std:
        # Should return "lines" instead of stderr/stdout streams
        raise NotImplementedError
    from subprocess import Popen, PIPE
    cmdline_args = [ GIT_BIN ] + args
    if capture_std:
        out = PIPE
    else:
        out = None
    proc = Popen(cmdline_args, stdout=out, stderr=out, shell=shell, cwd=cwd)
    (stdout, stderr) = proc.communicate()
    return GitCmdOutput(cmdline_args, proc.returncode, stdout, stderr, None)

def _xargs(iterable, cmd_len=1024):
    fn_len = 0
    buf = []
    iterable = list(iterable)
    while iterable:
        s = iterable.pop(0)
        l = len(s) + 1
        if fn_len +l >= cmd_len:
            yield buf
            buf = []
            fn_len = 0
        buf.append(s)
        fn_len += l
    if buf:
        yield buf

def git_cmd_iterable(args, iterable, cwd=None, cmd_len=1024):
    base_len = sum([len(s)+1 for s in args])
    for chunk in _xargs(iterable, cmd_len-base_len):
        p = git_cmd(args + chunk, cwd=cwd)
        if p.returncode != 0:
            raise RuntimeError("git exited with code {}.  Command: {}".format(
                               p.returncode, list2cmdline(args+chunk)))


def git_status_summary(path):
    c = Counter()
    cmd = git_cmd(["status", "--porcelain", "--ignored", "."], cwd=path)
    if cmd.returncode != 0:
        raise RuntimeError("git command returned exit code {}.".format(cmd.returncode))
    # XY:  X=index, Y=working tree.   For our simplistic approach we consider them together.
    for line in cmd.stdout.splitlines():
        state = line[0:2]
        if state == "??":
            c["untracked"] += 1
        elif state == "!!":
            c["ignored"] += 1
        else:
            c["changed"] += 1
    return c


def git_is_working_tree(path=None):
    return git_cmd(["rev-parse", "--is-inside-work-tree"], cwd=path).returncode == 0

'''
def get_gitdir(path=None):
    # May not need this.  the 'git status' was missing '.' to make it specific to JUST the app folder
    # I thought I needed this because of my local testing git-inside-of-git scenario...
    p = git_cmd(["rev-parse", "--git-dir"], cwd=path)
    if p.returncode == 0:
        gitdir = p.stdout.strip()
        return gitdir
    # Then later you can use  git --git-dir=apps/.git --working-tree apps Splunk_TA_aws
'''

def git_is_clean(path=None, check_untracked=True, check_ignored=False):
    # ANY change to the index or working tree is considered unclean.
    c = git_status_summary(path)
    total_changes = c["changed"]
    if check_untracked:
        total_changes += c["untracked"]
    if check_ignored:
        total_changes += c["ignored"]
    '''
    print "GIT IS CLEAN?:   path={} check_untracked={} check_ignored={} total_changes={} c={}".format(
        path, check_untracked, check_ignored, total_changes, c)
    '''
    return total_changes == 0


def git_ls_files(path, *modifiers):
    # staged=True
    args = [ "ls-files" ]
    for m in modifiers:
        args.append("--" + m)
    proc = git_cmd(args, cwd=path)
    if proc.returncode != 0:
        raise RuntimeError("Bad return code from git... {} add better exception handling here.."
                           .format(proc.returncode))
    return proc.stdout.splitlines()


def git_status_ui(path, *args):
    from subprocess import call
    # Don't redirect the std* streams; let the output go straight to the console
    cmd = [GIT_BIN, "status", "."]
    cmd.extend(args)
    call(cmd, cwd=path)


####################################################################################################
## CLI do_*() functions


def do_check(args):
    # Should we read a list of conf files from STDIN?
    if len(args.conf) == 1 and args.conf[0] == "-":
        confs = _stdin_iter()
    else:
        confs = args.conf
    c = Counter()
    exit_code = EXIT_CODE_SUCCESS
    for conf in confs:
        c["checked"] += 1
        if not os.path.isfile(conf):
            sys.stderr.write("Skipping missing file:  {0}\n".format(conf))
            c["missing"] += 1
            continue
        try:
            parse_conf(conf, profile=PARSECONF_STRICT_NC)
            c["okay"] += 1
            if not args.quiet:
                sys.stdout.write("Successfully parsed {0}\n".format(conf))
                sys.stdout.flush()
        except ConfParserException, e:
            sys.stderr.write("Error in file {0}:  {1}\n".format(conf, e))
            sys.stderr.flush()
            exit_code = EXIT_CODE_BAD_CONF_FILE
            # TODO:  Break out counts by error type/category (there's only a few of them)
            c["error"] += 1
        except Exception, e:
            sys.stderr.write("Unhandled top-level exception while parsing {0}.  "
                             "Aborting.\n{1}\n".format(conf, e))
            exit_code = EXIT_CODE_INTERNAL_ERROR
            c["error"] += 1
            break
    if True:    #show stats or verbose
        sys.stdout.write("Completed checking {0[checked]} files.  rc={1} Breakdown:\n"
                         "   {0[okay]} files were parsed successfully.\n"
                         "   {0[error]} files failed.\n".format(c, exit_code))
    sys.exit(exit_code)




def do_merge(args):
    ''' Merge multiple configuration files into one '''
    return merge_conf_files(args.target, args.conf, dry_run=args.dry_run, banner_comment=args.banner)


def do_diff(args):
    ''' Compare two configuration files. '''
    args.conf1.set_parser_option(keep_comments=args.comments)
    args.conf2.set_parser_option(keep_comments=args.comments)

    cfg1 = args.conf1.data
    cfg2 = args.conf2.data

    diffs = compare_cfgs(cfg1, cfg2)
    rc = show_diff(args.output, diffs, headers=(args.conf1.name, args.conf2.name))
    if rc == EXIT_CODE_DIFF_EQUAL:
        sys.stderr.write("Files are the same.\n")
    elif rc == EXIT_CODE_DIFF_NO_COMMON:
        sys.stderr.write("No common stanzas between files.\n")
    return rc


# ANSI_COLOR = "\x1b[{0}m"
ANSI_BOLD = 1
ANSI_RED = 31
ANSI_GREEN = 32
ANSI_YELLOW = 33
ANSI_RESET = 0
FORCE_TTY_COLOR = False


def tty_color(stream, *codes):
    if codes and FORCE_TTY_COLOR or hasattr(stream, "isatty") and stream.isatty():
        stream.write("\x1b[{}m".format(";".join([str(i) for i in codes])))

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
    def write_key(key, value, prefix=" "):
        if "\n" in value:
            write_multiline_key(key, value, prefix)
        else:
            if key.startswith("#-"):
                template = "{0}{2}\n"
            else:
                template = "{0}{1} = {2}\n"
            stream.write(template.format(prefix, key, value))

    def write_multiline_key(key, value, prefix=" "):
        lines = value.replace("\n", "\\\n").split("\n")
        tty_color(stream, _diff_color_mapping.get(prefix))
        stream.write("{0}{1} = {2}\n".format(prefix, key, lines.pop(0)))
        for line in lines:
            stream.write("{0}{1}\n".format(prefix, line))
        tty_color(stream, ANSI_RESET)

    def show_value(value, stanza, key, prefix=""):
        tty_color(stream, _diff_color_mapping.get(prefix))
        if isinstance(value, dict):
            if stanza is not GLOBAL_STANZA:
                stream.write("{0}[{1}]\n".format(prefix, stanza))
            for x, y in sorted(value.iteritems()):
                write_key(x, y, prefix)
            stream.write("\n")
        else:
            write_key(key, value, prefix)
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
            for (prefix, d) in [("-", op.a), ("+", op.b)]:
                for (stanza, keys) in sorted(d.items()):
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
            continue

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
            show_value(op.b,  op.location.stanza,  op.location.key, "-")
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


def _drop_stanza_comments(stanza):
    n = {}
    for (key, value) in stanza.iteritems():
        if key.startswith("#"):
            continue
        n[key] = value
    return n

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
    explode_defaults = True
    if args.explode_default:
        # Is this the SAME as exploding the defaults AFTER the merge?;  I think NOT.  Needs testing
        cfgs = [ explode_default_stanza(conf.data) for conf in args.conf ]
    else:
        cfgs = [ conf.data for conf in args.conf ]
    # Merge all config files:
    default_cfg = merge_conf_dicts(*cfgs)
    del cfgs
    local_cfg = args.target.data

    if args.explode_default:
        # Make a skeleton default dict; at the highest level, that ensure that all default
        default_stanza = default_cfg.get(GLOBAL_STANZA, default_cfg.get("default"))
        skeleton_default = dict([ (k,{}) for k in args.target.data])
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
                if match_bwlist(op.location.key, args.preserve_key):
                    '''
                    sys.stderr.write("Skipping key [PRESERVED]  [{0}] key={1} value={2!r}\n"
                                 "".format(op.location.stanza, op.location.key, op.a))
                    '''
                    continue
                del minz_cfg[op.location.stanza][op.location.key]
                # If that was the last remaining key in the stanza, delete the entire stanza
                if not minz_cfg[op.location.stanza]:
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
        rc = show_diff(sys.stdout, compare_cfgs(local_cfg, minz_cfg),
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


def do_promote(args):
    if isinstance(args.target, ConfDirProxy):
        # If a directory is given instead of a target file, then assume the source filename is the
        # same as the target filename.
        args.target = args.target.get_file(os.path.basename(args.source.name))

    # If src/dest are the same, then the file ends up being deleted.  Whoops!
    if os.path.samefile(args.source.name, args.target.name):
        sys.stderr.write("Aborting.  SOURCE and TARGET are the same file!\n")
        return EXIT_CODE_FAILED_SAFETY_CHECK

    if not os.path.isfile(args.target.name):
        sys.stdout.write("Target file {} does not exist.  Moving source file {} to the target."
                         .format(args.target.name, args.source.name))
        if args.keep:
            shutil.copy2(args.source.name, args.target.name)
        else:
            shutil.move(args.source.name, args.target.name)
        return

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
        delta = [ op for op in delta if op.tag!=DIFF_OP_DELETE ]
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
    smart_write_conf(args.target.name, cfg_final_tgt)
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


def do_sort(args):
    ''' Sort a single configuration file. '''
    stanza_delims = "\n" * args.newlines
    if args.inplace:
        failure = False
        changes = 0
        for conf in args.conf:
            try:
                # KISS:  Look for the KSCONF-NO-SORT string in the first 4k of this file.
                if not args.force and "KSCONF-NO-SORT" in open(conf.name).read(4096):
                    if not args.quiet:
                        sys.stderr.write("Skipping blacklisted file {}\n".format(conf.name))
                    continue
                data = parse_conf(conf, profile=PARSECONF_STRICT)
                conf.close()
                smart_rc = smart_write_conf(conf.name, data, stanza_delim=stanza_delims, sort=True)
            except ConfParserException, e:
                smart_rc = None
                sys.stderr.write("Error trying to process file {0}.  "
                                 "Error:  {1}\n".format(conf.name, e))
                failure = True
            if smart_rc == SMART_NOCHANGE:
                if not args.quiet:
                    sys.stderr.write("Nothing to update.  "
                                    "File {0} is already sorted\n".format(conf.name))
            else:
                sys.stderr.write("Replaced file {0} with sorted content.\n".format(conf.name))
                changes += 1
        if failure:
            return EXIT_CODE_BAD_CONF_FILE
        if changes:
            return EXIT_CODE_SORT_APPLIED
    else:
        for conf in args.conf:
            if len(args.conf) > 1:
                args.target.write("---------------- [ {0} ] ----------------\n\n".format(conf.name))
            try:
                data = parse_conf(conf, profile=PARSECONF_STRICT)
                write_conf(args.target, data, stanza_delim=stanza_delims, sort=True)
            except ConfParserException, e:
                sys.stderr.write("Error trying processing {0}.  Error:  {1}\n".format(conf.name, e))
                return EXIT_CODE_BAD_CONF_FILE


def do_combine(args):
    # Ignores case sensitivity.  If you're on Windows, name your files right.
    conf_file_re = re.compile("([a-z]+\.conf|(default|local)\.meta)$")

    if args.target is None:
        sys.stderr.write("Must provide the '--target' directory.\n")
        return EXIT_CODE_MISSING_ARG

    sys.stderr.write("Combining conf files into {}\n".format(args.target))
    args.source = list(_expand_glob_list(args.source))
    for src in args.source:
        sys.stderr.write("Reading conf files from {}\n".format(src))

    marker_file = os.path.join(args.target, CONTROLLED_DIR_MARKER)
    if os.path.isdir(args.target):
        if not os.path.isfile(os.path.join(args.target, CONTROLLED_DIR_MARKER)):
            sys.stderr.write("Target directory already exists, but it appears to have been created "
                             "by some other means.  Marker file missing.\n")
            return EXIT_CODE_COMBINE_MARKER_MISSING
    elif args.dry_run:
        sys.stderr.write("Skipping creating destination folder {0} (dry-run)\n".format(args.target))
    else:
        sys.stderr.write("Creating destination folder {0}\n".format(args.target))
        os.mkdir(args.target)
        open(marker_file, "w").write("This directory is managed by KSCONF.  Don't touch\n")

    # Build a common tree of all src files.
    src_file_index = defaultdict(list)
    for src_root in args.source:
        for (root, dirs, files) in relwalk(src_root):
            for fn in files:
                # Todo: Add blacklist CLI support:  defaults to consider: *sw[po], .git*, .bak, .~
                if fn.endswith(".swp") or fn.endswith("*.bak"):
                    continue
                src_file = os.path.join(root, fn)
                src_path = os.path.join(src_root, root, fn)
                src_file_index[src_file].append(src_path)

    # Find a set of files that exist in the target folder, but in NO source folder (for cleanup)
    target_extra_files = set()
    for (root, dirs, files) in relwalk(args.target):
        for fn in files:
            tgt_file = os.path.join(root, fn)
            if tgt_file not in src_file_index:
                # Todo:  Add support for additional blacklist wildcards (using fnmatch)
                if fn == CONTROLLED_DIR_MARKER or fn.endswith(".bak"):
                    continue
                target_extra_files.add(tgt_file)

    for (dest_fn, src_files) in sorted(src_file_index.items()):
        dest_path = os.path.join(args.target, dest_fn)

        # Make missing destination folder, if missing
        dest_dir = os.path.dirname(dest_path)
        if not os.path.isdir(dest_dir) and not args.dry_run:
            os.makedirs(dest_dir)

        # Handle conf files and non-conf files separately
        if not conf_file_re.search(dest_fn):
            #sys.stderr.write("Considering {0:50}  NON-CONF Copy from source:  {1!r}\n".format(dest_fn, src_files[-1]))
            # Always use the last file in the list (since last directory always wins)
            src_file = src_files[-1]
            if args.dry_run:
                if os.path.isfile(dest_path):
                    if file_compare(src_file, dest_path):
                        smart_rc = SMART_NOCHANGE
                    else:
                        if (_is_binary_file(src_file) or _is_binary_file(dest_path)):
                            # Binary files.  Can't compare...
                            smart_rc = "DRY-RUN (NO-DIFF=BIN)"
                        else:
                            show_text_diff(sys.stdout, src_file, dest_path)
                            smart_rc = "DRY-RUN (DIFF)"
                else:
                    smart_rc = "DRY-RUN (NEW)"
            else:
                smart_rc = smart_copy(src_file, dest_path)
            if smart_rc != SMART_NOCHANGE:
                sys.stderr.write("Copy <{0}>   {1:50}  from {2}\n".format(smart_rc, dest_path, src_file))
        else:
            # Handle merging conf files
            dest = ConfFileProxy(os.path.join(args.target, dest_fn), "rw",
                                 parse_profile=PARSECONF_MID)
            srcs = [ ConfFileProxy(sf, "r", parse_profile=PARSECONF_STRICT) for sf in src_files ]
            #sys.stderr.write("Considering {0:50}  CONF MERGE from source:  {1!r}\n".format(dest_fn, src_files[0]))
            smart_rc = merge_conf_files(dest, srcs, dry_run=args.dry_run,
                                        banner_comment=args.banner)
            if smart_rc != SMART_NOCHANGE:
                sys.stderr.write("Merge <{0}>   {1:50}  from {2!r}\n".format(smart_rc, dest_path,
                                                                             src_files))

    if True and target_extra_files:     # Todo: Allow for cleanup to be disabled via CLI
        sys.stderr.write("Cleaning up extra files not part of source tree(s):  {0} files.\n".format(
            len(target_extra_files)))
        for dest_fn in target_extra_files:
            sys.stderr.write("Remove unwanted file {0}\n".format(dest_fn))
            os.unlink(os.path.join(args.target, dest_fn))




def do_unarchive(args):
    """ Install / upgrade a Splunk app from an archive file """
    # Handle ignored files by preserving them as much as possible.
    # Add --dry-run mode?  j/k - that's what git is for!

    if not os.path.isfile(args.tarball):
        sys.stderr.write("No such file or directory {}\n".format(args.tarball))
        return EXIT_CODE_FAILED_SAFETY_CHECK

    if not os.path.isdir(args.dest):
        sys.stderr.write("Destination directory does not exist: {}\n".format(args.dest))
        return EXIT_CODE_FAILED_SAFETY_CHECK

    f_hash = file_hash(args.tarball)
    sys.stdout.write("Inspecting archive:               {}\n".format(args.tarball))

    new_app_name = args.app_name
    # ARCHIVE PRE-CHECKS:  Archive must contain only one app, no weird paths, ...
    app_name = set()
    app_conf = {}
    files = 0
    local_files = set()
    a = extract_archive(args.tarball, extract_filter=gaf_filter_name_like("app.conf"))
    for gaf in sanity_checker(a):
        gaf_app, gaf_relpath = gaf.path.split("/", 1)
        files += 1
        if gaf.path.endswith("app.conf") and gaf.payload:
            conffile = StringIO(gaf.payload)
            conffile.name = os.path.join(args.tarball, gaf.path)
            app_conf = parse_conf(conffile, profile=PARSECONF_LOOSE)
            del conffile
        elif gaf_relpath.startswith("local") or gaf_relpath.endswith("local.meta"):
            local_files.add(gaf_relpath)
        app_name.add(gaf.path.split("/", 1)[0])
        del gaf_app, gaf_relpath
    if len(app_name) > 1:
        sys.stderr.write("The 'unarchive' command only supports extracting a single splunk app at "
                         "a time.\nHowever the archive {} contains {} apps:  {}\n"
                         "".format(args.tarball, len(app_name), ", ".join(app_name)))
        return EXIT_CODE_FAILED_SAFETY_CHECK
    else:
        app_name = app_name.pop()
    del a
    if local_files:
        sys.stderr.write("Local {} files found in the archive.  ".format(len(local_files)))
        if args.allow_local:
            sys.stderr.write("Keeping these due to the '--allow-local' flag\n")
        else:
            sys.stderr.write("Excluding these files by default.  Use '--allow-local' to override.")

    if not new_app_name and True:        # if not --no-app-name-fixes
        if app_name.endswith("-master"):
            sys.stdout.write("Automatically dropping '-master' from the app name.  This is often "
                             "the result of a github export.\n")
            # Trick, but it works...
            new_app_name = app_name[:-7]
        mo = re.search(r"(.*)-\d+\.[\d.-]+$", app_name)
        if mo:
            sys.stdout.write("Automatically removing the version suffix from the app name.  '{}' "
                             "will be extracted as '{}'\n".format(app_name, mo.group(1)))
            new_app_name = mo.group(1)

    app_basename = new_app_name or app_name
    dest_app = os.path.join(args.dest, app_basename)
    sys.stdout.write("Inspecting destination folder:    {}\n".format(os.path.abspath(dest_app)))

    # FEEDBACK TO THE USER:   UPGRADE VS INSTALL, GIT?, APP RENAME, ...
    app_name_msg = app_name
    vc_msg = "without version control support"

    old_app_conf = {}
    if os.path.isdir(dest_app):
        mode = "upgrade"
        is_git = git_is_working_tree(dest_app)
        try:
            # Ignoring the 'local' entries since distributed apps should never modify local anyways
            old_app_conf_file = os.path.join(dest_app, args.default_dir or "default", "app.conf")
            old_app_conf = parse_conf(old_app_conf_file, profile=PARSECONF_LOOSE)
        except:
            sys.stderr.write("Unable to read app.conf from existing install.\n")
    else:
        mode = "install"
        is_git = git_is_working_tree(args.dest)
    if is_git:
        vc_msg = "with git support"
    if new_app_name and new_app_name != app_name:
        app_name_msg = "{} (renamed from {})".format(new_app_name, app_name)

    def show_pkg_info(conf, label):
        sys.stdout.write("{} packaging info:    '{}' by {} (version {})\n".format(
            label,
            conf.get("ui", {}).get("label", "Unknown"),
            conf.get("launcher", {}).get("author", "Unknown"),
            conf.get("launcher", {}).get("version", "Unknown")))
    if old_app_conf:
        show_pkg_info(old_app_conf, " Installed app")
    if app_conf:
        show_pkg_info(app_conf, "   Tarball app")

    sys.stdout.write("About to {} the {} app {}.\n".format(mode, app_name_msg, vc_msg))

    existing_files = set()
    if mode == "upgrade":
        if is_git:
            existing_files.update(git_ls_files(dest_app))
            if not existing_files:
                sys.stderr.write("App appears to be in a git repository but no files have been "
                                 "staged or committed.  Either commit or remove '{}' and try "
                                 "again.\n".format(dest_app))
                return EXIT_CODE_FAILED_SAFETY_CHECK
            if args.git_sanity_check == "off":
                sys.stdout.write("The 'git status' safety checks have been disabled via CLI"
                                 "argument.  Skipping.\n")
            else:
                d = {
                #                untracked, ignored
                    "changed" :     (False, False),
                    "untracked" :   (True, False),
                    "ignored":      (True, True)
                }
                is_clean = git_is_clean(dest_app, *d[args.git_sanity_check])
                del d
                if is_clean:
                    sys.stdout.write("Git folder is clean.   Okay to proceed with the upgrade.\n")
                else:
                    sys.stderr.write("Unable to move forward without a clean working directory.\n"
                                     "Clean up and try again.  Modifications are listed below.\n\n")
                    sys.stderr.flush()
                    if args.git_sanity_check == "changed":
                        git_status_ui(dest_app, "--untracked-files=no")
                    elif args.git_sanity_check == "ignored":
                        git_status_ui(dest_app, "--ignored")
                    else:
                        git_status_ui(dest_app)
                    return EXIT_CODE_FAILED_SAFETY_CHECK
        else:
            for (root, dirs, filenames) in os.walk(dest_app):
                for fn in filenames:
                    existing_files.add(os.path.join(root, fn))
        sys.stdout.write("Before upgrade.  App has {} files\n".format(len(existing_files)))
    else:
        sys.stdout.write("Git clean check skipped.  Not needed for a fresh app install.\n")

    def fixup_pattern_bw(patterns, prefix=None):
        modified = []
        for pattern in patterns:
            if pattern.startswith("./"):
                if prefix:
                    pattern = "{0}/{1}".format(prefix, pattern[2:])
                else:
                    pattern = pattern[2:]
                modified.append(pattern)
            # If a pattern like 'tags.conf' or '*.bak' is provided, assume basename match (any dir)
            elif "/" not in pattern:
                modified.append("(^|.../)" + pattern)
            else:
                modified.append(pattern)
        return modified

    # PREP ARCHIVE EXTRACTION
    installed_files = set()
    excludes = list(args.exclude)
    '''
    for pattern in args.exclude:
        # If a pattern like 'default.meta' or '*.bak' is provided, assume it's a basename match.
        if "/" not in pattern:
            excludes.append(".../" + pattern)
        else:
            excludes.append(pattern)
    '''
    if not args.allow_local:
        for pattern in local_files:
            excludes.append("./" + pattern)
    excludes = fixup_pattern_bw(excludes, app_basename)
    sys.stderr.write("Extraction exclude patterns:  {!r}\n".format(excludes))
    path_rewrites = []
    files_iter = extract_archive(args.tarball)
    if True:
        files_iter = sanity_checker(files_iter)
    if args.default_dir:
        rep = "/{}/".format(args.default_dir.strip("/"))
        path_rewrites.append(("/default/", rep))
        del rep
    if new_app_name:
        # We do have the "app_name" extracted from our first pass above, but
        regex = re.compile(r'^([^/]+)(?=/)')
        path_rewrites.append((regex, new_app_name))
    if path_rewrites:
        files_iter = gen_arch_file_remapper(files_iter, path_rewrites)

    sys.stdout.write("Extracting app now...\n")
    for gaf in files_iter:
        if match_bwlist(gaf.path, excludes, escape=False):
            print "Skipping [blacklist] {}".format(gaf.path)
            continue
        if not is_git or args.git_mode in ("nochange", "stage"):
            print "{0:60s} {2:o} {1:-6d}".format(gaf.path, gaf.size, gaf.mode)
        installed_files.add(gaf.path.split("/",1)[1])
        full_path = os.path.join(args.dest, gaf.path)
        dir_exists(os.path.dirname(full_path))
        with open(full_path, "wb") as fp:
            fp.write(gaf.payload)
        os.chmod(full_path, gaf.mode)
        del fp, full_path

    files_new, files_upd, files_del = _cmp_sets(installed_files, existing_files)
    '''
    print "New: \n\t{}".format("\n\t".join(sorted(files_new)))
    print "Existing: \n\t{}".format("\n\t".join(sorted(files_upd)))
    print "Removed:  \n\t{}".format("\n\t".join(sorted(files_del)))
    '''

    sys.stdout.write("Extracted {} files:  {} new, {} existing, and {} removed\n".format(
        len(installed_files), len(files_new), len(files_upd), len(files_del)))

    # Filer out "removed" files; and let us keep some based on a keep-whitelist:  This should
    # include things like local, ".gitignore", ".gitattributes" and so on

    keep_list = [ ".git*" ]
    keep_list.extend(args.keep)
    if not args.allow_local:
        keep_list += [ "local/...", "local.meta" ]
    keep_list = fixup_pattern_bw(keep_list)
    sys.stderr.write("Keep file patterns:  {!r}\n".format(keep_list))

    files_to_delete = []
    files_to_keep = []
    for fn in files_del:
        if match_bwlist(fn, keep_list, escape=False):
            # How to handle a keep of "default.d/..." when we DO want to cleanup the default
            # redirect folder of "default.d/10-upstream"?
            # Practially this probably isn't mucn of an issue since most apps will continue to send
            # an ever increasing list of default files (to mask out old/unused ones)
            sys.stdout.write("Keeping {}\n".format(fn))
            files_to_keep.append(fn)
        else:
            files_to_delete.append(fn)
    if files_to_keep:
        sys.stdout.write("Keeping {} of {} files marked for deletion due to whitelist.\n"
                         .format(len(files_to_keep), len(files_del)))
    git_rm_queue = []

    if files_to_delete:
        sys.stdout.write("Removing files that are no longer in the upgraded version of the app.\n")
    for fn in files_to_delete:
        path = os.path.join(dest_app, fn)
        if is_git and args.git_mode in ("stage", "commit"):
            print "git rm -f {}".format(path)
            git_rm_queue.append(fn)
        else:
            print "rm -f {}".format(path)
            os.unlink(path)

    if git_rm_queue:
        # Run 'git rm file1 file2 file3 ..." (using an xargs like mechanism)
        git_cmd_iterable(["rm"], git_rm_queue, cwd=dest_app)
    del git_rm_queue

    if is_git:
        if args.git_mode in ("stage", "commit"):
            git_cmd(["add", os.path.basename(dest_app)], cwd=os.path.dirname(dest_app))
            #sys.stdout.write("git add {}\n".format(os.path.basename(dest_app)))
        '''
        else:
            sys.stdout.write("git add {}\n".format(dest_app))
        '''

        # Is there anything to stage/commit?
        if git_is_clean(os.path.dirname(dest_app), check_untracked=False):
            sys.stderr.write("No changes detected.  Nothing to {}\n".format(args.git_mode))
            return

        git_commit_app_name = app_conf.get("ui", {}).get("label", os.path.basename(dest_app))
        git_commit_new_version = app_conf.get("launcher", {}).get("version", None)
        if mode == "install":
            git_commit_message = "Install {}".format(git_commit_app_name)

            if git_commit_new_version:
                git_commit_message += " version {}".format(git_commit_new_version)
        else:
            # Todo:  Specify Upgrade/Downgrade/Refresh
            git_commit_message = "Upgrade {}".format(
                git_commit_app_name)
            git_commit_old_version = old_app_conf.get("launcher", {}).get("version", None)
            if git_commit_old_version and git_commit_new_version:
                git_commit_message += " version {} (was {})".format(git_commit_new_version,
                                                                    git_commit_old_version)
            elif git_commit_new_version:
                git_commit_message += " to version {}".format(git_commit_new_version)
        # Could possibly include some CLI arg details, like what file patterns were excluded
        git_commit_message += "\n\nSHA256 {} {}\n\nSplunk-App-managed-by: ksconf" \
                                .format(f_hash, os.path.basename(args.tarball))
        git_commit_cmd = [ "commit", os.path.basename(dest_app), "-m", git_commit_message ]

        if not args.no_edit:
            git_commit_cmd.append("--edit")

        git_commit_cmd.extend(args.git_commit_args)

        if args.git_mode == "commit":
            proc = git_cmd(git_commit_cmd, cwd=os.path.dirname(dest_app), capture_std=False)
            if proc.returncode == 0:
                sys.stderr.write("You changes have been committed.  Please review before pushing "
                                 "If you find any issues, here are some helpful options:\n\n"
                                 "To fix some minor issues in the last commit, edit and add the "
                                 "files to be fixed, then run:\n"
                                 "\tgit commit --amend\n\n"
                                 "To roll back the last commit but KEEP the app upgrade, run:\n"
                                 "\t git reset --soft HEAD^1\n\n"
                                 "To roll back the last commit and REVERT the app upgrade, run:\n"
                                 "\tgit reset --hard HEAD^1\n\n")
            else:
                sys.stderr.write("Git commit failed.  Return code {}. Git args:  git {}\n"
                                 .format(proc.returncode, list2cmdline(git_commit_cmd)))
                return EXIT_CODE_GIT_FAILURE
        elif args.git_mode == "stage":
            sys.stdout.write("To commit later, use the following\n")
            sys.stdout.write("\tgit {}\n".format(list2cmdline(git_commit_cmd).replace("\n", "\\n")))
        # When in 'nochange' mode, no point in even noting these options to the user.


class ConfDirProxy(object):
    def __init__(self, name, mode, parse_profile=None):
        self.name = name
        self._mode = mode
        self._parse_profile = parse_profile

    def get_file(self, relpath):
        path = os.path.join(self.name, relpath)
        return ConfFileProxy(path, self._mode, parse_profile=self._parse_profile, is_file=True)


class ConfFileProxy(object):
    def __init__(self, name, mode, stream=None, parse_profile=None, is_file=None):
        self.name = name
        if is_file is not None:
            self._is_file = is_file
        elif stream:
            self._is_file = False
        else:
            self._is_file = True
        self._stream = stream
        self._mode = mode
        # Not sure if there's a good reason to keep a copy of the data locally?
        self._data = None
        self._parse_profile = parse_profile or {}

    def is_file(self):
        return self._is_file

    def _type(self):
        if self._is_file:
            return "file"
        else:
            return "stream"

    def _close_stream(self):
        if self._stream:
            if not self._stream.closed:
                self._stream.close()
        self._stream = None

    def set_parser_option(self, **kwargs):
        """ Setting a key to None will remove that setting. """
        changed = False
        for (k, v) in kwargs.items():
            if v is None:
                if k in self._parse_profile:
                    del self._parse_profile[k]
                    changed = True
            else:
                cv = self._parse_profile.get(k, None)
                if cv != v:
                    self._parse_profile[k] = v
                    changed = True
        if changed:
            self._data = None

    @property
    def stream(self):
        if self._stream is None:
            self._stream = open(self.name, self._mode)
        return self._stream

    @property
    def data(self):
        if self._data is None:
            self._data = self.load()
        return self._data

    def load(self, profile=None):
        if "r" not in self._mode:
            # Q: Should we mimic the exception caused by doing a read() on a write-only file object?
            raise ValueError("Unable to load() from {} with mode '{}'".format(self._type(),
                                                                              self._mode))
        parse_profile = dict(self._parse_profile)
        if profile:
            parse_profile.update(profile)
        data = parse_conf(self.stream, profile=parse_profile)
        return data

    def dump(self, data):
        if "w" not in self._mode:
            raise ValueError("Unable to dump() to {} with mode '{}'".format(self._type(),
                                                                            self._mode))
        # Feels like the right thing to do????  OR self._data = data
        self._data = None
        # write vs smart write here ----
        if self._is_file:
            self._close_stream()
            return smart_write_conf(self.name, data)
        else:
            write_conf(self._stream, data)
            return SMART_CREATE

    def unlink(self):
        # Eventually this could trigger some kind of backup or recovery mechanism
        # self._close_stream()
        return os.unlink(self.name)

    def backup(self, bkname=None):
        raise NotImplementedError

    def checksum(self, hash="sha256"):
        raise NotImplementedError



class ConfFileType(object):
    """Factory for creating conf file object types;  returns a lazy-loader ConfFile proxy class

    Started from argparse.FileType() and then changed everything.   With our use case, it's often
    necessary to delay writing, or read before writing to a conf file (depending on weather or not
    --dry-run mode is enabled, for example.)

    Instances of FileType are typically passed as type= arguments to the
    ArgumentParser add_argument() method.

    Keyword Arguments:
        - mode      A string indicating how the file is to be opened.  Accepts "r", "w", and "rw".
        - action    'none', 'open', 'load'.   'none' means no preparation or tests;  'open' means
                    make sure the file exists/openable;  'load' means make sure the file can be
                    opened and parsed successfully.
    """

    def __init__(self, mode='r', action="open", parse_profile=None, accept_dir=False):
        self._mode = mode
        self._action = action
        self._parse_profile = parse_profile or {}
        self._accept_dir = accept_dir

    def __call__(self, string):
        from argparse import ArgumentTypeError
        # the special argument "-" means sys.std{in,out}
        if string == '-':
            if 'r' in self._mode:
                cfp = ConfFileProxy("<stdin>", "r", stream=sys.stdin, is_file=False)
                if self._action == "load":
                    try:
                        d = cfp.data
                        del d
                    except ConfParserException, e:
                        raise ArgumentTypeError("failed to parse <stdin>: {}".format(e))
                return cfp
            elif 'w' in self._mode:
                return ConfFileProxy("<stdout>", "w", stream=sys.stdout, is_file=False)
            else:
                raise ValueError('argument "-" with mode {}'.format(self._mode))
        if self._accept_dir and os.path.isdir(string):
            return ConfDirProxy(string, self._mode, parse_profile=self._parse_profile)
        if self._action == "none":
            return ConfFileProxy(string, self._mode, parse_profile=self._parse_profile)
        else:
            try:
                stream = open(string, self._mode)
                cfp = ConfFileProxy(string, self._mode, stream=stream,
                                    parse_profile=self._parse_profile, is_file=True)
                if self._action == "load":
                    # Force file to be parsed by accessing the 'data' property
                    d = cfp.data
                    del d
                return cfp
            except IOError as e:
                message = "can't open '%s': %s"
                raise ArgumentTypeError(message % (string, e))
            except ConfParserException, e:
                raise ArgumentTypeError("failed to parse '%s': %s" % (string, e))
            except TypeError, e:
                raise ArgumentTypeError("Parser config error '%s': %s" % (string, e))

    def __repr__(self):
        args = self._mode, self._action, self._parse_profile
        args_str = ', '.join(repr(arg) for arg in args if arg != -1)
        return '%s(%s)' % (type(self).__name__, args_str)


####################################################################################################
## CLI definition


# ------------------------------------------ wrap to 80 chars ----------------v
_cli_description= """Kintyre Splunk CONFig tool.

This utility handles a number of common Splunk app maintenance tasks in a small
and easy to relocate package.  Specifically, this tools deals with many of the
nuances with storing Splunk apps in git, and pointing live Splunk apps to a git
repository.  Merging changes from the live system's (local) folder to the
version controlled (default) folder, and dealing with more than one layer of
"default" (which splunk can't handle natively) are all supported tasks.
"""
# ------------------------------------------ wrap to 80 chars ----------------^


def cli(argv=None, _unittest=False):
    import argparse
    import textwrap

    # For now, just effectively a copy of RawDescriptionHelpFormatter
    class MyDescriptionHelpFormatter(argparse.HelpFormatter):
        def _fill_text(self, text, width, indent):
            # Looks like this one is ONLY used for the top-level description
            return ''.join([indent + line for line in text.splitlines(True)])

        def _split_lines(self, text, width):
            text = self._whitespace_matcher.sub(' ', text).strip()
            return textwrap.wrap(text, width)

    parser = argparse.ArgumentParser(fromfile_prefix_chars="@",
                                     formatter_class=MyDescriptionHelpFormatter,
                                     description=_cli_description)
    # Optional argcomplete library for CLI (BASH-based) tab completion
    # pip install argcomplete
    # activate-global-python-argcomplete  (in ~/.bashrc)
    try:
        from argcomplete import autocomplete
        from argcomplete.completers import FilesCompleter, DirectoriesCompleter
    except ImportError:
        def _argcomplete_noop(*args, **kwargs): del args, kwargs
        autocomplete = _argcomplete_noop
        # noinspection PyPep8Naming
        FilesCompleter = DirectoriesCompleter = _argcomplete_noop

    # Someday add *.meta (once more testing is done with those files
    conf_files_completer = FilesCompleter(allowednames=["*.conf"])

    # Common settings
    '''
    ### DEPRECATE THESE
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
    '''
    parser.add_argument("--force-color", action="store_true", default=False,
                        help="Force TTY color mode on.  Useful if piping the output a color-aware"
                             "pager, like 'less -R'")

    # Logging settings -- not really necessary for simple things like 'diff', 'merge', and 'sort';
    # more useful for 'patch', very important for 'combine'

    subparsers = parser.add_subparsers()

    # SUBCOMMAND:  splconf check <CONF>
    sp_chck = subparsers.add_parser("check",
                                    help="Perform basic syntax and sanity checks on .conf files",
                                    description=
                                    "Provide basic syntax and sanity checking for Splunk's .conf "
                                    "files.  Use Splunk's builtin 'btool check' for a more robust "
                                    "validation of keys and values.\n\n"
                                    "Consider using this utility as part of a pre-commit hook.")
    sp_chck.set_defaults(funct=do_check)
    sp_chck.add_argument("conf", metavar="FILE", nargs="+",
                         help="One or more configuration files to check.  If the special value of "
                              "'-' is given, then the list of files to validate is read from "
                              "standard input"
                         ).completer = conf_files_completer
    sp_chck.add_argument("--quiet", "-q", default=False, action="store_true",
                         help="Reduce the volume of output.")
    ''' # Do we really need this?
    sp_chck.add_argument("--max-errors", metavar="INT", type=int, default=0,
                         help="Abort check if more than this many files fail validation.  Useful
                         for a pre-commit hook where any failure is unacceptable.")
    '''
    # Usage example:   find . -name '*.conf' | splconf check -  (Nice little pre-commit script)

    # SUBCOMMAND:  splconf combine --target=<DIR> <SRC1> [ <SRC-n> ]
    sp_comb = subparsers.add_parser("combine",
                                    help=
                                    "Merge configuration files from one or more source directories "
                                    "into a combined destination directory.  This allows for an "
                                    "arbitrary number of splunk's configuration layers within a "
                                    "single app.  Ad-hoc uses include merging the 'users' "
                                    "directory across several instances after a phased server"
                                    "migration.",
                                    description="""\
Merge .conf settings from multiple source directories into a combined target
directory.   Configuration files can be stored in a '/etc/*.d' like directory
structure and consolidated back into a single 'default' directory.

This command supports both one-time operations and recurring merge jobs.
For example, this command can be used to combine all users knowledge objects
(stored in 'etc/users') after a server migration, or to merge a single user's
settings after an their account has been renamed.  Recurring operations assume
some type of external scheduler is being used.  A best-effort is made to only
write to target files as needed.

The 'combine' command takes your logical layers of configs (upstream,
corporate, splunk admin fixes, and power user knowledge objects, ...)
expressed as individual folders and merges them all back into the single
'default' folder that Splunk reads from.  One way to keep the 'default'
folder up-to-date is using client-side git hooks.

No directory layout is mandatory, but but one simple approach is to model your
layers using a prioritized 'default.d' directory structure. (This idea is
borrowed from the Unix System V concept where many services natively read
their config files from '/etc/*.d' directories.)


THE PROBLEM:

In a typical enterprise deployment of Splunk, a single app can easily have
multiple logical sources of configuration:  (1) The upstream app developer,
(2) local developer app-developer  adds organization-specific customizations
or fixes, (3) splunk admin tweaks the inappropriate ''indexes.conf' settings,
and (4) custom knowledge objects added by your subject matter experts.
Ideally we'd like to version control these, but doing so is complicated
because normally you have to manage all 4 of these logical layers in one
'default' folder.  (Splunk requires that app settings be located either in
'default' or 'local'; and managing local files with version control leads to
merge conflicts; so effectively, all version controlled settings need to be in
'default', or risk merge conflicts.)  So when a new upstream version is
released, someone has to manually upgrade the app being careful to preserve
all custom configurations.  The solution provided by the 'combine'
functionality is that all of these logical sources can be stored separately in
their own physical directories allowing changes to be managed independently.
(This also allows for different layers to be mixed-and-matched by selectively
including which layers to combine.)  While this doesn't completely remove the
need for a human to review app upgrades, it does lower the overhead enough
that updates can be pulled in more frequently, thus reducing the divergence
potential.  (Merge frequently.)


NOTES:

The 'combine' command is similar to running the 'merge' subcommand recursively
against a set of directories.  One key difference is that this command will
gracefully handle non-conf files intelligently too.

EXAMPLE:

    Splunk_CiscoSecuritySuite/
    ├── README
    ├── default.d
    │   ├── 10-upstream
    │   │   ├── app.conf
    │   │   ├── data
    │   │   │   └── ui
    │   │   │       ├── nav
    │   │   │       │   └── default.xml
    │   │   │       └── views
    │   │   │           ├── authentication_metrics.xml
    │   │   │           ├── cisco_security_overview.xml
    │   │   │           ├── getting_started.xml
    │   │   │           ├── search_ip_profile.xml
    │   │   │           ├── upgrading.xml
    │   │   │           └── user_tracking.xml
    │   │   ├── eventtypes.conf
    │   │   ├── macros.conf
    │   │   ├── savedsearches.conf
    │   │   └── transforms.conf
    │   ├── 20-my-org
    │   │   └── savedsearches.conf
    │   ├── 50-splunk-admin
    │   │   ├── indexes.conf
    │   │   ├── macros.conf
    │   │   └── transforms.conf
    │   └── 70-firewall-admins
    │       ├── data
    │       │   └── ui
    │       │       └── views
    │       │           ├── attacks_noc_bigscreen.xml
    │       │           ├── device_health.xml
    │       │           └── user_tracking.xml
    │       └── eventtypes.conf

Commands:

    cd Splunk_CiscoSecuritySuite
    ksconf combine default.d/* --target=default

""",
                                    formatter_class=MyDescriptionHelpFormatter)
    sp_comb.set_defaults(funct=do_combine)
    sp_comb.add_argument("source", nargs="+",
                         help="The source directory where configuration files will be merged from. "
                              "When multiple sources directories are provided, start with the most "
                              "general and end with the specific;  later sources will override "
                              "values from the earlier ones. Supports wildcards so a typical Unix "
                              "conf.d/##-NAME directory structure works well."
                         ).completer = DirectoriesCompleter()
    sp_comb.add_argument("--target", "-t",
                         help="Directory where the merged files will be stored.  Typically either "
                              "'default' or 'local'"
                         ).completer = DirectoriesCompleter()
    sp_comb.add_argument("--dry-run", "-D", default=False, action="store_true",
                         help="Enable dry-run mode.  Instead of writing to TARGET, show what "
                              "changes would be made to it in the form of a 'diff'. "
                              "If TARGET doesn't exist, then show the merged file.")
    sp_comb.add_argument("--banner", "-b",
                         default=" **** WARNING: This file is managed by 'ksconf combine', do not "
                                 "edit hand-edit this file! ****",
                         help="A warning banner telling discouraging editing of conf files.")


    # SUBCOMMAND:  splconf diff <CONF> <CONF>
    sp_diff = subparsers.add_parser("diff",
                                    help="Compares settings differences of two .conf files "
                                         "ignoring textual and sorting differences",
                                         description="""\
Compares the content differences of two .conf files

This command ignores textual differences (like order, spacing, and comments)
and focuses strictly on comparing stanzas, keys, and values.  Note that spaces
within any given value will be compared.  Multiline fields are compared in are
compared in a more traditional 'diff' output so that long savedsearches and
macros can be compared more easily.
""",
                                    formatter_class=MyDescriptionHelpFormatter)
    sp_diff.set_defaults(funct=do_diff)
    sp_diff.add_argument("conf1", metavar="CONF1", help="Left side of the comparison",
                         type=ConfFileType("r", "load", parse_profile=PARSECONF_MID_NC)
                         ).completer = conf_files_completer
    sp_diff.add_argument("conf2", metavar="CONF2", help="Right side of the comparison",
                         type=ConfFileType("r", "load", parse_profile=PARSECONF_MID_NC)
                         ).completer = conf_files_completer
    sp_diff.add_argument("-o", "--output", metavar="FILE",
                         type=argparse.FileType('w'), default=sys.stdout,
                         help="File where difference is stored.  Defaults to standard out.")
    sp_diff.add_argument("--comments", "-C",
                         action="store_true", default=False,
                         help="Enable comparison of comments.  (Unlikely to work consistently)")


    # SUBCOMMAND:  splconf promote --target=<CONF> <CONF>
    sp_prmt = subparsers.add_parser("promote",
                                    help="Promote .conf settings from one file into another either "
                                         "in batch mode (all changes) or interactively allowing "
                                         "the user to pick which stanzas and keys to integrate. "
                                         "Changes made via the UI (stored in the local folder) "
                                         "can be promoted (moved) to a version-controlled "
                                         "directory.",
                                    description="""\
Propagate .conf settings applied in one file to another.  Typically this is
used to take local changes made via the UI and push them into a default (or
default.d/) location.

NOTICE:  By default, changes are *MOVED*, not just copied.

Promote has two different modes:  batch and interactive.  In batch mode all
changes are applied automatically and the (now empty) source file is removed.
In interactive mode the user is prompted to pick which stanzas and keys to
integrate.  This can be used to push  changes made via the UI, which are
stored in a 'local' file, to the version-controlled 'default' file.  Note that
the normal operation moves changes from the SOURCE file to the TARGET,
updating both files in the process.  But it's also possible to preserve the
local file, if desired.

If either the source file or target file is modified while a promotion is
under progress, changes will be aborted.  And any custom selections you made
will be lost.  (This needs improvement.)
""",
                                    formatter_class=MyDescriptionHelpFormatter)
    sp_prmt.set_defaults(funct=do_promote, mode="ask")
    sp_prmt.add_argument("source", metavar="SOURCE",
                         type=ConfFileType("rw", "load", parse_profile=PARSECONF_STRICT_NC),
                         help="The source configuration file to pull changes from.  (Typically the "
                              "'local' conf file)"
                         ).completer = conf_files_completer
    sp_prmt.add_argument("target", metavar="TARGET",
                         type=ConfFileType("rw", "load", accept_dir=True,
                                           parse_profile=PARSECONF_STRICT),
                         help="Configuration file or directory to push the changes into. "
                              "(Typically the 'default' folder) "
                              "When a directory is given instead of a file then the same file name "
                              "is assumed for both SOURCE and TARGET"
                         ).completer = conf_files_completer
    sp_prg1 = sp_prmt.add_mutually_exclusive_group()
    sp_prg1.add_argument("--batch", "-b",
                         action="store_const",
                         dest="mode", const="batch",
                         help="Use batch mode where all configuration settings are automatically "
                              "promoted.  All changes are moved from the source to the target "
                              "file and the source file will be blanked or removed.")
    sp_prg1.add_argument("--interactive", "-i",
                         action="store_const",
                         dest="mode", const="interactive",
                         help="Enable interactive mode where the user will be prompted to approve "
                              "the promotion of specific stanzas and keys.  The user will be able "
                              "to apply, skip, or edit the changes being promoted.  (This "
                              "functionality was inspired by 'git add --patch').")
    sp_prmt.add_argument("--force", "-f",
                         action="store_true", default=False,
                         help="Disable safety checks.")
    sp_prmt.add_argument("--keep", "-k",
                         action="store_true", default=False,
                         help="Keep conf settings in the source file.  This means that changes "
                              "will be copied into the target file instead of moved there.")
    sp_prmt.add_argument("--keep-empty",
                         action="store_true", default=False,
                         help="Keep the source file, even if after the settings promotions the "
                              "file has no content.  By default, SOURCE will be removed if all "
                              "content has been moved into the TARGET location.  "
                              "Splunk will re-create any necessary local files on the fly.")

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

    # SUBCOMMAND:  splconf merge --target=<CONF> <CONF> [ <CONF-n> ... ]
    sp_merg = subparsers.add_parser("merge",
                                    help="Merge two or more .conf files",
                                    formatter_class=MyDescriptionHelpFormatter)
    sp_merg.set_defaults(funct=do_merge)
    sp_merg.add_argument("conf", metavar="FILE", nargs="+",
                         type=ConfFileType("r", "load", parse_profile=PARSECONF_MID),
                         help="The source configuration file to pull changes from."
                         ).completer = conf_files_completer
    sp_merg.add_argument("--target", "-t", metavar="FILE",
                         type=ConfFileType("rw", "none", parse_profile=PARSECONF_STRICT),
                         default=ConfFileProxy("<stdout>", "w", sys.stdout),
                         help="Save the merged configuration files to this target file.  If not "
                              "given, the default is to write the merged conf to standard output."
                         ).completer = conf_files_completer
    sp_merg.add_argument("--dry-run", "-D", default=False, action="store_true",
                         help="Enable dry-run mode.  Instead of writing to TARGET, show what "
                              "changes would be made to it in the form of a 'diff'. "
                              "If TARGET doesn't exist, then show the merged file.")
    sp_merg.add_argument("--banner", "-b", default="",
                         help="A banner or warning comment to add to the TARGET file.  Often used "
                              "to warn Splunk admins from editing a auto-generated file.")

    # SUBCOMMAND:  splconf minimize --target=<CONF> <CONF> [ <CONF-n> ... ]
    # Example workflow:
    #   1. cp default/props.conf local/props.conf
    #   2. vi local/props.conf (edit JUST the lines you want to change)
    #   3. splconf minimize --target=local/props.conf default/props.conf
    #  (You could take this a step further by appending "$SPLUNK_HOME/system/default/props.conf"
    # and removing any SHOULD_LINEMERGE = true entries (for example)
    sp_minz = subparsers.add_parser("minimize",
                                    help="Minimize the target file by removing entries duplicated "
                                         "in the default conf(s) provided.  ",
                                    description="""\
The minimize command will allow for the removal of all
default-ish settings from a target configuration files.
In theory, this allows for a cleaner upgrade, and fewer
duplicate settings.""",
                                    formatter_class=MyDescriptionHelpFormatter)
    sp_minz.set_defaults(funct=do_minimize)
    sp_minz.add_argument("conf", metavar="FILE", nargs="+",
                         type=ConfFileType("r", "load", parse_profile=PARSECONF_LOOSE),
                         help="The default configuration file(s) used to determine what base "
                              "settings are unnecessary to keep in the target file."
                         ).completer = conf_files_completer
    sp_minz.add_argument("--target", "-t", metavar="FILE",
                         type=ConfFileType("rw", "load", parse_profile=PARSECONF_STRICT),
                         help="This is the local file that you with to remove the duplicate "
                              "settings from.  By default, this file will be read and the updated "
                              "with a minimized version."
                         ).completer = conf_files_completer
    sp_mzg1 = sp_minz.add_mutually_exclusive_group()
    sp_mzg1.add_argument("--dry-run", "-D", default=False, action="store_true",
                         help="Enable dry-run mode.  Instead of writing the minimized value to "
                              "TARGET, show a 'diff' of what would be removed.")
    sp_mzg1.add_argument("--explode-default", "-E", default=False, action="store_true",
                         help="Along with minimizing the same stanza across multiple config files, "
                              "also take into consideration the [default] or global stanza values. "
                              "This can often be use to trim out cruft in savedsearches.conf by "
                              "pointing to etc/system/default/savedsearches.conf, for example.")
    sp_mzg1.add_argument("--output",
                         type=ConfFileType("w", "none", parse_profile=PARSECONF_STRICT),
                         default=None,
                         help="When this option is used, the new minimized file will be saved to "
                              "this file instead of updating TARGET.  This can be use to preview "
                              "changes or helpful in other workflows."
                         ).completer = conf_files_completer
    sp_minz.add_argument("-k", "--preserve-key",
                         action="append", default=[],
                         help="Specify a key that should be allowed to be a duplication but should "
                              "be preserved within the minimized output.  For example the it's"
                              "often desirable keep the 'disabled' settings in the local file, "
                              "even if it's enabled by default.")



    # SUBCOMMAND:  splconf sort <CONF>
    sp_sort = subparsers.add_parser("sort",
                                    help="Sort a Splunk .conf file.  Sorted output can be echoed "
                                         "or files can be sorted inplace.",
                                    description="""\
Sort a Splunk .conf file.  Sort has two modes:  (1) by default, the sorted
config file will be echoed to the screen.  (2) the config files are updated
inplace when the '-i' option is used.

Conf files that are manually managed that you don't ever want sorted can be
'blacklisted' by placing the string 'KSCONF-NO-SORT' in a comment at the top
of the .conf file.

To recursively sort all files:

    find . -name '*.conf' | xargs ksconf sort -i
""",
                                    formatter_class=MyDescriptionHelpFormatter)
    sp_sort.set_defaults(funct=do_sort)

    sp_sort.add_argument("conf", metavar="FILE", nargs="+",
                         type=argparse.FileType('r'), default=[sys.stdin],
                         help="Input file to sort, or standard input."
                         ).completer = conf_files_completer
    group = sp_sort.add_mutually_exclusive_group()
    group.add_argument("--target", "-t", metavar="FILE",
                       type=argparse.FileType('w'), default=sys.stdout,
                       help="File to write results to.  Defaults to standard output."
                       ).completer = conf_files_completer
    group.add_argument("--inplace", "-i",
                       action="store_true", default=False,
                       help="Replace the input file with a sorted version.  Warning this a "
                            "potentially destructive operation that may move/remove comments.")
    sp_sog1 = sp_sort.add_argument_group("In-place update arguments")
    sp_sog1.add_argument("-F", "--force", action="store_true",
                         help="Force file sorting for all files, even for files containing the "
                              "special 'KSCONF-NO-SORT' marker.")
    sp_sog1.add_argument("-q", "--quiet", action="store_true",
                         help="Reduce the output.  Reports only updated or invalid files.  "
                              "This is useful for pre-commit hooks, for example.")
    sp_sort.add_argument("-n", "--newlines", metavar="LINES", type=int, default=1,
                         help="Lines between stanzas.")

    # SUBCOMMAND:  splconf upgrade tarball
    sp_unar = subparsers.add_parser("unarchive",
                                    help="Install or overwrite an existing app in a git-friendly "
                                         "way.  If the app already exist, steps will be taken to "
                                         "upgrade it safely.",
                                    formatter_class=MyDescriptionHelpFormatter)
    # Q:  Should this also work for fresh installs?
    sp_unar.set_defaults(funct=do_unarchive)
    sp_unar.add_argument("tarball", metavar="SPL",
                         help="The path to the archive to install."
                         ).completer = FilesCompleter(allowednames=("*.tgz", "*.tar.gz", "*.spl",
                                                                    "*.zip"))
    sp_unar.add_argument("--dest", metavar="DIR", default=".",
                         help="Set the destination path where the archive will be extracted.  "
                              "By default the current directory is used, but sane values include "
                              "etc/apps, etc/deployment-apps, and so on.  This could also be a "
                              "git repository working tree where splunk apps are stored."
                         ).completer = DirectoriesCompleter()
    sp_unar.add_argument("--app-name", metavar="NAME", default=None,
                         help="The app name to use when expanding the archive.  By default, the "
                              "app name is taken from the archive as the top-level path included "
                              "in the archive (by convention)  Expanding archives that contain "
                              "multiple (ITSI) or nested apps (NIX, ES) is not supported.")
    sp_unar.add_argument("--default-dir", default="default", metavar="DIR",
                         help="Name of the directory where the default contents will be stored.  "
                              "This is a useful feature for apps that use a dynamic default "
                              "directory that's created by the 'combine' mode."
                         ).completer = DirectoriesCompleter()
    sp_unar.add_argument("--exclude", "-e", action="append", default=[],
                         help="Add a file pattern to exclude.  Splunk's psudo-glob "
                              "patterns are supported here.  '*' for any non-directory match, "
                              "'...' for ANY (including directories), and '?' for a single "
                              "character.")
    sp_unar.add_argument("--keep", "-k", action="append", default=[],
                         help="Add a pattern of file to preserve during an upgrade.")
    sp_unar.add_argument("--allow-local", default=False, action="store_true",
                         help="Allow local/ and local.meta files to be extracted from the archive. "
                              "This is a Splunk packaging violation and therefore by default these "
                              "files are excluded.")
    sp_unar.add_argument("--git-sanity-check",
                         choices=["off", "changed", "untracked", "ignored"],
                         default="untracked",
                         help="By default a 'git status' is run on the destination folder to see "
                              "if the working tree or index has modifications before the unarchive "
                              "process starts.  "
                              "The choices go from least restrictive to most thorough: "
                              "Use 'off' to prevent any 'git status' safely checks. "
                              "Use 'changed' to abort only upon local modifications to files "
                              "tracked by git. "
                              "Use 'untracked' (by default) to look for changed and untracked "
                              "files before considering the tree clean. "
                              "Use 'ignored' to enable the most intense safety check which will "
                              "abort if local changes, untracked, or ignored files are found. "
                              "(These checks are automatically disabled if the app is not in a git "
                              "working tree, or git is not present.)")
    sp_unar.add_argument("--git-mode", default="stage",
                         choices=["nochange", "stage", "commit"],
                         help="Set the desired level of git integration.  "
                              "The default mode is 'stage', where new, updated, or removed files "
                              "are automatically handled for you.  If 'commit' mode is selected, "
                              "then files are committed with an  auto-generated commit message.  "
                              "To prevent any 'git add' or 'git rm' commands from being run, pick "
                              "the 'nochange' mode. "
                              "  Notes:  "
                              "(1) The git mode is irrelevant if the app is not in a git working "
                              "tree.  "
                              "(2) If a git commit is incorrect, simply roll it back with "
                              "'git reset' or fix it with a 'git commit --amend' before the "
                              "changes are pushed anywhere else.  (That's why you're using git in "
                              "the first place, right?)")
    sp_unar.add_argument("--no-edit",
                         action="store_true", default=False,
                         help="Tell git to skip opening your editor.  By default you will be "
                              "prompted to review/edit the commit message.  (Git Tip:  Delete the "
                              "content of the message to abort the commit.)")
    sp_unar.add_argument("--git-commit-args", "-G", default=[], action="append")

    autocomplete(parser)
    args = parser.parse_args(argv)

    global FORCE_TTY_COLOR
    FORCE_TTY_COLOR = args.force_color

    try:
        return_code = args.funct(args)
    except Exception, e:
        sys.stderr.write("Unhandled top-level exception.  {0}\n".format(e))
        raise
        return_code = EXIT_CODE_INTERNAL_ERROR

    if _unittest:
        return return_code or 0
    else:
        sys.exit(return_code or 0)




if __name__ == '__main__':
    cli()
