"""
SUBCOMMAND:  ksconf snapshot --output=FILE.json <PATH> [ ... <PATH-n> ]

Usage example:

    ksconf snapshot --output=daily.json /opt/splunk/etc/app/

"""
from __future__ import absolute_import, unicode_literals

import sys
import os
import json

from argparse import FileType

from ksconf import __version__, __vcs_info__
from ksconf.commands import KsconfCmd, dedent
from ksconf.conf.parser import PARSECONF_MID_NC, parse_conf, ConfParserException, GLOBAL_STANZA
from ksconf.consts import EXIT_CODE_SUCCESS
from ksconf.util.file import file_hash
from ksconf.util.completers import DirectoriesCompleter, FilesCompleter


class ConfSnapshotConfig(object):
    max_file_size = 10 * 1024 * 1024

    # max_files = 10000
    # include_parts = [ "conf", "meta", "lookups", "data/ui", "data/model", "data/ui/nav" ]


PARSECONF_MID_NC


class ConfSnapshot(object):
    schema_version = 0.1

    def __init__(self, config):
        self.config = config
        self._data = []

    @staticmethod
    def _decode_path_meta(path):
        meta = {}
        if path.endswith(".conf"):
            meta["type"] = "conf"
            meta["conf"] = os.path.basename(path)[:-5]
        elif path.endswith(".meta"):
            meta["type"] = "metadata"
        # meta["level"] = local vs default
        # meta["folder"] = apps, deployment-apps, master-apps, users, ...
        # Eventually need some kind of "data/*" decoder as well.
        return meta

    @staticmethod
    def _get_file_info(path):
        file_info = {}
        file_info["path"] = path
        # XXX:  Format is ISO something or other (with timezone, ugh); for now just use int
        st = os.stat(path)
        file_info["mtime"] = int(st.st_mtime)
        file_info["size"] = st.st_size
        # Full hash is probably an overkill; first 20 characters is probably plenty; and this is a
        # hash of the RAW file, not the config contents.
        file_info["hash"] = file_hash(path)
        # For now, don't bother capturing OS specific stuff like mode or file ownership.
        # Let's assume that if we can read it, Splunk can read it too.
        return file_info

    def snapshot_file_conf(self, path):
        # XXX: If we are unable to read the file (IOError/OSError) that should be reported via
        # metadata or via 'failure'
        record = {}
        record["meta"] = self._decode_path_meta(path)
        record["file"] = self._get_file_info(path)
        try:
            data = parse_conf(path, profile=PARSECONF_MID_NC)
            # May need to format this differently.   Specifically need some way to textually
            # indicate the global stanza
            record["conf"] = data
            if GLOBAL_STANZA in data:
                g = data[GLOBAL_STANZA]
                data["**GLOBAL_STANZA**"] = g
                del data[GLOBAL_STANZA]
        except ConfParserException as e:
            record["conf"] = None
            record["failure"] = "{}".format(e)
        self._data.append(record)

    def snapshot_dir(self, path):
        path = os.path.abspath(path)
        for (dirpath, dirnames, filenames) in os.walk(path):
            # Remove unwanted directories
            for avoid in ("bin", "static"):
                if avoid in dirnames:
                    dirnames.remove(avoid)
            for fn in filenames:
                if not (fn.endswith(".conf") or fn.endswith(".meta")):
                    continue
                self.snapshot_file_conf(os.path.join(path, dirpath, fn))

    def write_snapshot(self, stream, **kwargs):
        record = {
            "schema_version" : self.schema_version,
            "software" : {
                "name" : "ksconf",
                "version" : [ __version__, __vcs_info__ ],
                "command" : sys.argv,
            },
        }
        record["records"] = self._data
        json.dump(record, stream, **kwargs)


class SnapshotCmd(KsconfCmd):
    help = "Snapshot .conf file directories into a JSON dump format"
    description = dedent("""\
    Build a static snapshot of various configuration files stored within a structured json export
    format.  If the .conf files being captured are within a standard Splunk directory structure,
    then certain metadata is assumed based on path locations.  Otherwise, less metadata is recorded.

    ksconf snapshot --output=daily.json /opt/splunk/etc/app/
    """)

    def register_args(self, parser):
        parser.add_argument("path", metavar="PATH", nargs="+", type=str,
                            help="Directory from which to load configuration files.  "
                                 "Recursive by default."
                            ).completer = DirectoriesCompleter()
        parser.add_argument("--output", "-t", metavar="FILE",
                            type=FileType("w"), default=sys.stdout,
                            help="""
            Save the snapshot to the named files.  If not provided, the snapshot is written to
            standard output."""
                            ).completer =  FilesCompleter(allowednames=["*.json"])
        parser.add_argument("--minimize", action="store_true", default=False, help="""
            Reduce the size of the JSON output by removing whitespace.  Reduces readability.  """)


    def run(self, args):
        ''' Snapshot multiple configuration files into a single json snapshot. '''

        cfg = ConfSnapshotConfig()
        confSnap = ConfSnapshot(cfg)
        for path in args.path:
            confSnap.snapshot_dir(path)

        if args.minimize:
            confSnap.write_snapshot(args.output)
        else:
            confSnap.write_snapshot(args.output, indent=2)
        return EXIT_CODE_SUCCESS
