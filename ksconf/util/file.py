from __future__ import absolute_import, unicode_literals

import filecmp
import os
import re
import shutil
import sys
from contextlib import contextmanager
from glob import glob
from io import open
from pathlib import Path
from random import randint
from typing import IO, Callable, Iterable, List, Tuple, Union

from ksconf.consts import SMART_CREATE, SMART_NOCHANGE, SMART_UPDATE, is_debug
from ksconf.types import PathType
from ksconf.util.compare import file_compare


def _is_binary_file(filename, peek=2048):
    # https://stackoverflow.com/a/7392391/315892
    textchars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
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
        regex = f"^{regex}$"
    return re.compile(regex, flags=re_flags)


def splglob_simple(pattern):
    """ Return a splglob that either matches a full path or match a simple file """
    if "/" not in pattern:
        # Assume we've been given a simple file name:   app.conf, *.tgz
        pattern = f"^.../{pattern}$"
    else:
        pattern = f"^{pattern}$"
    return pattern


def relwalk(top: PathType,
            topdown=True, onerror=None, followlinks=False
            ) -> Iterable[Tuple[str, List[str], List[str]]]:
    """ Relative path walker
    Like os.walk() except that it doesn't include the "top" prefix in the resulting 'dirpath'.
    """
    top = os.fspath(top)
    if not top.endswith(os.path.sep):
        top += os.path.sep
    prefix = len(top)
    for (dirpath, dirnames, filenames) in os.walk(top, topdown, onerror, followlinks):
        dirpath = dirpath[prefix:]
        yield (dirpath, dirnames, filenames)


def file_hash(path: PathType, algorithm="sha256") -> str:
    import hashlib
    h = hashlib.new(algorithm)
    with open(path, "rb") as fp:
        buf = True
        while buf:
            buf = fp.read(4096)
            h.update(buf)
    return h.hexdigest()


def _samefile(file1: PathType, file2: PathType) -> bool:
    if hasattr(os.path, "samefile"):
        # Nix
        return os.path.samefile(file1, file2)
    else:
        # Windows
        file1 = os.path.normpath(os.path.normcase(file1))
        file2 = os.path.normpath(os.path.normcase(file2))
        return file1 == file2


def secure_delete(path: Path, passes=3):
    """
    A simple file shred technique.  If there's demand, this could be expanded.
    But for now, 'secure' means just slightly more secure that unlink().

    Adapted from from Ansible's _shred_file_custom()
    """
    path = Path(path)
    file_len = path.stat().st_size
    if file_len == 0:
        # avoid work when empty
        return
    max_chunk_len = min(1024 * 1024 * 2, file_len)
    with open(path, "wb") as fh:
        for _ in range(passes):
            fh.seek(0, 0)
            # get a random chunk of data, each pass with other length
            chunk_len = randint(max_chunk_len // 2, max_chunk_len)
            data = os.urandom(chunk_len)

            for _ in range(0, file_len // chunk_len):
                fh.write(data)
            fh.write(data[:file_len % chunk_len])
            os.fsync(fh)
    path.unlink()


@contextmanager
def atomic_writer(dest: Path,
                  temp_name: Union[Path, str, Callable[[Path], Path], None]) -> Path:
    """
    Context manager to atomically update a destination.  When entering the context, a temporary file
    name is returned.  When the context is successfully exited, the temporary file is renamed into
    place.  Either way, the temporary file is removed.

    The name of the temporary file can be controlled via ``temp_name``.  If a ``str`` is provided,
    it will be used as a suffix.  If a Path is provided, that will be used as the literal temporary
    file name.  If a callable is given, the ``dest`` path will be passed into the callable to
    determine the temporary file.  Alternatively, the entire _atomic_ nature of this function can be
    disabled by passing temp_name=None.
    """
    dest = Path(dest)

    if temp_name is None:
        # Opt-out of temp file handling.  Just write directly to the real destination.
        yield dest
        return

    if isinstance(temp_name, str):
        # Suffix mode:  Concatenate 'temp_name' to existing name
        if not temp_name.startswith("."):
            temp_name = "." + temp_name
        temp_dest: Path = dest.with_name(dest.name + temp_name)
    elif isinstance(temp_name, Path):

        # The actual temp file name was created by the caller
        temp_dest = temp_name
    elif callable(temp_name):
        # Temp filename to be generated via function call
        temp_dest = Path(temp_name(dest))
    else:
        raise TypeError("Unsupported type for 'temp_name'.  "
                        f"Expected str, Path, or callable but received {type(temp_name).__name__}")

    if dest == temp_dest:
        # If you want to write directly to the output file, use temp_name=None
        # Having dest==temp_dest will result in all files being removed.
        raise ValueError(f"Invalid options.  Both dest and temp_dest are the same:  {dest}")

    # Remove any existing temporary files.
    if temp_dest.is_file():
        temp_dest.unlink()

    try:
        yield temp_dest
        assert temp_dest.is_file(), f"No file written to the temporary path {temp_dest}, " \
                                    f"therefore we cannot rename it to {dest}"
        if dest.is_file():
            dest.unlink()
        temp_dest.replace(dest)
    finally:
        if temp_dest.is_file():
            temp_dest.unlink()


@contextmanager
def atomic_open(name: Path,
                temp_name: Union[Path, str, Callable[[Path], Path], None],
                mode="w",
                **open_kwargs) -> IO:
    """
    Context manager to atomically write to a file stream.  Like the open() context manager, a file
    handle returned when the context is entered.  Upon successful completion, the temporary file is
    renamed into place; thus providing an atomic update operation.

    See :func:`atomic_writer` for behaviors regarding the ``temp_name`` parameter option.

    This function can be used nearly any place that ``with open(myfile, mode="w") as stream``
    """
    with atomic_writer(name, temp_name) as tmp_filename:
        with open(tmp_filename, mode=mode, **open_kwargs) as stream:
            yield stream


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
            if is_debug():
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
