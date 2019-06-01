"""

Python script to rebuild an app and user directory structure from a CSV export from various REST endpoints.


This script restores data exported from a search like so:


    | makeresults count=1 | eval id="BACKUP-HEADER", now=now(), title="Lowell's backup after a long day's work"
    | append [ rest splunk_server=local /servicesNS/-/-/data/ui/views ]
    | append [ rest splunk_server=local /servicesNS/-/-/data/ui/nav ]
    | append [ rest splunk_server=local /servicesNS/-/-/data/models ]
    | append [ rest splunk_server=local /servicesNS/-/-/configs/conf-macros ]
    | append [ rest splunk_server=local /servicesNS/-/-/configs/conf-savedsearches ]
    | append [ rest splunk_server=local /servicesNS/-/-/configs/conf-eventtypes ]
    | append [ rest splunk_server=local /servicesNS/-/-/configs/conf-transforms ]
    | append [ rest splunk_server=local /servicesNS/-/-/configs/conf-props ]
    | append [ rest splunk_server=local /servicesNS/-/-/configs/conf-tags ]
    | append [ rest splunk_server=local /servicesNS/-/-/configs/conf-fields ]
    | append [ rest splunk_server=local /servicesNS/-/-/configs/conf-datamodels ]
    | append [ rest splunk_server=local /servicesNS/-/-/configs/conf-commands ]
    | append [ rest splunk_server=local /servicesNS/-/-/configs/conf-restmap ]
    | append [ rest splunk_server=local /servicesNS/-/-/configs/conf-alert_actions ]
    | append [ rest splunk_server=local /servicesNS/-/-/configs/conf-workflow_actions ]
    | append [ rest splunk_server=local /servicesNS/-/-/configs/conf-times ]
    | append [ rest splunk_server=local /servicesNS/-/-/configs/conf-app ]
    | append [ rest splunk_server=local /servicesNS/-/-/configs/conf-inputs ]
    | append [ rest splunk_server=local /servicesNS/-/-/configs/conf-eventgen ]
    | append [ rest splunk_server=local /servicesNS/-/-/configs/conf-ui-prefs ]
    | append [ rest splunk_server=local /servicesNS/-/-/configs/conf-collections ]
    | append [ rest splunk_server=local /servicesNS/-/-/configs/conf-limits ]
    | append [ rest splunk_server=local /servicesNS/-/-/configs/conf-web ]
    | append [ rest splunk_server=local /servicesNS/-/-/configs/conf-server ]
    | append [ rest splunk_server=local /servicesNS/-/-/configs/conf-multikv ]
    | append [ rest splunk_server=local /servicesNS/-/-/configs/conf-indexes ]
    | append [ rest splunk_server=local /servicesNS/-/-/configs/conf-authorize ]
    | table splunk_server, id, title, eai:*, *, _*

# We intentionally exclude:

 * passwords - for security reasons
 * viewstates - because you shouldn't use them anymore
 * authentication - because it could have sensitive info

# Stuff that we don't normally care about:

 * checklist (health check)
 * distsearch
 * searchb
 * event_renderers
 * outputs
 * regmon-filters
 * wmi
 * admon
 * healthlog
 * migration
 * sourcetypes




"https://127.0.0.1:8089/servicesNS/nobody/system/data/ui/views/_admin"
"https://127.0.0.1:8089/servicesNS/nobody/system/configs/conf-props/sendmail_syslog"


Known limitations:

 * Can't capture custom command scripts (python or otherwise)
 * Can't capture any static files
 * Doesn't capture custom config files (though, any /configs/conf-* is supported automatically)
 * Doesn't handle lookups (could add support for small lookups; using inputlookup & map)
 * Can't separate layers or peak between them (e.g. what values came from 'default', and in from which layer)
 * Only captures live server settings (system + apps + user); can't view into deployment-apps, master-apps, or shcluster/apps

ToDo:  Add a Splunk Server information header to determine the Splunk version/build.  At the very
       least, this tells us what the "system/defaults" looked like.  And there could be other
       relevant tweaks as well.
"""
from __future__ import print_function, unicode_literals

import re
import csv
import sys
import os
import hashlib

from six import PY2, PY3

from collections import defaultdict
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse
from datetime import datetime

# Increase CSV field limit from 128k to something more appropriate for data dumps (2MB)
csv.field_size_limit(2*1024*1024)


NoMatch = object()

def str_matcher(litstring):
    def matcher(value):
        if value == litstring:
            return value
        else:
            return NoMatch
    # Helps with interactive debugging
    matcher.__doc__ = "Match string '{}'".format(litstring)
    return matcher


def re_matcher(regex):
    cre = re.compile(regex)
    if "(?P<" in regex:
        mode = "dict"
    else:
        mode = "list"

    def matcher(value):
        mo = cre.match(value)
        if mo:
            if mode == "dict":
                return mo.groupdict()
            else:
                return mo.groups()
        else:
            return NoMatch
    # Helps with interactive debugging
    matcher.__doc__ = "Match regex '{}'".format(regex)
    return matcher



def _makedir_dirname(p):
    d = os.path.dirname(p)
    if not os.path.isdir(d):
        os.makedirs(d)

def output_file(path, content):
    _makedir_dirname(path)
    with open(path, "wb") as fp:
        fp.write(content)


# from ksconf import write_conf
# Hardly worth importing for 30 lines of code
GLOBAL_STANZA = "default"
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
        for (key, value) in sorter(iter(items.items())):
            if key.startswith("#"):
                stream.write("{0}\n".format(value))
            elif value:
                # XXX: REPLACE SUPER LAME WORKAROUND.  **FIXME**
                try:
                    stream.write("{0} = {1}\n".format(key, value.replace("\n", "\\\n")))
                except UnicodeDecodeError:
                    stream.write("######## UNICODE DECODE ERROR ---> WORKAROUND #######\n")
                    stream.write("{0!r} = {1!r}\n".format(key, value))
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

def output_conf(filename, conf):
    _makedir_dirname(filename)
    with open(filename, "w") as stream:
        write_conf(stream, conf)


class ContextObject(object):
    # user
    # app
    # sharing
    pass


class SplunkEAIObject(object):
    def __init__(self, data):
        self._data = data
        self._id = None

    def __hash__(self):
        if self._id is None:
            self._id = ( self.data["id"], )
        return id(self._id)

    def __getitem__(self, key):
        return self._data[key]

    @property
    def sharing(self):
        return self._data["eai:acl.sharing"]

    @property
    def app(self):
        return self._data["eai:acl.app"] # OR eai:appName?

    @property
    def user(self):
        return self._data["eai:acl.owner"]  # OR eai:userName?

    @property
    def data(self):
        return self._data["eai:data"]

    @property
    def digest(self):
        return self._data["eai:digest"]

    # digest?
    def type(self):
        return self._data["eai:type"]

    def get_fs_path(self, prefix="etc", level="local"):
        sharing = self.sharing
        if sharing == "system":
            path = [ "system", level ]
        elif sharing in ("app", "global"):
            path = [ "apps", self.app, level ]
        elif sharing == "user":
            # This one is ALWAYS local
            path = [ "user", self.user, self.app, "local" ]
        else:
            raise ValueError("Unknown value for eai:acl.sharing:  %s  [%s]" %
                             (sharing, self._data.get("title", "No title")))
        return os.path.join(prefix, *path)

    def validate_data(self):
        data = self.data
        digest = self.digest
        if not data or not digest:
            return None
        if len(digest) == 32:
            hash_algo = "md5"
        else:
            raise ValueError("Unknown hash type for '{}'".format(digest))
        h = hashlib.new(hash_algo)
        if PY3:
            # XXX:  Ugly workaround for now, just mask any encoding errors...
            data = data.encode("utf-8", errors="replace")
        h.update(data)
        h.hexdigest()
        return h.hexdigest().lower() == digest.lower()


class NoRouteFound(Exception):
    pass


def _get_rest_url(rest_url, context=None):
    if context is None:
        context = ContextObject()
    url = urlparse(rest_url)
    url_parts = url.path.split("/")[1:]
    context.url = url
    if url_parts[0] == "services":
        context.user = "nobody"
        context.app = "system"
        url_parts = url_parts[1:]
    elif url_parts[0] == "servicesNS":
        context.user = url_parts[1]
        context.app = url_parts[2]
        url_parts = url_parts[3:]
    else:
        raise ValueError("Unknown prefix %s" % url_parts[0])
    short_url = "/" + "/".join(url_parts)
    return short_url


class SplunkEaiCsvImportRouter(object):
    _rules = []

    def __init__(self):
        self.writer = None

    def set_writer(self, writer):
        self.writer = writer

    @classmethod
    def add_rule(cls, pattern, handler):
        assert callable(handler)
        assert callable(pattern)
        cls._rules.append( (pattern, handler) )

    def route(self, row):
        row_id = row["id"]
        context = ContextObject()
        if row_id.startswith("https://"):
            row_id = _get_rest_url(row_id, context)
        for (pattern, handler) in self._rules:
            match = pattern(row_id)
            if match is not NoMatch:
                return handler(self.writer, row, context, match)
        else:
            raise NoRouteFound("No handler found for %s" % row_id)

    @classmethod
    def match_regex(cls, regex):
        def f(funct):
            cls.add_rule(re_matcher(regex), funct)
            return funct
        return f

    @classmethod
    def match_string(cls, literal):
        def f(funct):
            cls.add_rule(str_matcher(literal), funct)
        return f

# Convenience name for decorator declarations
router = SplunkEaiCsvImportRouter


class OutputBase(object):
    def __init__(self):
        self._context_entries = []

    @staticmethod
    def _get_conf_filename(root, eai, conf, conf_level=None):
        path = eai.get_fs_path(root, conf_level)
        basename = conf + ".conf"
        return os.path.join(path, basename)

    @staticmethod
    def _get_data_filename(root, eai, data_type, title, conf_level=None):
        path = eai.get_fs_path(root, conf_level)
        parts = [ path, "data" ]
        suffix = ".unknown"
        if data_type in ("views", "nav"):
            # Todo:  Support other types of views like HTML dashboards
            suffix = ".xml"
            parts.append("ui")
        elif data_type == "models":
            suffix = ".json"
        parts.append(data_type)
        parts.append(title + suffix)
        return os.path.join(*parts)

    def put_conf_entry(self, eai, conf, title, data):
        raise NotImplementedError

    def put_data_entry(self, eai, data_type, title, payload):
        raise NotImplementedError

    def put_context(self, context):
        self._context_entries.append(context)

    def process(self):
        pass


class OutputInMemory(OutputBase):
    """ Write the given config entries to a etc/{apps,user,system}/... style filesystem """
    conf_level = "local"

    def __init__(self, root):
        super(OutputInMemory, self).__init__()
        self.root = root
        self._conf = defaultdict(lambda: defaultdict())   # [path][stanza][key]
        self._data = {}
        self._data_meta = {}

    def put_conf_entry(self, eai, conf, title, data):
        conf_file = self._get_conf_filename(self.root, eai, conf, self.conf_level)
        self._conf[conf_file][title] = data

    def put_data_entry(self, eai, data_type, title, payload):
        file_path = self._get_data_filename(self.root, eai, data_type, title, self.conf_level)
        self._data[file_path] = payload
        self._data_meta[file_path] = eai


class OutputDebugDump(OutputInMemory):
    def __init__(self, root, debug_stream=None):
        super(OutputDebugDump, self).__init__(root)
        self.stream = debug_stream or sys.stdout

    def show_inventory(self):
        stream = self.stream
        for context in self._context_entries:
            stream.write("{!r}\n".format(context))
            stream.write("{!r}\n".format(context.__dict__))
        for (path, conf_entries) in sorted(self._conf.items()):
            for title in sorted(conf_entries.keys()):
                stream.write("Conf {} [{}]\n".format(path, title))
            stream.write("\n")
        for (path, eai) in sorted(self._data_meta.items()):
            stream.write("Data {}  >>{}<< bytes={:d} valid={}\n".format(
                          path, eai["label"], len(eai.data), eai.validate_data()))

    def process(self):
        stream = self.stream
        for context in self._context_entries:
            print(context)
            print(context.__dict__)

        for (path, conf_entries) in sorted(self._conf.items()):
            stream.write("------ {} -------\n".format(path))
            for (stanza, kvpairs) in sorted(conf_entries.items()):
                stream.write("[{}]\n".format(stanza))
                for (key, value) in sorted(kvpairs.items()):
                    # No line continuation handled here...
                    try:
                        stream.write("{} = {}\n".format(key, value))
                    except UnicodeDecodeError:
                        stream.write("{} = {!r}   <<< UNICODE DECODE ERROR\n".format(key, value))
                stream.write("\n")
            stream.write("\n\n")
        max_data_size = 1024*10
        for (path, data_content) in sorted(self._data.items()):
            stream.write(">----- {} --->>>\n".format(path))
            if PY2:
                data_content = data_content.decode("utf-8", errors="replace")
            if len(data_content) > max_data_size:
                stream.write(data_content[:max_data_size] + "... (TRUNCATED)\n")
            else:
                stream.write(data_content)
                stream.write("\n<<<--- {} -----<\n\n".format(path))

class OutputFileSystem(OutputInMemory):
    # Derived from "in-memory" class, but we intercept the 'data' bits to reduce memory footprint.
    def put_data_entry(self, eai, data_type, title, payload):
        file_path = self._get_data_filename(self.root, eai, data_type, title, self.conf_level)
        if eai.validate_data():
            sys.stdout.write("Creating data file:  {}  size={:d}\n".format(file_path, len(payload)))
            output_file(file_path, payload)
        else:
            sys.stderr.write("Skipping to write to {}.  Digest mismatch.\n".format(file_path))

    def process(self):
        for (path, conf_entries) in sorted(self._conf.items()):
            sys.stdout.write("Creating conf file:  {}  stanzas={:d}\n"
                             .format(path, len(conf_entries)))
            output_conf(path, conf_entries)


class OutputTarball(OutputInMemory):
    def __init__(self, tarball_name):
        raise NotImplementedError


class OutputRESTReceiver(OutputBase):
    """ Replay REST style config content to a running Splunk instance.  (For "cloning" from a .csv instance.) """
    pass


@router.match_string("BACKUP-HEADER")
def handle_backup_header(writer, row, context, match):
    context.name = row["title"]
    now = int(row["now"])
    context.timestamp = datetime.fromtimestamp(now)
    writer.put_context(context)
    del match

STANDARD_EAI_KEYS = ("title", "id", "owner", "splunk_server", "author", "updated")
STANDARD_EAI_DEFAULTS = {
    "disabled" : "0"
}

@router.match_regex(r"/configs/conf-(?P<conf_name>[a-z_]+)/[^/]+$")
def handle_generic_configs_conf(writer, row, context, match):
    eai = SplunkEAIObject(row)
    conf_name = match["conf_name"]
    title = row["title"]
    data = {}
    for (key, value) in row.items():
        if key.startswith("eai:"):
            continue
        if key in STANDARD_EAI_KEYS:
            continue
        if key in STANDARD_EAI_DEFAULTS and value == STANDARD_EAI_DEFAULTS[key]:
            continue
        if not value:
            continue
        data[key] = value
    writer.put_conf_entry(eai, conf_name, title, data)


@router.match_regex(r"/data/ui/(?P<data_type>[^/]+)/(?P<data_name>[^/]+)$")
def handle_generic_data_handler(writer, row, context, match):
    eai = SplunkEAIObject(row)
    data_type = match["data_type"]
    data_name = match["data_name"]
    title = row["title"]
    if data_name != title:
        raise ValueError("Unexpected {} name mismatch:  '{}' != '{}'".format(data_type, data_name, title))
    writer.put_data_entry(eai, data_type, title, eai.data)

@router.match_regex(r"/data/(?P<data_type>models)/(?P<data_name>[^/]+)$")
def handle_data_models(writer, row, context, match):
    eai = SplunkEAIObject(row)
    data_type = match["data_type"]
    data_name = match["data_name"]
    title = row["title"]
    if data_name != title:
        raise ValueError("Unexpected {} name mismatch:  '{}' != '{}'".format(data_type, data_name, title))
    writer.put_data_entry(eai, data_type, title, eai.data)


def drop_empty(d):
    d2 = []
    for (k,v) in d.items():
        if v:
            d2[k] = v
    return d2


def main():
    # Todo:  Add a "tarball" exporter option;  Possibly one per app?
    import argparse
    parser = argparse.ArgumentParser(
        description="Script to convert Splunk csv dump back into Splunk app(s).  "
                    "See comments for the REST-based splunk search that will create a proper input"
                    "file. ")
    parser.add_argument("csv", metavar="FILE",
                        type=argparse.FileType('r'),
                        help="Input CSV file.")
    parser.add_argument("output", metavar="DIR", default="etc",
                        help="Output directory")
    parser.add_argument("--dump", default=False, action="store_true",
                        help="Dump output to standard output")
    args = parser.parse_args()

    reader = csv.DictReader(args.csv)
    importer = SplunkEaiCsvImportRouter()

    if args.dump:
        ofs = OutputDebugDump(args.output)
    else:
        ofs = OutputFileSystem(args.output)
    importer.set_writer(ofs)

    for row in reader:
        try:
            importer.route(row)
        except NoRouteFound:
            print("Skipping %s" % row["id"])

    if args.dump:
        ofs.show_inventory()

    ofs.process()

if __name__ == "__main__":
    main()
