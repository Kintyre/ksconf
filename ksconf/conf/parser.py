import codecs
import os
import re
from StringIO import StringIO

from ..consts import SMART_NOCHANGE, SMART_UPDATE, SMART_CREATE
from ..util.compare import fileobj_compare


class Token(object):
    """ Immutable token object.  deepcopy returns the same object """

    def __deepcopy__(self, memo):
        memo[id(self)] = self
        return self


DUP_OVERWRITE = "overwrite"
DUP_MERGE = "merge"

GLOBAL_STANZA = Token()

# Parsing configuration profiles

DUP_EXCEPTION = "exception"
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
## Core parsing / conf file writing logic


def section_reader(stream, section_re=re.compile(r'^[\s\t]*\[(.*)\]\s*$')):
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


def bom_handler(iterable):
    # Strip out aany UTF BOM markers, if present.
    item = iterable.next()
    yield item.lstrip(codecs.BOM_UTF8)
    for item in iterable:
        yield item
    # Py 3 something...
    # yield iterable


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
    if buf:  # pragma: no cover
        # Weird this generally shouldn't happen.
        yield buf


def splitup_kvpairs(lines, comments_re=re.compile(r"^\s*[#;]"), keep_comments=False, strict=False):
    comment = 0
    for entry in lines:
        if comments_re.search(entry):
            if keep_comments:
                comment += 1
                yield ("#-%06d" % comment, entry)
        elif "=" in entry:
            k, v = entry.split("=", 1)
            yield k.rstrip(), v.lstrip()
        elif re.search('^\s*\[|\]\s*$', entry):
            # ToDo:  There should be a 'loose' mode that allows this to be ignored...
            raise ConfParserException("Dangling stanza header:  {0}".format(entry))
        elif strict and entry.strip():
            raise ConfParserException("Unexpected entry:  {0}".format(entry))


def parse_conf(stream, profile=PARSECONF_MID):
    # Placeholder stub for an eventual migration to proper class-oriented parser
    if hasattr(stream, "read"):
        return parse_conf_stream(stream, **profile)
    else:
        # Assume it's a filename
        with open(stream, "r") as stream:
            return parse_conf_stream(stream, **profile)


def parse_conf_stream(stream, keys_lower=False, handle_conts=True, keep_comments=False,
                dup_stanza=DUP_EXCEPTION, dup_key=DUP_OVERWRITE, strict=False):
    if hasattr(stream, "name"):
        stream_name = stream.name
    else:
        stream_name = repr(stream)

    sections = {}
    # Q: What's the value of allowing line continuations to be disabled?
    if handle_conts:
        reader = section_reader(cont_handler(bom_handler(stream)))
    else:
        reader = section_reader(bom_handler(stream))
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
    # If the global entry is just a blank line, drop it
    if GLOBAL_STANZA in sections:
        g = sections[GLOBAL_STANZA]
        if not g:
            # if len(g) == 1 and not g[0]:
            del sections[GLOBAL_STANZA]
    return sections


def write_conf(stream, conf, stanza_delim="\n", sort=True):
    if not hasattr(stream, "write"):
        # Assume it's a filename
        with open(stream, "w") as stream:
            write_conf_stream(stream, conf, stanza_delim, sort)
    else:
        write_conf_stream(stream, conf, stanza_delim, sort)


def write_conf_stream(stream, conf, stanza_delim="\n", sort=True):
    conf = dict(conf)

    if sort:
        sorter = sorted
    else:
        sorter = list

    def write_stanza_body(items):
        for (key, value) in sorter(items.iteritems()):
            if value is None:
                value = ""
            else:
                value = str(value)
            if key.startswith("#"):
                stream.write("{0}\n".format(value))
            elif value:
                stream.write("{0} = {1}\n".format(key, value.replace("\n", "\\\n")))
            else:
                # Avoid a trailing whitespace to keep the git gods happy
                stream.write("{0} =\n".format(key))

    keys = sorter(conf)
    # Global MUST be written first
    # Todo, "[default]" (case sensitive?) should go second...
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
        write_conf_stream(temp, conf, stanza_delim, sort)
        with open(filename, "rb") as dest:
            file_diff = fileobj_compare(temp, dest)
        if file_diff:
            return SMART_NOCHANGE
        else:
            tempfile = filename + temp_suffix
            with open(tempfile, "wb") as dest:
                dest.write(temp.getvalue())
            os.unlink(filename)
            os.rename(tempfile, filename)
            return SMART_UPDATE
    else:
        tempfile = filename + temp_suffix
        with open(tempfile, "wb") as dest:
            write_conf_stream(dest, conf, stanza_delim, sort)
        os.rename(tempfile, filename)
        return SMART_CREATE


def _format_stanza(stanza):
    """ Return a more human readable stanza name."""
    if stanza is GLOBAL_STANZA:
        return "GLOBAL"
    else:
        return stanza


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


def _drop_stanza_comments(stanza):
    n = {}
    for (key, value) in stanza.iteritems():
        if key.startswith("#"):
            continue
        n[key] = value
    return n
