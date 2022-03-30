"""
SUBCOMMAND:  ``ksconf snapshot --output=FILE.json <PATH> [ ... <PATH-n> ]``

Usage example:

.. code-block:: sh

    ksconf snapshot --output=daily.json /opt/splunk/etc/app/

"""
from __future__ import absolute_import, unicode_literals

import json
import os
import sys
from argparse import FileType

from ksconf import __vcs_info__, __version__
from ksconf.commands import KsconfCmd, dedent
from ksconf.conf.parser import GLOBAL_STANZA, PARSECONF_MID_NC, ConfParserException, parse_conf
from ksconf.consts import EXIT_CODE_NO_SUCH_FILE, EXIT_CODE_SUCCESS
from ksconf.util.completers import DirectoriesCompleter, FilesCompleter
from ksconf.util.file import file_hash


class ConfSnapshotConfig:
    max_file_size = 10 * 1024 * 1024

    # max_files = 10000
    # include_parts = [ "conf", "meta", "lookups", "data/ui", "data/model", "data/ui/nav" ]


class ConfSnapshot:
    schema_version = 0.2

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
        # XXX: Extract the app name ...
        return meta

    @staticmethod
    def _get_file_info(path):
        file_info = {}
        file_info["path"] = path
        # XXX:  Format as ISO something or other (with timezone, ugh); for now just use int
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
            conf = record["conf"] = []
            for (stanza, stanza_data) in data.items():
                rec = {
                    "stanza": stanza,
                    "attributes": stanza_data
                }
                if stanza is GLOBAL_STANZA:
                    rec["stanza"] = "**GLOBAL_STANZA**"
                conf.append(rec)
        except ConfParserException as e:
            record["conf"] = None
            record["failure"] = f"{e}"
        self._data.append(record)

    def snapshot_dir(self, path):
        path = os.path.abspath(path)
        for (dirpath, dirnames, filenames) in os.walk(path):
            # Remove unwanted directories
            for avoid in ("bin", "static"):
                if avoid in dirnames:
                    dirnames.remove(avoid)
            for fn in filenames:
                if fn.endswith(".conf") or fn.endswith(".meta"):
                    self.snapshot_file_conf(os.path.join(path, dirpath, fn))

    def write_snapshot(self, stream, **kwargs):
        record = {
            "schema_version": self.schema_version,
            "software": {
                "name": "ksconf",
                "version": [__version__, __vcs_info__],
                "command": sys.argv,
            },
        }
        record["records"] = self._data
        json.dump(record, stream, **kwargs)


class SnapshotCmd(KsconfCmd):
    help = "Snapshot .conf file directories into a JSON dump format"
    description = dedent("""\
    Build a static snapshot of various configuration files stored within a structured json export
    format.  If the .conf files being captured are within a standard Splunk directory structure,
    then certain metadata and namespace information is assumed based on typical path locations.
    Individual apps or conf files can be collected as well, but less metadata may be extracted.
    """)

    def register_args(self, parser):
        parser.add_argument("path", metavar="PATH", nargs="+", type=str,
                            help="Directory from which to load configuration files.  "
                                 "All .conf and .meta file are included recursively."
                            ).completer = DirectoriesCompleter()
        parser.add_argument("--output", "-o", metavar="FILE",
                            type=FileType("w"), default=self.stdout,
                            help=dedent("""\
            Save the snapshot to the named files.  If not provided, the snapshot is written to
            standard output.""")
                            ).completer = FilesCompleter(allowednames=["*.json"])
        parser.add_argument("--minimize", action="store_true", default=False,
                            help="Reduce the size of the JSON output by removing whitespace.  "
                            "Reduces readability.")

    def run(self, args):
        ''' Snapshot multiple configuration files into a single json snapshot. '''
        cfg = ConfSnapshotConfig()
        confSnap = ConfSnapshot(cfg)
        for path in args.path:
            if os.path.isfile(path):
                confSnap.snapshot_file_conf(path)
            elif os.path.isdir(path):
                confSnap.snapshot_dir(path)
            else:
                self.stderr.write(f"No such file or directory {path}\n")
                return EXIT_CODE_NO_SUCH_FILE

        if args.minimize:
            confSnap.write_snapshot(args.output)
        else:
            confSnap.write_snapshot(args.output, indent=2)
        return EXIT_CODE_SUCCESS
