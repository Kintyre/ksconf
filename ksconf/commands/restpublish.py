# -*- coding: utf-8 -*-
"""
SUBCOMMAND:  ``ksconf rest-publish <ENDPOINT> <CONF>``

Usage example:

.. code-block:: sh

    ksconf rest-publish MyApp/local/props.conf


"""
from __future__ import absolute_import, unicode_literals

import os
import sys
from argparse import ArgumentParser
from urllib.parse import urlparse

from ksconf.commands import (ConfFileProxy, ConfFileType, KsconfCmd,
                             add_splunkd_access_args, add_splunkd_namespace,
                             dedent)
from ksconf.conf.delta import DiffHeader, compare_stanzas, is_equal, reduce_stanza, show_diff
from ksconf.conf.meta import MetaData
from ksconf.conf.parser import GLOBAL_STANZA, PARSECONF_LOOSE, conf_attr_boolean
from ksconf.consts import EXIT_CODE_SUCCESS
from ksconf.util.completers import conf_files_completer

# Lazy loaded by _handle_imports()
splunklib = None


class RestPublishCmd(KsconfCmd):
    help = "Publish .conf settings to a live Splunk instance via REST"
    description = dedent("""\
    Publish stanzas in a .conf file to a running Splunk instance via REST.  This requires access to
    the HTTPS endpoint of Splunk.  By default, ksconf will handle both the creation of new stanzas
    and the update of existing stanzas.

    This can be used to push full configuration stanzas where you only have REST access and can't
    directly publish an app.

    Only attributes present in the conf file are pushed.  While this may seem obvious, this fact can
    have profound implications in certain situations, like when using this command for continuous
    updates.  This means that it's possible for the source .conf to ultimately differ from what ends
    up on the server's .conf file.  One way to avoid this, is to explicitly remove an object using
    ``--delete`` mode first, and then insert a new copy of the object.  Of course, this means that
    the object will be unavailable.  The other impact is that diffs only compares and shows a subset
    of attribute.

    Be aware, that for consistency, the configs/conf-TYPE endpoint is used for this command.
    Therefore, a reload may be required for the server to use the published config settings.
    """)

    maturity = "alpha"

    def __init__(self, *args, **kwargs):
        super(RestPublishCmd, self).__init__(*args, **kwargs)
        self._service = None
        self.meta: MetaData = None

    @classmethod
    def _handle_imports(cls):
        g = globals()
        if globals()["splunklib"]:
            return
        import splunklib.client
        g["splunklib"] = splunklib
        import splunklib
        cls.version_extra = f"splunk-sdk {splunklib.__version__}"

    def register_args(self, parser: ArgumentParser):
        parser.add_argument("conf", metavar="CONF", nargs="+",
                            type=ConfFileType("r", "load", parse_profile=PARSECONF_LOOSE),
                            help="Configuration file(s) to export settings from."
                            ).completer = conf_files_completer

        parser.add_argument("--conf", dest="conf_type", metavar="TYPE",
                            help=dedent("""\
            Explicitly set the configuration file type.  By default, this is derived from CONF, but
            sometimes it's helpful to set this explicitly. Can be any valid Splunk conf file type.
            Examples include: 'app', 'props', 'tags', 'savedsearches', etc."""))
        parser.add_argument("-m", "--meta", action="append",
                            help="Specify one or more ``.meta`` files to determine the desired read & "
                            "write ACLs, owner, and sharing for objects in the CONF file.")

        # add_splunkd_namespace(
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
            In this mode, stanza attributes are unnecessary.
            NOTE:  This works for 'local' entities only; the default folder cannot be updated.
            """))

    @staticmethod
    def make_boolean(stanza, attr="disabled"):
        if attr in stanza:
            stanza[attr] = "1" if conf_attr_boolean(stanza[attr]) else "0"

    def connect_splunkd(self, args):
        up = urlparse(args.url)
        # Take username/password form URL, if encoded there; otherwise use defaults from argparse
        if args.session_key:
            auth_args = {
                "token": args.session_key
            }
            login_fail_info = f"session={args.session_key[:10]}..."
        else:
            username = up.username or args.user
            password = up.password or args.password
            auth_args = {
                "username": username,
                "password": password,
            }
            login_fail_info = f"user={username} pass={'*' * len(password)}"
        try:
            self._service = splunklib.client.connect(
                host=up.hostname, port=up.port,
                owner=args.owner, app=args.app, sharing=args.sharing,
                **auth_args)
            # Sanity check to:
            #   (1) confirm that session key is good, and
            #   (2) confirm that that the given namespace (app) is legit.
            self._service.apps.list()
        except Exception as e:
            sys.stderr.write(f"Connect issue url=https://{up.hostname}:{up.port} "
                             f"{login_fail_info}:  {e}\n")
            raise e

    def handle_conf_file(self, args, conf_proxy):
        if args.conf_type:
            conf_type = args.conf_type
        else:
            conf_type = os.path.basename(conf_proxy.name).replace(".conf", "")


        try:
            config_file = self._service.confs[conf_type]
        except KeyError:
            self.stderr.write(f"Invalid conf type named '{conf_type}'.\n")
            return
        conf = conf_proxy.data

        # Sorting stanza for consistent processing of large files.  No CLI option for now.
        # XXX:  Support stanza order preservation after new parser is created (long-term)
        for stanza_name in sorted(conf):
            stanza_data = conf[stanza_name]

            if not stanza_data:
                print(f"Skipping empty stanza [{stanza_name}]")
                continue

            if stanza_name is GLOBAL_STANZA or stanza_name == "":
                # XXX:  Research proper handling of default/global stanzas..
                # As-is, curl returns an HTTP error, but yet the new entry is added to the
                # conf file.  So I suppose we could ignore the exit code?!    ¯\_(ツ)_/¯
                sys.stderr.write("Refusing to touch the [default] stanza.  Too much could go wrong.\n")
                continue

            if args.delete:
                action, info = self.delete_conf(stanza_name, stanza_data, config_file)
            else:
                action, info = self.publish_conf(stanza_name, stanza_data, config_file)

            print("{:50} {:8}   (delta size: {})".format("[{}]".format(stanza_name),
                                                         action, len(info.get("delta", []))))

            update_time = info.get("updated", 0)
            # headers = (conf_proxy.name, "{}/{}".format(args.url, config_file.path))
            # rest_header = DiffHeader("{}/{}".format(args.url, info.get("path", config_file.path), update_time))
            rest_header = DiffHeader(info.get("path", config_file.path), update_time)
            if action != "nochange" and "delta" in info:
                show_diff(self.stdout, info["delta"], headers=(conf_proxy.name, rest_header))

            if "meta" in info:
                print(info["meta"])

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

        res = {}
        # XXX:  Move boolean comparison stuff to the core delta detection library....
        self.make_boolean(stanza_data)

        try:
            stz = config_file[stanza_name]
        except KeyError:
            stz = None

        if stz is not None:
            # print(f"Stanza {stanza_name} already exists on server.  Checking to see if update is needed.")
            # When pulling do we need to specify this?  (owner=owner, app=app, sharing=sharing);
            # If meta is given and where these are different than the defaults on the CLI?...
            stz_data = stz.content

            # Diff printing really doesn't like 'None's...
            stz_data = {k: v or "" for k, v in stz_data.items()}
            self.make_boolean(stz_data)
            res["path"] = stz.path
            try:
                res["updated"] = stz.state["updated"]
            except Exception:
                pass
            # print(f"VALUE NOW:   (FROM SERVER)   {stz.content}")  ## VERY NOISY!
            data = reduce_stanza(stz_data, stanza_data)
            # print(f"VALUE NOW:   (FILTERED TO OUR ATTRS)   {data}")
            delta = res["delta"] = compare_stanzas(stanza_data, data, stanza_name)
            if is_equal(delta):
                # print("NO CHANGE NEEDED.")
                res["delta"] = []
                action = "nochange"
            else:
                stz.update(**stanza_data)
                # Any need to call .refresh() here to grab the state from the server?
                action = "update"
        else:
            # print(f"Stanza {stanza_name} new -- publishing!")
            stz = config_file.create(stanza_name, owner=owner, app=app, sharing=sharing, **stanza_data)
            res["delta"] = compare_stanzas({}, stanza_data, stanza_name)
            res["path"] = stz.path
            action = "new"

        # METADATA PUSH

        if not self.meta:
            return (action, res)

        if not int(stz.access["can_change_perms"]):
            res["meta"] = "Can't change meta according to 'can_change_perms'"
            return (action, res)

        # NOTE:  We don't support attribute-level metadata here (Need it?  2 words:  pull request)
        if not metadata:
            res["meta"] = f"No metadata found for [{config_file.name}/{stanza_name}]"
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

        # Build access dict for comparison purpose
        access = {}
        for x in ("owner", "app", "sharing"):
            access[x] = stz.access[x]
        for x in ("read", "write"):
            try:
                access["perms." + x] = ",".join(stz.access["perms"][x])
            except (KeyError, TypeError):
                access["perms." + x] = ""
        # print(f"[{stanza_name}] fm={final_meta} access:  {access}")

        acl_delta = compare_stanzas(reduce_stanza(access, final_meta), final_meta,
                                    stanza_name + "/acl")
        if is_equal(acl_delta):
            res["acl_delta"] = []
            return (action, res)
        else:
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
            # logger.debug("request to do the ACL THING!  (Round trip debugging)")
            response = svc.http.post(resource, all_headers, **final_meta)

            res["meta_response"] = response
        except Exception:
            # Don't die on exceptions for ACLs...  print the error and move on (too many things to go wrong here)
            print(f"Failed hitting:  {resource}  ARGS={final_meta}")
            import traceback
            traceback.print_exc()
            # XXX:  Do better

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
            # print(f"Found {stz_data}")
            data = reduce_stanza(stz_data, stanza_data)
            config_file.delete(stanza_name)
            res["delta"] = compare_stanzas(data, {}, stanza_name)
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
                print(f"Loading metadata from {meta_file}")
                self.meta.feed_file(meta_file)

        self.connect_splunkd(args)
        for conf_proxy in args.conf:    # type: ConfFileProxy
            self.handle_conf_file(args, conf_proxy)

        return EXIT_CODE_SUCCESS


'''
# For really crapy debug messages from splunksdk  (optimize server round trips)

import logging

logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
'''
