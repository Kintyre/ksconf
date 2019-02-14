# -*- coding: utf-8 -*-
"""
SUBCOMMAND:  ksconf rest-publish <ENDPOINT> <CONF>

Usage example:

    ksconf rest-publish MyApp/local/props.conf


"""
from __future__ import absolute_import, unicode_literals

import os
import sys
from argparse import ArgumentParser

from six.moves.urllib.parse import quote

from ksconf.util.rest import SplunkRestHelper
from ksconf.commands import KsconfCmd, dedent, ConfFileType, add_splunkd_access_args, add_splunkd_namespace
from ksconf.conf.parser import PARSECONF_LOOSE, GLOBAL_STANZA
from ksconf.consts import EXIT_CODE_SUCCESS
from ksconf.util.completers import conf_files_completer


#import splunklib.client
#c = splunklib.client.Configurations







def enable_requests_debug():
    # https://stackoverflow.com/questions/10588644/how-can-i-see-the-entire-http-request-thats-being-sent-by-my-python-application
    # Seems to work without the logging stuff (at least with Python 2.7); needs more testing
    try:
        import http.client as http_client
    except ImportError:
        # Python 2
        import httplib as http_client
    http_client.HTTPConnection.debuglevel = 1



class RestPublishCmd(KsconfCmd):
    help = "Publish .conf settings to a live Splunk instance via REST"
    description = dedent("""\
    Publish stanzas in a .conf file to a running Splunk instance via REST.  This requires access to
    the HTTPS endpoint of splunk.  By default, ksconf will handle both the creation of new stanzas
    and the update of exists stanzas without user interaction.

    This can be used to push full configuration stanzas where you only have REST access and can't
    directly publish an app.

    In dry-run mode, the output of what would be pushed is shown.  Keep in mind that ONLY the attributes present in the conf file will be pushed.


    Setting permissions is currently not supported.
    """)

    maturity = "alpha"

    def register_args(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument("conf", metavar="CONF", nargs="+",
                            type=ConfFileType("r", "load", parse_profile=PARSECONF_LOOSE),
                            help="Configuration file(s) to export settings from."
                            ).completer = conf_files_completer

        parser.add_argument("--conf", dest="conf_type", metavar="TYPE",
                            help=dedent("""\
                    Explicitly set the configuration file type.  By default this is derived from CONF, but
                    sometime it's helpful set this explicitly.  Can be any valid Splunk conf file type,
                    example include 'app', 'props', 'tags', 'savedsearches', and so on."""))

        #add_splunkd_namespace(
        #    add_splunkd_access_args(parser.add_argument("Splunkd endpoint")))

        add_splunkd_namespace(
            add_splunkd_access_args(parser))

        parsg1 = parser.add_mutually_exclusive_group(required=False)
        parsg1.add_argument("-u", "--update", action="store_true", default=False,
                            help="Assume that the REST entities already exist.")
        parsg1.add_argument("--update-only", action="store_true", default=False,
                            help="Only update existing entities.  "
                                 "Non-existent entries will be skipped.")
        parsg1.add_argument("-D", "--delete", action="store_true", default=False,
                            help=dedent("""\
            Remove existing REST entities.  This is a destructive operation.
            In this mode, stanzas attributes are unnecessary and therefore ignored.
            NOTE:  This works for 'local' entities only; the default folder cannot be updated.
            """))

    def run(self, args):
        """
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
        rest = SplunkRestHelper(args.url)
        if args.insecure:
            rest.set_verify(False)
        rest.login(args.user, args.password)

        enable_requests_debug()
        #rest._session.debug = True

        for conf_proxy in args.conf:
            conf = conf_proxy.data

            if args.conf_type:
                conf_type = args.conf_type
            else:
                conf_type = os.path.basename(conf_proxy.name).replace(".conf", "")

            for stanza_name, stanza_data in conf.items():

                #url = self.build_rest_url(args.url, args.user, args.app, conf_type)

                data = dict(stanza_data)


                entity = "configs/conf-{}".format(conf_type)

                method = "post"

                if stanza_name is GLOBAL_STANZA:
                    # XXX:  Research proper handling of default/global stanzas..
                    # As-is, curl returns an HTTP error, but yet the new entry is added to the
                    # conf file.  So I suppose we could ignore the exit code?!    ¯\_(ツ)_/¯
                    sys.stderr.write("Refusing to update the [default] entity.\n")
                    # entity += "/default"
                '''
                elif args.update or args.delete:
                    entity += "/" + quote(stanza_name, "")  # Must quote '/'s too.
                else:
                    data["name"] = stanza_name
                '''

                entity += "/" + quote(stanza_name, "")

                if args.delete:
                    method = "delete"
                else:
                    # Add individual keys
                    for (key, value) in stanza_data.items():
                        data[key] = value

                r = rest.get_entity(entity, args.owner, args.app)
                import json
                j = r.json()
                print(json.dumps(j, indent=2, sort_keys=True))
                if method == "post":
                    r = rest.put_entity(entity, data, args.owner, args.app)
                elif method == "delete":
                    r = rest.put_entity(entity, data, args.owner, args.app)

                print("Published [{}]    response: {}  {}".format(entity, r.status_code, r.json()))

        return EXIT_CODE_SUCCESS
