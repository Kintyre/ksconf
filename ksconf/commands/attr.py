"""r SUBCOMMAND:  ``ksconf attr-get <CONF> --stanza STANZA --attribute ATTR``

.. code-block:: sh

    ksconf attr-get $SPLUNK_HOME/etc/apps/Splunk_TA_aws/default/app.conf --stanza launcher --attribute version


SUBCOMMAND:  ``ksconf attr-set <CONF> --stanza STANZA --attribute ATTR --value VALUE``

.. code-block:: sh

    ksconf attr-set $SPLUNK_HOME/etc/apps/Splunk_TA_aws/local/app.conf \
        --stanza launcher --attribute version --value 9.9.9

    echo "9.9.9" > /tmp/new_version
    ksconf attr-set $SPLUNK_HOME/etc/apps/Splunk_TA_aws/local/app.conf \
        --stanza launcher --attribute version  -t file /tmp/new_version

    export NEW_VERSION=1.2.3
    ksconf attr-set $SPLUNK_HOME/etc/apps/Splunk_TA_aws/local/app.conf \
        --stanza launcher --attribute version -t env NEW_VERSION

"""

from __future__ import absolute_import, unicode_literals

import argparse
import os
from pathlib import Path

from ksconf.command import KsconfCmd, dedent
from ksconf.conf.parser import update_conf
from ksconf.consts import (EXIT_CODE_CONF_NO_DATA_MATCH, EXIT_CODE_NO_SUCH_FILE,
                           EXIT_CODE_NOTHING_TO_DO, EXIT_CODE_SUCCESS)
from ksconf.util.completers import conf_files_completer
from ksconf.util.file import expand_glob_list


class AttrGetCmd(KsconfCmd):
    help = "Get the value from a specific stanzas and attribute"
    description = dedent("""\
    Get a specific stanza and attribute value from a Splunk .conf file.
    """)
    format = "manual"
    maturity = "beta"

    def register_args(self, parser):
        parser.add_argument("conf", nargs="+",
                            default=["-"],
                            help="Input file or standard input."
                            ).completer = conf_files_completer

        parser.add_argument("--stanza", "-s", required=True,
                            help="Name of the stanza within CONF to retrieve.")
        parser.add_argument("--attribute", "--attr", "-a",
                            metavar="ATTR", required=True,
                            help="Name of attribute within STANZA to retrieve.")

        parser.add_argument("--missing-okay", action="store_true", default=False,
                            help="Ignore missing stanzas and attributes.  ")
        '''
        parser.add_argument("--quite", "-q", action="store_true", default=False,
                            help="Reduce the amount of output stderr")
        '''

        parser.add_argument("-o", "--output",
                            type=argparse.FileType('w'), default=self.stdout,
                            help="File where the filtered results are written.  "
                                 "Defaults to standard out.")

    def pre_run(self, args):
        # For Windows users, expand any glob patterns as needed.
        args.conf = list(expand_glob_list(args.conf))

    def run(self, args):
        ''' For a given conf file, get the 'value' from [stanza] attribute = value '''
        for conf in args.conf:
            if len(args.conf) > 1:
                args.output.write(f"---------------- [ {conf} ] ----------------\n\n")
            data = self.parse_conf(conf).data
            if args.missing_okay:
                try:
                    value = data[args.stanza][args.attribute]
                except KeyError:
                    value = ""
            else:
                try:
                    stanza = data[args.stanza]
                except KeyError:
                    self.stderr.write(f"File {conf} does not have the stanza [{args.stanza}] \n")
                    return EXIT_CODE_CONF_NO_DATA_MATCH
                try:
                    value = stanza[args.attribute]
                except KeyError:
                    self.stderr.write(f"File {conf} does not have {args.attribute} "
                                      f"in stanza [{args.stanza}]\n")
                    return EXIT_CODE_CONF_NO_DATA_MATCH
            args.output.write(f"{value}\n")
            args.output.flush()

        return EXIT_CODE_SUCCESS


class AttrSetCmd(KsconfCmd):
    help = "Set the value of a specific stanzas and attribute"
    description = dedent("""\
    Set a specific stanza and attribute value of a Splunk .conf file.
    The value can be provided as a command line argument, file, or
    environment variable

    This command does not support preserving leading or trailing whitespace.
    Normally this is desireable.
    """)
    format = "manual"
    maturity = "beta"

    def register_args(self, parser):
        parser.add_argument("conf",
                            help="Configuration file to update."
                            ).completer = conf_files_completer
        parser.add_argument("--stanza", "-s", required=True,
                            help="Name of the stanza within CONF to set.")
        parser.add_argument("--attribute", "--attr", "-a",
                            metavar="ATTR", required=True,
                            help="Name of the attribute within STANZA to set.")

        parser.add_argument("value",
                            help="Value to apply to the conf file.  Note that this can be a raw "
                            "text string, or the name of the file, or an environment variable")

        parser.add_argument("--value-type", "-t", metavar="TYPE", default="string",
                            choices=["string", "file", "env"],
                            help="Select the type of VALUE.  The default is a string.  "
                            "Alternatively, the real value can be provided within a file, "
                            "or an environment variable.")

        parser.add_argument("--create-missing", action="store_true", default=False,
                            help="Create a new conf file if it doesn't currently exist.")
        parser.add_argument("--no-overwrite", action="store_true", default=False,
                            help="Only set VALUE if none currently exists.  "
                            "This can be used to safely set a one-time default, "
                            "but don't update overwrite an existing value.")

    def get_value(self, value, value_type):
        if value_type == "file":
            if value == "-":
                return self.stdin.read().strip()
            else:
                return Path(value).read_text().strip()
        elif value_type == "env":
            return os.environ[value]
        else:
            return value

    def set_conf_value(self, conf_file: Path, stanza: str, attribute: str, value: str,
                       create_missing: bool, no_overwrite: bool):

        if not conf_file.is_file() and not create_missing:
            self.stderr.write(f"Unable to write to non-existent file {conf_file}.\n"
                              "To automatically create missing files use '--create-missing'\n")
            return EXIT_CODE_NO_SUCH_FILE

        with update_conf(conf_file, make_missing=create_missing) as conf:
            try:
                existing_value = conf[stanza][attribute]
            except KeyError:
                existing_value = None

            if existing_value is not None:
                if existing_value == value:
                    self.stderr.write(f"No change necessary.  {conf_file} "
                                      f"[{stanza}] {attribute} already has desired value.\n")
                    conf.cancel()
                    return EXIT_CODE_SUCCESS

                if no_overwrite:
                    self.stderr.write(f"Skipping updating {conf_file} due to --no-overwrite.  "
                                      f"[{stanza}] {attribute} already set.\n")
                    conf.cancel()
                    return EXIT_CODE_NOTHING_TO_DO

            if stanza not in conf:
                conf[stanza] = {}
            conf[stanza][attribute] = value

        self.stderr.write(f"Set {conf_file} [{stanza}] {attribute} as requested.\n")
        return EXIT_CODE_SUCCESS

    def run(self, args):
        ''' For a given conf file, set [stanza] attribute = value '''
        value = self.get_value(args.value, args.value_type)
        conf_path = Path(args.conf)
        return self.set_conf_value(conf_path, args.stanza, args.attribute, value,
                                   args.create_missing, args.no_overwrite)
