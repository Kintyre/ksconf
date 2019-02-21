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
from ksconf.conf.meta import MetaData
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

    In dry-run mode, the output of what would be pushed is shown.  Keep in mind that ONLY the
    attributes present in the conf file are pushed.  Therefore it's possible for the source .conf
    file to ultimately differ from what ends up on the server's .conf file.  To avoid this, you
    could remove the object using ``--delete`` mode and then insert a new copy of the object.
    This will make the object unavailable for a short period of time.

    Be aware that, for consistency, the configs/conf-TYPE endpoint is used for this command.
    Therefore, a reload may be required for the server to use the published config settings.
    """)

    maturity = "alpha"

    def __init__(self, *args, **kwargs):
        super(RestPublishCmd, self).__init__(*args, **kwargs)
        self._service = None
        self.meta = None        # type: MetaData

    @classmethod
    def _handle_imports(cls):
        g = globals()
        if globals()["splunklib"]:
            return
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
        parser.add_argument("-m", "--meta", action="append",
                            help=
                            "Specify one or more ``.meta`` files to determine the desired read & "
                            "write ACLs, owner, and sharing for objects in the CONF file.")

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
            ###headers = (conf_proxy.name, "{}/{}".format(args.url, config_file.path))
            #rest_header = DiffHeader("{}/{}".format(args.url, info.get("path", config_file.path), update_time))
            rest_header = DiffHeader(info.get("path", config_file.path), update_time)
            if action != "nochange" and "delta" in info:
                show_diff(self.stdout, info["delta"], headers=(conf_proxy.name, rest_header))

            if "acl_delta" in info:
                show_diff(self.stdout, info["acl_delta"])

    def publish_conf(self, stanza_name, stanza_data, config_file):
        if self.meta:
            metadata = self.meta.get(config_file.name, stanza_name)
            owner = metadata.get("owner", None)
            app = config_file.service.namespace.app
            if metadata.get("export", None) == "system":
                sharing = "global"
            else:
                # Could still be "user" technically; but it seems unlikely that '--meta' would be given
                # in that case.  Still, there's possible room for improvement.
                sharing = "app"
        else:
            metadata = {}
            owner = None
            sharing = None
            app = None

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
                action = "nochange"
            stz.update(**stanza_data)
            action = "update"
        else:
            ## print("Stanza {} new -- publishing!".format(stanza_name))
            stz = config_file.create(stanza_name, owner=owner, app=app, sharing=sharing, **stanza_data)
            res["delta"] = list(compare_stanzas(stanza_data, {}, stanza_name))
            action = "new"

        # METADATA PUSH

        if not self.meta:
            return (action, res)

        if not int(stz.access["can_change_perms"]):
            res["meta"] = "Can't change meta according to 'can_change_perms'"
            return (action, res)

        # ACL_FIELDS = ["access.read", "access.write", "owner", "sharing" ]

        # NOTE:  We don't support attribute-level metadata here (Need it?  2 words:  pull request)

        if not metadata:
            res["meta"] = "No metadata found for [{}/{}]".format(config_file.name, stanza_name)
            return (action, res)
        final_meta = {}
        if "access.read" in metadata:
            final_meta["perms.read"] = ",".join(metadata["access.read"])
        if "access.write" in metadata:
            final_meta["perms.write"] = ",".join(metadata["access.write"])
        if "owner" in metadata:
            final_meta["owner"] = metadata["owner"]
        else:
            final_meta["owner"] = "nobody"
        export = metadata.get("export", "")
        if export == "system":
            final_meta["sharing"] = "global"
        else:
            # Could still be "user" technically; but it seems unlikely that '--meta' would be given
            # in that case.  Still, there's possible room for improvement.
            final_meta["sharing"] = "app"

        current_meta = {k: v for k, v in stz.access.items() if k in final_meta}
        acl_delta = list(compare_stanzas(current_meta, final_meta, stanza_name + "/acl"))
        if len(acl_delta) == 1 and acl_delta[0][0] == DIFF_OP_EQUAL:
            ## print("NO CHANGE NEEDED.")
            res["acl_delta"] = []
        res["acl_delta"] = acl_delta

        resource = None
        try:
            # Wonky workaround.  See https://github.com/splunk/splunk-sdk-python/issues/207
            # config_file.service.http.post()
            # response = Endpoint(config_file.service, stz.path + "acl/").post(**final_meta)

            svc = config_file.service
            all_headers = svc.additional_headers + svc._auth_headers
            resource = svc.authority + \
                       svc._abspath(stz.path + "acl",
                                    owner=svc.namespace.owner, app=svc.namespace.app,
                                    sharing=svc.namespace.sharing)
            response = svc.http.post(resource, all_headers, **final_meta)

            res["meta_response"] = response
        except Exception:
            #raise
            # Don't die on exceptions for ACLs...  print the error and move on
            import traceback
            traceback.print_exc()
            try:
                print("Failed hitting:  {}  ARGS={}".format(resource, final_meta))
            except:
                pass
        return (action, res)

    def delete_conf(self, stanza_name, stanza_data, config_file):
        res = {}
        if stanza_name in config_file:
            stz = config_file[stanza_name]
            stz_data = stz.content
            res["path"] = stz.path
            try:
                res["updated"] = stz.state["updated"]
            except KeyError:
                # Doesn't matter
                pass

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

        if args.meta:
            self.meta = MetaData()
            for meta_file in args.meta:
                print("Loading metadata from {}".format(meta_file))
                self.meta.feed_file(meta_file)

        self.connect_splunkd(args)
        for conf_proxy in args.conf:    # type: ConfFileProxy
            self.handle_conf_file(args, conf_proxy)

        return EXIT_CODE_SUCCESS


'''
For really crapy debug messages from splunksdk:

import logging

logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

'''
