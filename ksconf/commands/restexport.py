# -*- coding: utf-8 -*-
"""
SUBCOMMAND:  ``ksconf rest-export --output=script.sh <CONF>``

Usage example:

.. code-block:: sh

    ksconf rest-export --output=apply_props.sh /opt/splunk/etc/app/Splunk_TA_aws/local/props.conf


NOTE:

    If we add support for Windows CURL, then we'll need to also support proper quoting for the '%'
    character.   This can be done with '%^', wonky, I know...

"""
from __future__ import absolute_import, unicode_literals

import os
import shlex
import sys
from argparse import ArgumentParser, FileType
from urllib.parse import quote

from ksconf.commands import ConfFileType, KsconfCmd, dedent
from ksconf.conf.parser import GLOBAL_STANZA, PARSECONF_LOOSE
from ksconf.consts import EXIT_CODE_SUCCESS
from ksconf.util.completers import conf_files_completer
from ksconf.util.rest import build_rest_url


class Literal:
    def __init__(self, value):
        self.value = value

    '''
    def __str__(self):
        return self.value
    '''


class CurlCommand:
    def __init__(self):
        self.url = None
        self.method = None  # curl defaults this to POST
        self.pre_args = ["-k"]
        self.post_args = []
        self.headers = {}
        self.data = {}
        self.pretty_format = True

    @classmethod
    def quote(cls, s):
        if isinstance(s, Literal):
            return s.value
        if "$" in s:
            s = f'"{s}"'
        elif " " in s:
            s = f"'{s}'"
        return s

    def get_command(self):
        cmd = ["curl"]
        args = []

        if self.method:
            args.append("-X")
            args.append(self.method)

        if self.headers:
            for header in self.headers:
                value = self.headers[header]
                args.append("-H")
                args.append(f"{header}: {value}")
        if self.data:
            for key in self.data:
                value = self.data[key]
                if self.pretty_format:
                    args.append(Literal("\\\n -d"))
                else:
                    args.append("-d")
                args.append(f"{quote(key)}={quote(value)}")

        # if self.pre_args:
        #    cmd.append(" ".join(self.pre_args))
        cmd.extend(self.pre_args)
        cmd.append(self.url)
        cmd.extend(self.quote(arg) for arg in args)
        cmd.extend(self.quote(arg) for arg in self.post_args)
        return " ".join(cmd)

    def extend_args(self, args):
        # Use shlex parsing to handle embedded quotess
        for s in shlex.split(args):
            self.post_args.append(s)


class RestExportCmd(KsconfCmd):
    help = "Export .conf settings as a curl script to apply to a Splunk instance later (via REST)"
    description = dedent("""\
    Build an executable script of the stanzas in a configuration file that can be later applied to
    a running Splunk instance via the Splunkd REST endpoint.

    This can be helpful when pushing complex props and transforms to an instance where you only have
    UI access and can't directly publish an app.

    """)
    format = "manual"
    maturity = "beta"

    def register_args(self, parser: ArgumentParser):
        parser.add_argument("conf", metavar="CONF", nargs="+",
                            type=ConfFileType("r", "load", parse_profile=PARSECONF_LOOSE),
                            help="Configuration file(s) to export settings from."
                            ).completer = conf_files_completer
        parser.add_argument("--output", "-t", metavar="FILE",
                            type=FileType("w"), default=sys.stdout,
                            help="Save the shell script output to this file.  "
                                 "If not provided, the output is written to standard output.")

        prsout = parser.add_argument_group("Output Control")

        '''
        prsout.add_argument("--syntax", choices=["curl", "powershell"],  # curl-windows?
                            default="curl",
                            help="Pick the output syntax mode.  "
                                 "Currently only 'curl' is supported.")
        '''
        prsout.add_argument("--disable-auth-output", action="store_true", default=False,
                            help="Turn off sample login curl commands from the output.")
        prsout.add_argument("--pretty-print", "-p", action="store_true", default=False,
                            help=dedent("""\
            Enable pretty-printing.
            Make shell output a bit more readable by splitting entries across lines."""))

        parsg1 = parser.add_mutually_exclusive_group(required=False)
        parsg1.add_argument("-u", "--update", action="store_true", default=False,
                            help="Assume that the REST entities already exist.  "
                                 "By default, output assumes stanzas are being created.")
        parsg1.add_argument("-D", "--delete", action="store_true", default=False,
                            help=dedent("""\
            Remove existing REST entities.  This is a destructive operation.
            In this mode, stanza attributes are unnecessary and ignored.
            NOTE:  This works for 'local' entities only; the default folder cannot be updated.
            """))

        parser.add_argument("--url", default="https://localhost:8089",
                            help="URL of Splunkd.  Default:  %(default)s")
        parser.add_argument("--app", default="$SPLUNK_APP",
                            help="Set the namespace (app name) for the endpoint")

        parser.add_argument("--user", help="Deprecated.  Use --owner instead.")
        parser.add_argument("--owner", default="nobody",
                            help="Set the object owner.  Typically, the default of 'nobody' is "
                                 "ideal if you want to share the configurations at the app-level.")
        parser.add_argument("--conf", dest="conf_type", metavar="TYPE",
                            help=dedent("""\
            Explicitly set the configuration file type.  By default, this is derived from CONF, but
            sometimes it's helpful to set this explicitly.  Can be any valid Splunk conf file type.
            Examples include: 'app', 'props', 'tags', 'savedsearches', etc."""))

        parser.add_argument("--extra-args", action="append",
                            help=dedent("""\
            Extra arguments to pass to all CURL commands.
            Quote arguments on the command line to prevent confusion between arguments to ksconf vs
            curl."""))

    @staticmethod
    def build_rest_url(base, owner, app, conf):
        # XXX: Quote owner & app; however for now we're still allowing the user to pass though an
        #  environmental variable as-is and quoting would break that.   Need to make a decision,
        # for now this is not likely to be a big issue given app and user name restrictions.
        return build_rest_url(base, f"configs/conf-{conf}", owner, app)

    def run(self, args):
        ''' Convert a conf file into a bunch of CURL commands'''
        r"""

        Some inspiration in the form of CURL commands...

        [single_quote_kv]
        REGEX = ([^=\s]+)='([^']+)'
        FORMAT = $1::$2
        MV_ADD = 0

        CREATE NEW:

        curl -k https://SPLUNK:8089/servicesNS/nobody/my_app/configs/conf-transforms \
         -H "Authorization: Splunk $SPLUNKDAUTH" -X POST \
         -d name=single_quote_kv \
         -d REGEX="(%5B%5E%3D%5Cs%5D%2B)%3D%27(%5B%5E%27%5D%2B)%27" \
         -d FORMAT='$1::$2'

        UPDATE EXISTING:  (note the change in URL/name attribute)

        curl -k https://SPLUNK:8089/servicesNS/nobody/my_app/configs/conf-transforms/single_quote_kv \
         -H "Authorization: Splunk $SPLUNKDAUTH" -X POST \
         -d REGEX="(%5B%5E%3D%5Cs%5D%2B)%3D%27(%5B%5E%27%5D%2B)%27" \
         -d FORMAT='$1::$2' \
         -d MV_ADD=0
        """
        stream = args.output

        if args.user:       # pragma: no cover
            from warnings import warn
            warn("Use '--owner' instead of '--user'", DeprecationWarning)
            if args.owner != "nobody":
                raise ValueError("Can't use both --user and --owner at the same time!")
            args.owner = args.user

        if args.pretty_print:
            line_breaks = 2
        else:
            line_breaks = 1

        if args.disable_auth_output is False:
            # Make this preamble optional
            stream.write("## Example of creating a local SPLUNKDAUTH token\n")
            stream.write("export SPLUNKDAUTH=$("
                         f"curl -ks {args.url}/services/auth/login -d username=admin -d password=changeme "
                         "| grep sessionKey "
                         r"| sed -E 's/[ ]*<sessionKey>(.*)<.sessionKey>/\1/')")
            stream.write('; [[ -n $SPLUNKDAUTH ]] && echo "Login token created"')
            stream.write("\n\n\n")

        for conf_proxy in args.conf:
            conf = conf_proxy.data
            if args.conf_type:
                conf_type = args.conf_type
            else:
                conf_type = os.path.basename(conf_proxy.name).replace(".conf", "")

            stream.write(f"# CURL REST commands for {conf_proxy.name}\n")

            for stanza_name, stanza_data in conf.items():
                cc = CurlCommand()
                cc.pretty_format = args.pretty_print
                cc.url = self.build_rest_url(args.url, args.owner, args.app, conf_type)
                if args.extra_args:
                    for extra_arg in args.extra_args:
                        cc.extend_args(extra_arg)

                if stanza_name is GLOBAL_STANZA:
                    # XXX:  Research proper handling of default/global stanzas..
                    # As-is, curl returns an HTTP error, but yet the new entry is added to the
                    # conf file.  So I suppose we could ignore the exit code?!    ¯\_(ツ)_/¯
                    stream.write("### WARN:  Writing to the default stanza may not work as "
                                 "expected.  Or it may work, but be reported as a failure.  "
                                 "Patches welcome!\n")
                    cc.url += "/default"
                elif args.update or args.delete:
                    cc.url += "/" + quote(stanza_name, "")  # Must quote '/'s too.
                else:
                    cc.data["name"] = stanza_name

                if args.delete:
                    cc.method = "DELETE"
                else:
                    # Add individual keys
                    for (key, value) in stanza_data.items():
                        cc.data[key] = value

                cc.headers["Authorization"] = "Splunk $SPLUNKDAUTH"

                stream.write(cc.get_command())
                stream.write("\n" * line_breaks)
            stream.write("\n\n" * line_breaks)
        stream.write("\n")

        return EXIT_CODE_SUCCESS
