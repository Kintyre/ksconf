# -*- coding: utf-8 -*-
"""
SUBCOMMAND:  ksconf rest-export --output=script.sh <CONF>

Usage example:

    ksconf rest-export --output=apply_props.sh /opt/splunk/etc/app/Splunk_TA_aws/local/props.conf


NOTE:

    If we add support for Windows CURL, then we'll need to also support proper quoting for the '%'
    character.   This can be done with '%^', wonky, I know...

"""
from __future__ import absolute_import, unicode_literals

import sys
import os

from argparse import FileType
from six.moves.urllib.parse import quote

from ksconf.commands import KsconfCmd, dedent, ConfFileType
from ksconf.conf.parser import PARSECONF_LOOSE, GLOBAL_STANZA
from ksconf.consts import EXIT_CODE_SUCCESS
from ksconf.util.completers import conf_files_completer
from collections import OrderedDict



class CurlCommand(object):
    def __init__(self):
        self.url = None
        self.pre_args = [ "-k" ]
        self.post_args = []
        self.headers = OrderedDict()
        self.data = OrderedDict()

    @classmethod
    def quote(cls, s):
        if "$" in s:
            s = '"{}"'.format(s)
        elif " " in s or "$" in s:
            s = "'{}'".format(s)
        return s

    def get_command(self):
        cmd = ["curl"]

        args = []
        if self.headers:
            for header in self.headers:
                value = self.headers[header]
                args.append("-H")
                args.append("{}: {}".format(header, value))
        if self.data:
            for key in self.data:
                value = self.data[key]
                args.append("-d")
                args.append("{}={}".format(quote(key), quote(value)))


        if self.pre_args:
            cmd.append(" ".join(self.pre_args))
        cmd.append(self.url)
        args = [ self.quote(arg) for arg in args ]
        cmd.extend(args)
        if self.post_args:
            cmd.append(" ".join(self.post_args))
        return " ".join(cmd)



class RestExportCmd(KsconfCmd):
    help = "Export .conf settings as a curl script to apply to a Splunk instance later (via REST)"
    description = dedent("""\
    Build an executable script of the stanzas in a configuration file that can be later applied to
    a running Splunk instance via the Splunkd REST endpoint.

    This can be helpful when pushing complex props & transforms to an instance where you only have
    UI access and can't directly publish an app.

    WARNING:  This command is indented for manual admin workflows.  It's quite possible that shell
    escaping bugs exist that may allow full shell access if you put this into an automated workflow.
    Evalute the risks, review the code, and run as a least-privilege user, and be responsible.

    For now the assumption is that 'curl' command will be used.  (Patches to support the Power Shell
    Invoke-WebRequest cmdlet would be greatly welcomed!)

    ksconf rest-export --output=apply_props.sh etc/app/Splunk_TA_aws/local/props.conf
    """)
    format = "manual"
    maturity = "beta"

    def register_args(self, parser):
        parser.add_argument("conf", metavar="FILE", nargs="+",
                            type=ConfFileType("r", "load", parse_profile=PARSECONF_LOOSE),
                            help="Configuration file(s) to export settings from."
                            ).completer = conf_files_completer
        parser.add_argument("--output", "-t", metavar="FILE",
                            type=FileType("w"), default=sys.stdout,
                            help="Save the shell script output to this file.  "
                                 "If not provided, the output is written to standard output.")
        '''
        parser.add_argument("--syntax", choices=["curl", "powershell"],  # curl-windows?
                            default="curl",
                            help="Pick the output syntax mode.  "
                                 "Currently only 'curl' is supported.")
        '''
        parser.add_argument("-u", "--update", action="store_true", default=False,
                            help="Assume that the REST entities already exist.  "
                                 "By default output assumes stanzas are being created.  "
                                 "(This is an unfortunate quark of the configs REST API)")
        parser.add_argument("--url", default="https://localhost:8089",
                            help="URL of Splunkd.  Default:  %(default)s")
        parser.add_argument("--app", default="$SPLUNK_APP",
                            help="Set the namespace (app name) for the endpoint")
        parser.add_argument("--user", default="nobody",
                            help="Set the user associated.  Typically the default of 'nobody' is "
                                 "ideal if you want to share the configurations at the app-level.")

    @staticmethod
    def build_rest_url(base, user, app, conf):
        # XXX: Quote user & app; however for now we're still allowing the user to pass though an
        #  environmental variable as-is and quoting would break that.   Need to make a decision,
        # for now this is not likely to be a big issue given app and user name restrictions.
        url = "{}/servicesNS/{}/{}/configs/conf-{}".format(base, user, app, conf)
        return url


    def run(self, args):
        ''' Snapshot multiple configuration files into a single json snapshot. '''
        """

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
        #  XXX:  Someday make multiline output that looks pretty...  someday

        stream = args.output

        if True:
            # Make this preamble optional
            stream.write("## Example of creating a local SPLUNKDAUTH token\n")
            stream.write("export SPLUNKDAUTH=$("
                         "curl -ks {}/services/auth/login -d username=admin -d password=changeme "
                         "| grep sessionKey "
                         r"| sed -re 's/\s*<sessionKey>(.*)<.sessionKey>/\1/')".format(args.url))
            stream.write("\n\n\n")

        for conf_proxy in args.conf:
            conf = conf_proxy.data
            conf_type = os.path.basename(conf_proxy.name).replace(".conf", "")

            stream.write("# CURL REST commands for {}\n".format(conf_proxy.name))

            for stanza_name, stanza_data in conf.items():
                cc = CurlCommand()
                cc.url = self.build_rest_url(args.url, args.user, args.app, conf_type)

                if stanza_name is GLOBAL_STANZA:
                    # XXX:  Research proper handling of default/global stanazas..
                    # As-is, curl returns an HTTP error, but yet the new entry is added to the
                    # conf file.  So I suppose we could ignore the exit code?!    ¯\_(ツ)_/¯
                    stream.write("### WARN:  Writing to the default stanza may not work as "
                                 "expected.  Or it may work, but be reported as a failure.  "
                                 "Patches welcome!\n")
                    cc.url += "/default"
                elif args.update:
                    cc.url += "/" + quote(stanza_name, "")   # Must quote '/'s too.
                else:
                    cc.data["name"] = stanza_name

                # Add individual keys
                for (key, value) in stanza_data.items():
                    cc.data[key] = value

                cc.headers["Authorization"] = "Splunk $SPLUNKDAUTH"

                stream.write(cc.get_command())
                stream.write("\n")
            stream.write("\n")
        stream.write("\n")

        return EXIT_CODE_SUCCESS
