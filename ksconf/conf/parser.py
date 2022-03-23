"""

Parse and write Splunk's .conf files


According to this doc:

https://docs.splunk.com/Documentation/Splunk/7.2.3/Admin/Howtoeditaconfigurationfile

 1.  Comments must start at the beginning of a line (#)
 2.  Comments may not be after a stanza name or on an attribute's value
 3.  Supporting encoding is UTF-8 (and therefore ASCII too)

"""

import codecs
import os
import re
from enum import Enum
from io import StringIO, open
from os import PathLike
from typing import Dict, Generator, Iterable, List, TextIO, Tuple, Union

from ..consts import SmartEnum
from ..util.compare import fileobj_compare

default_encoding = "utf-8"


# Type definitions

StanzaType = Dict[str, str]
ConfType = Dict[str, StanzaType]
PathType = Union[PathLike, str]
_StreamInput = Union[TextIO, Iterable[str]]
_StreamOutput = Union[PathType, TextIO]
_StreamNameFile = Union[PathType, _StreamInput]
ParserConfig = Dict


class Token:
    """ Immutable token object.  deepcopy returns the same object """

    def __deepcopy__(self, memo):
        memo[id(self)] = self
        return self

    # Always sort to the top of the list (should only ever be GLOBAL stanza)
    def __lt__(self, other):
        return isinstance(other, str)

    def __gt__(self, other):
        return not isinstance(other, str)


class DuplicateEnum(Enum):
    OVERWRITE = "overwrite"
    MERGE = "merge"
    EXCEPTION = "exception"


# Legacy names
DUP_OVERWRITE = DuplicateEnum.OVERWRITE
DUP_MERGE = DuplicateEnum.MERGE
DUP_EXCEPTION = DuplicateEnum.EXCEPTION

GLOBAL_STANZA = Token()

# Parsing configuration profiles

PARSECONF_MID = dict(
    keep_comments=True,
    dup_stanza=DUP_EXCEPTION,
    dup_key=DUP_OVERWRITE,
    strict=True)

PARSECONF_MID_NC = dict(
    keep_comments=False,  # No comments
    dup_stanza=DUP_EXCEPTION,
    dup_key=DUP_OVERWRITE,
    strict=True)

PARSECONF_LOOSE = dict(
    keep_comments=False,
    dup_stanza=DUP_MERGE,
    dup_key=DUP_MERGE,
    strict=False)

PARSECONF_STRICT = dict(
    keep_comments=True,
    dup_stanza=DUP_EXCEPTION,
    dup_key=DUP_EXCEPTION,
    strict=True)

PARSECONF_STRICT_NC = dict(
    keep_comments=False,  # No comment
    dup_stanza=DUP_EXCEPTION,
    dup_key=DUP_EXCEPTION,
    strict=True)


class ConfParserException(Exception):
    pass


class DuplicateKeyException(ConfParserException):
    pass


class DuplicateStanzaException(ConfParserException):
    pass


####################################################################################################
# Core parsing / conf file writing logic


def section_reader(stream: Iterable[str],
                   section_re: re.Pattern = re.compile(r'^[\s\t]*\[(.*)\]\s*$')
                   ) -> Generator[Tuple[str, List[str]], None, None]:
    """
    This generator break a configuration file stream into sections.  Each section contains a name
    and a list of text lines held within that section.

    Sections that have no entries must be preserved.  Any lines before the first section are send back
    with the section name of None.

    :param stream: configuration file input stream
    :type stream: file
    :param section_re: regular expression for detecting stanza headers
    :return: sections in the form of `(section_name, lines_of_text)`
    :rtype: tuple
    """
    buf = []
    section = None
    for line in stream:
        line = line.rstrip("\r\n")
        match = section_re.match(line)
        if match:
            yield section, buf
            section = match.group(1)
            buf = []
        else:
            buf.append(line)
    if section or buf:
        yield section, buf


def _detect_lite(byte_str: bytes) -> Dict[str, str]:
    """ A super simple drop-in replacement for chardet.detect(byte_str) that ONLY looks for BOM or
    assumes "utf-8".
    If someday the full chardet features are needed, we could use this for optional (opportunistic)
    chardet support with this as the local fall-back function. """
    # https://stackoverflow.com/a/24370596/315892
    # UTF-8 BOM is 3 bytes, UTF-16 is 2 bytes, UTF-32 is 4 bytes
    for (enc, boms) in (
            ('utf-8-sig', (codecs.BOM_UTF8,)),
            ('utf-16', (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)),
            ('utf-32', (codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE))):
        if any(byte_str.startswith(bom) for bom in boms):
            return {"encoding": enc}
    return {"encoding": default_encoding}


""" # Not ready for this approach yet!  (more testing scenarios required)
try:
    from chardet import detect
else:
    _detect_lite = detect
"""


def detect_by_bom(path: PathType) -> str:
    with open(path, 'rb') as f:
        raw = f.read(4)    # will read less if the file is smaller
    encoding = _detect_lite(raw)
    return encoding["encoding"]


def cont_handler(iterable: Iterable[str],
                 continue_re: re.Pattern = re.compile(r"^(.*)\\$"),
                 breaker: str = "\n"
                 ) -> Generator[str, None, None]:
    r"""
    Look for trailing backslashes ("`\\`") which indicate a value for an attribute is split across
    multiple lines.  This function will group such lines together, and pass all other lines through
    as-is.  Note that the continuation character must be the very last character on the line,
    trailing whitespace is not allowed.

    :param iterable: lines from a configuration file
    :type iterable: iter
    :param continue_re: regular expression to detect the continuation character
    :param breaker: joining string when combining continued lines into a single string.
           Default '`\\n`'
    :return: lines of text
    :rtype: str
    """
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
    if buf:  # pragma: no cover
        # Weird this generally shouldn't happen.
        yield buf


def splitup_kvpairs(lines: Iterable[str],
                    comments_re: re.Pattern = re.compile(r"^\s*[#;]"),
                    keep_comments: bool = False,
                    strict: bool = False
                    ) -> Generator[Tuple[str, str], None, None]:
    """
    Break up 'attribute=value' entries in a configuration file.

    :param lines: the body of a stanza containing associated attributes and values
    :type lines: iter
    :param comments_re: Regular expression used to detect comments.
    :param keep_comments: Should comments be preserved in the output.  Defaults to `False`.
    :type keep_comments: bool, optional
    :param strict: Should unknown content in the stanza stop processing.  Defaults to `False`
                   allowing "junk" to be silently ignored for a best-effort parse.
    :type strict: bool, optional
    :return: iterable of (attribute,value) tuples
    """
    comment = 0
    for entry in lines:
        if comments_re.search(entry):
            if keep_comments:
                comment += 1
                yield f"#-{comment:06d}", entry
        elif "=" in entry:
            k, v = entry.split("=", 1)
            yield k.rstrip(), v.lstrip()
        elif re.search(r'^\s*\[|\]\s*$', entry):
            # ToDo:  There should be a 'loose' mode that allows this to be ignored...
            raise ConfParserException(f"Dangling stanza header:  {entry}")
        elif strict and entry.strip():
            #  if entry == "\ufeff": continue # UTF-8 BOM read as UTF-8;  But this ONLY works for PY3
            raise ConfParserException(f"Unexpected entry:  {entry!r}")


def parse_conf(stream: _StreamNameFile,
               profile: ParserConfig = PARSECONF_MID,
               encoding: str = None
               ) -> ConfType:
    """
    Parse a .conf file.  This is a wrapper around :func:`parse_conf_stream` that allows filenames
    or stream to be passed in.

    :param stream: the path to a configuration file or open file-like object to be parsed
    :type stream: str, file
    :param profile: parsing configuration settings
    :param encoding: Defaults to the system default, (Often "utf-8")
    :return: a mapping of the stanza and attributes.
             The resulting output is accessible as [stanza][attribute] -> value
    :rtype: dict
    """
    try:
        # Placeholder stub for an eventual migration to proper class-oriented parser
        if hasattr(stream, "read"):
            return parse_conf_stream(stream, **profile)
        else:
            if not encoding:
                encoding = detect_by_bom(stream)
            # Assume it's a filename
            with open(stream, "r", encoding=encoding) as stream:
                return parse_conf_stream(stream, **profile)
    except UnicodeDecodeError as e:
        raise ConfParserException(f"Encoding error encountered: {e}")


def parse_conf_stream(stream: _StreamInput,
                      keys_lower: bool = False,
                      handle_conts: bool = True,
                      keep_comments: bool = False,
                      dup_stanza: DuplicateEnum = DUP_EXCEPTION,
                      dup_key: DuplicateEnum = DUP_OVERWRITE,
                      strict: bool = False) -> ConfType:
    if hasattr(stream, "name"):
        stream_name = stream.name
    else:
        stream_name = repr(stream)

    sections = {}
    # Q: What's the value of allowing line continuations to be disabled?
    if handle_conts:
        stream = cont_handler(stream)
    for section, entry in section_reader(stream):
        if section is None:
            section = GLOBAL_STANZA
        if section in sections:
            if dup_stanza == DUP_OVERWRITE:
                s = sections[section] = {}
            elif dup_stanza == DUP_EXCEPTION:
                raise DuplicateStanzaException(
                    f"Stanza [{_format_stanza(section)}] found more than once "
                    f"in config file {stream_name}")
            elif dup_stanza == DUP_MERGE:
                s = sections[section]
            else:
                raise TypeError(f"Unknown value '{dup_stanza}' for dup_stanza")
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
                    raise DuplicateKeyException(
                        f"Stanza [{_format_stanza(section)}] has duplicate "
                        f"key '{key}' in file {stream_name}")
            else:
                local_stanza[key] = value
                s[key] = value
        del s
    # If the global entry is just a blank line, drop it
    if GLOBAL_STANZA in sections:
        g = sections[GLOBAL_STANZA]
        if not g:
            # if len(g) == 1 and not g[0]:
            del sections[GLOBAL_STANZA]
    return sections


def write_conf(stream: _StreamOutput,
               conf: ConfType,
               stanza_delim: str = "\n",
               sort: bool = True,
               mtime: float = None):
    if not hasattr(stream, "write"):
        # Assume it's a filename
        with open(stream, "w", encoding=default_encoding) as stream:
            write_conf_stream(stream, conf, stanza_delim, sort)
            if mtime:
                os.utime(stream, (mtime, mtime))
    else:
        write_conf_stream(stream, conf, stanza_delim, sort)


def write_conf_stream(stream: TextIO,
                      conf: ConfType,
                      stanza_delim: str = "\n",
                      sort: bool = True):
    if sort:
        sorter = sorted
    else:
        sorter = list

    def write_stanza_body(stanza: dict):
        for (key, value) in sorter(stanza.items()):
            if value is None:
                value = ""
            else:
                value = str(value)
            if key.startswith("#"):
                stream.write(f"{value}\n")
            elif value:
                value = value.replace("\n", "\\\n")
                stream.write(f"{key} = {value}\n")
            else:
                # Avoid a trailing whitespace to keep the git gods happy
                stream.write(f"{key} =\n")

    keys = sorter(conf)
    while keys:
        section = keys.pop(0)
        cfg = conf[section]
        if section is not GLOBAL_STANZA:
            stream.write(f"[{section}]\n")
        write_stanza_body(cfg)
        if keys:
            stream.write(stanza_delim)


def smart_write_conf(filename: PathType,
                     conf: ConfType,
                     stanza_delim: str = "\n",
                     sort: bool = True,
                     temp_suffix: str = ".tmp",
                     mtime: float = None) -> SmartEnum:
    if os.path.isfile(filename):
        temp = StringIO()
        write_conf_stream(temp, conf, stanza_delim, sort)
        with open(filename, encoding=default_encoding) as dest:
            file_diff = fileobj_compare(temp, dest)
        if file_diff:
            return SmartEnum.NOCHANGE
        else:
            tempfile = filename + temp_suffix
            with open(tempfile, "w", encoding=default_encoding) as dest:
                dest.write(temp.getvalue())
            if mtime:
                os.utime(tempfile, (mtime, mtime))
            os.unlink(filename)
            os.rename(tempfile, filename)
            return SmartEnum.UPDATE
    else:
        tempfile = filename + temp_suffix
        with open(tempfile, "w", encoding=default_encoding) as dest:
            write_conf_stream(dest, conf, stanza_delim, sort)
        if mtime:
            os.utime(tempfile, (mtime, mtime))
        os.rename(tempfile, filename)
        return SmartEnum.CREATE


def _format_stanza(stanza: Union[str, Token]) -> str:
    """ Return a more human readable stanza name."""
    if stanza is GLOBAL_STANZA:
        return "GLOBAL"
    else:
        return stanza


def _extract_comments(section: StanzaType) -> List[str]:
    """ Return a sequential list of comments REMOVED from a section dict """
    comments = []
    for key, value in sorted(section.items()):
        if key.startswith("#-"):
            comments.append(value)
            del section[key]
    return comments


def inject_section_comments(section: StanzaType,
                            prepend: str = None,
                            append: str = None):
    """
    Extract existing comments from section dict (in order; and remove them)
    Add in any prepend/append comments (if that comment isn't already present)
    Re-inject comments back into the section dict with fresh numbering
    """
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
        section[f"#-{i:06d}"] = comment


def _drop_stanza_comments(stanza: StanzaType) -> StanzaType:
    n = {}
    for (key, value) in stanza.items():
        if key.startswith("#"):
            continue
        n[key] = value
    return n


def conf_attr_boolean(value: Union[str, bool, int]) -> bool:
    if isinstance(value, bool):
        return value
    elif isinstance(value, str):
        value = value.lower()
        if value in ("1", "t", "y", "true", "yes"):
            return True
        elif value in ("0", "f", "n", "false", "no"):
            return False
        else:
            raise ValueError(f"Can't convert {value!r} to a boolean.")
    elif isinstance(value, int):
        if value == 0:
            return False
        elif value == 1:
            # Technically any non-0 is true; but that's unusual in typical config files.
            # Let's keep the logic the same as how stings are handled:  Only '1' as true.
            return True
        else:
            raise ValueError(f"Can't convert {value!r} to a boolean.")
    else:
        raise ValueError(f"Can't convert type {type(value)} to a boolean.")


class update_conf:
    """
    Context manager that allows for simple in-place updates to conf files.
    This provides a simple dict-like interface for easy updates.

    Usage example:

    ..  code-block:: py

            with update_conf("app.conf") as conf:
                conf["launcher"]["version"] = "1.0.2"
                conf["install"]["build"] = 33

    :param str conf_path: Path to ``.conf`` file to be edited.
    :param dict profile:  Parsing settings and strictness profile.
    :param str encoding:  encoding to use for file operations.
    :param bool make_missing:  When true, a new blank configuration file will be created
                               with the updates rather than raising an exception.
    """

    def __init__(self, conf_path: PathType,
                 profile: ParserConfig = PARSECONF_MID,
                 encoding: str = None,
                 make_missing: bool = False):
        self.path = conf_path
        self.profile = profile
        self.encoding = encoding
        self.make_missing = make_missing
        self._data: ConfType = None

    def __enter__(self):
        if not os.path.isfile(self.path) and self.make_missing:
            self._data = {}
        else:
            self._data = parse_conf(self.path, self.profile, self.encoding)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            # No update since an exception was raised
            return
        if self.make_missing:
            parent = os.path.dirname(self.path)
            if not os.path.isdir(parent):
                os.makedirs(parent)
        smart_write_conf(self.path, self._data, sort=True)

    def __getitem__(self, item: str) -> StanzaType:
        return self._data[item]

    def __setitem__(self, key: str, value: StanzaType):
        self._data[key] = value
        return value

    def __contains__(self, item):
        return item in self._data

    def __iter__(self) -> Iterable[str]:
        return iter(self._data)

    def keys(self) -> List[str]:
        return list(self._data)

    def update(self, *args, **kwargs):
        self._data.update(*args, **kwargs)
