import os
import re
import shutil
import sys
from glob import glob

from ksconf.consts import SMART_CREATE, SMART_NOCHANGE, SMART_UPDATE
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


def _expand_glob_list(iterable):
    for item in iterable:
        if "*" in item or "?" in item:
            for match in glob(item):
                yield match
        else:
            yield item


_glob_to_regex = {
    r"\*": r"[^/\\]*",
    r"\?": r".",
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
