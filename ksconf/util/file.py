from __future__ import absolute_import, unicode_literals

import filecmp
import os
import re
import shutil
import sys
from glob import glob
from io import open
from pathlib import Path, PurePath


from ksconf.consts import SMART_CREATE, SMART_NOCHANGE, SMART_UPDATE, KSCONF_DEBUG
from ksconf.util.compare import file_compare
from ksconf.ext.six import text_type
from ksconf.ext.six.moves import range


def _path_to_str(p):
    if isinstance(p, PurePath):
        return text_type(p)
    if isinstance(p, tuple):
        return tuple(_path_to_str(i) for i in p)
    if isinstance(p, list):
        return [_path_to_str(i) for i in p]
    return p


def pathlib_compat(f):
    if sys.version_info < (3, 6):
        from functools import wraps

        @wraps(f)
        def wrapper(*args, **kwargs):
            args = [_path_to_str(p) for p in args]
            kwargs = {k: _path_to_str(v) for k, v in kwargs.items()}
            return f(*args, **kwargs)
        return wrapper
    else:
        return f


@pathlib_compat
def _is_binary_file(filename, peek=2048):
    # https://stackoverflow.com/a/7392391/315892; modified for Python 2.6 compatibility
    textchars = bytearray(set([7, 8, 9, 10, 12, 13, 27]) | set(range(0x20, 0x100)) - set([0x7f]))
    with open(filename, "rb") as f:
        b = f.read(peek)
        return bool(b.translate(None, textchars))


_dir_exists_cache = set()


@pathlib_compat
def dir_exists(directory):
    """ Ensure that the directory exists """
    # This works as long as we never call os.chdir()
    if directory in _dir_exists_cache:
        return
    if not os.path.isdir(directory):
        os.makedirs(directory)
    _dir_exists_cache.add(directory)


@pathlib_compat
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


@pathlib_compat
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


# This is a Splunk-style (props) stanza style glob:  where '* is a single path component, and '...' means any level of path
_glob_to_regex = {
    r"\*": r"[^/\\]*",
    r"\?": r".",
    r"\.\.\.": r".*",
}
_is_glob_re = re.compile("({})".format("|".join(list(_glob_to_regex.keys()))))


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


@pathlib_compat
def file_hash(path, algorithm="sha256"):
    import hashlib
    h = hashlib.new(algorithm)
    with open(path, "rb") as fp:
        buf = True
        while buf:
            buf = fp.read(4096)
            h.update(buf)
    return h.hexdigest()


@pathlib_compat
def _samefile(file1, file2):
    if hasattr(os.path, "samefile"):
        # Nix
        return os.path.samefile(file1, file2)
    else:
        # Windows
        file1 = os.path.normpath(os.path.normcase(file1))
        file2 = os.path.normpath(os.path.normcase(file2))
        return file1 == file2


class ReluctantWriter(object):
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
        except:
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
