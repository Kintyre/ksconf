from __future__ import absolute_import, unicode_literals

import filecmp
import os
import re
import shutil
import sys
from glob import glob
from io import open

from ksconf.consts import KSCONF_DEBUG, SMART_CREATE, SMART_NOCHANGE, SMART_UPDATE
from ksconf.util.compare import file_compare


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


def file_fingerprint(path, compare_to=None):
    stat = os.stat(path)
    fp = (stat.st_mtime, stat.st_size)
    if compare_to:
        return fp != compare_to
    else:
        return fp


def expand_glob_list(iterable, do_sort=False):
    for item in iterable:
        if "*" in item or "?" in item:
            glob_expanded = glob(item)
            if do_sort:
                glob_expanded.sort()
            for match in glob_expanded:
                yield match
        else:
            yield item


# This is a Splunk-style (props) stanza style glob:
# where '*' is a single path component, and '...' or '**' means any depth
_glob_to_regex = [
    ("**", r".*"),
    ("*", r"[^/\\]*"),
    ("?", r"."),
    ("...", r".*"),
    (".", r"\."),
]
_glob_to_regex_find = "({})".format("|".join(re.escape(r) for r, _ in _glob_to_regex))


def splglob_to_regex(pattern, re_flags=None):
    glob_to_regex = dict(_glob_to_regex)
    regex = re.sub(_glob_to_regex_find, lambda m: glob_to_regex[m.group()], pattern)
    # If NO anchors have been explicitly given, then assume full-match mode:
    if not re.search(r'(?<![\[\\])[$^]', regex):
        regex = "^{}$".format(regex)
    return re.compile(regex, flags=re_flags)


def splglob_simple(pattern):
    """ Return a splglob that either matches a full path or match a simple file """
    if "/" not in pattern:
        # Assume we've been given a simple file name:   app.conf, *.tgz
        pattern = "^.../{}$".format(pattern)
    else:
        pattern = "^{}$".format(pattern)
    return pattern


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


def file_hash(path, algorithm="sha256"):
    import hashlib
    h = hashlib.new(algorithm)
    with open(path, "rb") as fp:
        buf = True
        while buf:
            buf = fp.read(4096)
            h.update(buf)
    return h.hexdigest()


def _samefile(file1, file2):
    if hasattr(os.path, "samefile"):
        # Nix
        return os.path.samefile(file1, file2)
    else:
        # Windows
        file1 = os.path.normpath(os.path.normcase(file1))
        file2 = os.path.normpath(os.path.normcase(file2))
        return file1 == file2


class ReluctantWriter:
    """
    Context manager to intelligently handle updates to an existing file.  New content is written
    to a temp file, and then compared to the current file's content.  The file file will be
    overwritten only if the contents changed.
    """

    def __init__(self, path, *args, **kwargs):
        self.path = path
        self._arg = (args, kwargs)
        self._fp = None
        self._tmpfile = path + ".tmp"
        self.change_needed = None
        self.result = None

    def __enter__(self):
        args, kwargs = self._arg
        self._fp = open(self._tmpfile, *args, **kwargs)
        return self._fp

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Don't do anything, other than try to close/delete the file, if an error occurred.
        try:
            self._fp.close()
        except Exception:
            raise
        if exc_type:
            if KSCONF_DEBUG in os.environ:
                # LOG that temp file is being kept
                pass
            else:
                os.unlink(self._tmpfile)
            return
        if not os.path.isfile(self.path):
            os.rename(self._tmpfile, self.path)
            self.change_needed = True
            self.result = "created"
        elif filecmp.cmp(self._tmpfile, self.path):
            os.unlink(self._tmpfile)
            self.change_needed = False
            self.result = "unchanged"
        else:
            os.unlink(self.path)
            os.rename(self._tmpfile, self.path)
            self.change_needed = True
            self.result = "updated"
