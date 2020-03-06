from __future__ import absolute_import
from __future__ import unicode_literals

import filecmp
import os
import re
import shutil
import sys
from glob import glob
from io import open

from ksconf.consts import SMART_CREATE, SMART_NOCHANGE, SMART_UPDATE, KSCONF_DEBUG
from ksconf.util.compare import file_compare
from ksconf.ext.six.moves import range


try:
    # Builtin in Python 3.3+
    from shutil import where
except ImportError:
    # Borrowed from Python's stdlib 3.7 shutil.py; comments removed to keep this short

    def which(cmd, mode=os.F_OK | os.X_OK, path=None):
        """Given a command, mode, and a PATH string, return the path which
        conforms to the given mode on the PATH, or None if there is no such
        file.
        `mode` defaults to os.F_OK | os.X_OK. `path` defaults to the result
        of os.environ.get("PATH"), or can be overridden with a custom search
        path.
        """
        def _access_check(fn, mode):
            return (os.path.exists(fn) and os.access(fn, mode)
                    and not os.path.isdir(fn))
        if os.path.dirname(cmd):
            if _access_check(cmd, mode):
                return cmd
            return None

        if path is None:
            path = os.environ.get("PATH", None)
            if path is None:
                try:
                    path = os.confstr("CS_PATH")
                except (AttributeError, ValueError):
                    # os.confstr() or CS_PATH is not available
                    path = os.defpath
        # PATH='' doesn't match, whereas PATH=':' looks in the current directory
        if not path:
            return None
        path = path.split(os.pathsep)

        if sys.platform == "win32":
            # The current directory takes precedence on Windows.
            if not os.curdir in path:
                path.insert(0, os.curdir)

            # PATHEXT is necessary to check on Windows.
            pathext = os.environ.get("PATHEXT", "").split(os.pathsep)
            if any(cmd.lower().endswith(ext.lower()) for ext in pathext):
                files = [cmd]
            else:
                files = [cmd + ext for ext in pathext]
        else:
            files = [cmd]

        seen = set()
        for dir in path:
            normdir = os.path.normcase(dir)
            if not normdir in seen:
                seen.add(normdir)
                for thefile in files:
                    name = os.path.join(dir, thefile)
                    if _access_check(name, mode):
                        return name
        return None



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


def expand_glob_list(iterable):
    for item in iterable:
        if "*" in item or "?" in item:
            for match in glob(item):
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


def file_hash(path, algorithm="sha256"):
    import hashlib
    h = hashlib.new(algorithm)
    with open(path, "rb") as fp:
        buf = fp.read(4096)
        while buf:
            h.update(buf)
            buf = fp.read(4096)
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
