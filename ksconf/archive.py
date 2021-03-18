from __future__ import absolute_import, unicode_literals

import os
from collections import namedtuple
from fnmatch import fnmatch

from ksconf.consts import RegexType

GenArchFile = namedtuple("GenericArchiveEntry", ("path", "mode", "size", "payload"))


def extract_archive(archive_name, extract_filter=None):
    if extract_filter is not None and not callable(extract_filter):  # pragma: no cover
        raise ValueError("extract_filter must be a callable!")
    if archive_name.lower().endswith(".zip"):
        return _extract_zip(archive_name, extract_filter)
    else:
        return _extract_tar(archive_name, extract_filter)


def gaf_filter_name_like(pattern):
    def filter(gaf):
        filename = os.path.basename(gaf.path)
        return fnmatch(filename, pattern)

    return filter


def _extract_tar(path, extract_filter=None, encoding="utf-8"):
    import tarfile
    with tarfile.open(path, "r", encoding=encoding) as tar:
        for ti in tar:
            if not ti.isreg():
                '''
                print "Skipping {}  ({})".format(ti.name, ti.type)
                '''
                continue
            mode = ti.mode & 0o777
            # PY2 doesn't return unicode file names
            if hasattr(ti.name, "decode"):
                ti.name = ti.name.decode(encoding)
            if extract_filter is None or \
                    extract_filter(GenArchFile(ti.name, mode, ti.size, None)):
                tar_file_fp = tar.extractfile(ti)
                buf = tar_file_fp.read()
            else:
                buf = None
            yield GenArchFile(ti.name, mode, ti.size, buf)


def _extract_zip(path, extract_filter=None, mode=0o644, encoding="latin"):
    # Note:  No encoding defined for Zip file spec.  Sticking with what WinZip uses by default.
    import zipfile
    with zipfile.ZipFile(path, mode="r") as zipf:
        for zi in zipf.infolist():
            if hasattr(zi.filename, "decode"):
                zi.filename = zi.filename.decode(encoding)
            if zi.filename.endswith('/'):
                # Skip directories
                continue
            if extract_filter is None or \
                    extract_filter(GenArchFile(zi.filename, mode, zi.file_size, None)):
                payload = zipf.read(zi)
            else:
                payload = None
            yield GenArchFile(zi.filename, mode, zi.file_size, payload)


def sanity_checker(iterable):
    for gaf in iterable:
        if gaf.path.startswith("/") or ".." in gaf.path:
            raise ValueError("Bad path found in archive:  {}".format(gaf.path))
        yield gaf


def gen_arch_file_remapper(iterable, mapping):
    # Mapping is assumed to be a sequence of (find,replace) strings; find can be compiled regex
    for gaf in iterable:
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
