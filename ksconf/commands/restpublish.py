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

from six.moves.urllib.parse import urlparse

from ksconf.commands import KsconfCmd, dedent, ConfFileType, ConfFileProxy, \
    add_splunkd_access_args, add_splunkd_namespace
from ksconf.conf.parser import PARSECONF_LOOSE, GLOBAL_STANZA, conf_attr_boolean
from ksconf.conf.delta import compare_stanzas, show_diff, DIFF_OP_EQUAL, DiffHeader
from ksconf.consts import EXIT_CODE_SUCCESS
from ksconf.util.completers import conf_files_completer


# Lazy loaded by _handle_imports()
splunklib = None


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

    def __init__(self, *args, **kwargs):
        super(RestPublishCmd, self).__init__(*args, **kwargs)
        self._service = None

    @classmethod
    def _handle_imports(cls):
        g = globals()
        if globals()["splunklib"] is None:
            import splunklib.client
            g["splunklib"] = splunklib

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
        '''
        parsg1.add_argument("-u", "--update", action="store_true", default=False,
                            help="Assume that the REST entities already exist.")
        parsg1.add_argument("--update-only", action="store_true", default=False,
                            help="Only update existing entities.  "
                                 "Non-existent entries will be skipped.")
        '''
        parsg1.add_argument("-D", "--delete", action="store_true", default=False,
                            help=dedent("""\
            Remove existing REST entities.  This is a destructive operation.
            In this mode, stanzas attributes are unnecessary and therefore ignored.
            NOTE:  This works for 'local' entities only; the default folder cannot be updated.
            """))


    @staticmethod
    def make_boolean(stanza, attr="disabled"):
        if attr in stanza:
            stanza[attr] = "1" if conf_attr_boolean(stanza[attr]) else "0"

    def connect_splunkd(self, args):
        # Take username/password form URL, if encoded there; otherwise use defaults from argparse
        up = urlparse(args.url)
        username = up.username or args.user
        password = up.password or args.password
        self._service = splunklib.client.connect(
            hostname=up.hostname, port=up.port, username=username, password=password,
            owner=args.owner, app=args.app, sharing=args.sharing)

    def handle_conf_file(self, args, conf_proxy):
        if args.conf_type:
            conf_type = args.conf_type
        else:
            conf_type = os.path.basename(conf_proxy.name).replace(".conf", "")

        config_file = self._service.confs[conf_type]
        conf = conf_proxy.data

        for stanza_name, stanza_data in conf.items():

            if stanza_name is GLOBAL_STANZA:
                # XXX:  Research proper handling of default/global stanzas..
                # As-is, curl returns an HTTP error, but yet the new entry is added to the
                # conf file.  So I suppose we could ignore the exit code?!    ¯\_(ツ)_/¯
                sys.stderr.write("Refusing to touch the [default] stanza.  Too much could go wrong.\n")
                continue

            if args.delete:
                action, info = self.delete_conf(stanza_name, stanza_data, config_file)
            else:
                action, info = self.publish_conf(stanza_name, stanza_data, config_file)

            print("{:50} {:8}   (delta size: {})".format("[{}]".format(stanza_name), action, len(info.get("delta",[]))))

            update_time = info.get("updated", 0)
            rest_header = DiffHeader(info.get("path", config_file.path), update_time)
            if action != "nochange" and "delta" in info:
                show_diff(self.stdout, info["delta"], headers=(conf_proxy.name, rest_header))

    def publish_conf(self, stanza_name, stanza_data, config_file):
        # XXX:  Optimize for round trips to the server
        res = {}
        self.make_boolean(stanza_data)
        if stanza_name in config_file:
            ## print("Stanza {} already exists on server.  Checking to see if update is needed.".format(stanza_name))
            stz = config_file[stanza_name]
            stz_data = stz.content
            self.make_boolean(stz_data)
            res["path"] = stz.path
            try:
                res["updated"] = stz.state["updated"]
            except:
                # debug
                raise
            ## print("VALUE NOW:   (FROM SERVER)   {}".format(stz.content))  ## VERY NOISY!
            data = {key: value for (key, value) in stz_data.items() if key in stanza_data}
            ## print("VALUE NOW:   (FILTERED TO OUR ATTRS)   {}".format(data))
            delta = res["delta"] = list(compare_stanzas(data, stanza_data, stanza_name))
            if len(delta) == 1 and delta[0][0] == DIFF_OP_EQUAL:
                ## print("NO CHANGE NEEDED.")
                res["delta"] = []
                return ("nochange", res)
            stz.update(**stanza_data)
            return ("update", res)
        else:
            ## print("Stanza {} new -- publishing!".format(stanza_name))
            config_file.create(stanza_name, **stanza_data)
            res["delta"] = list(compare_stanzas(stanza_data, {}, stanza_name))
            return ("new", res)

    def delete_conf(self, stanza_name, stanza_data, config_file):
        res = {}
        if stanza_name in config_file:
            stz = config_file[stanza_name]
            stz_data = stz.content
            res["path"] = stz.path
            try:
                res["updated"] = stz.state["updated"]
            except:
                # debug
                raise
            self.make_boolean(stz_data)
            ## print("Found {}".format(stz_data))
            data = {key: value for (key, value) in stz_data.items() if key in stanza_data}
            config_file.delete(stanza_name)
            res["delta"] = list(compare_stanzas({}, data, stanza_name))
            return ("deleted", res)
        else:
            res["delta"] = []
            return ("nochange", res)

    def run(self, args):
        if args.insecure:
            raise NotImplementedError("Need to implement -k feature")

        self.connect_splunkd(args)
        for conf_proxy in args.conf:    # type: ConfFileProxy
            self.handle_conf_file(args, conf_proxy)

        return EXIT_CODE_SUCCESS
