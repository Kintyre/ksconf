from __future__ import absolute_import, unicode_literals

import argparse
import logging
import os
import re
import sys
import textwrap
from argparse import ArgumentParser, ArgumentTypeError
from collections import namedtuple
from io import open
from textwrap import dedent
from warnings import warn

from ksconf import KsconfPluginWarning
from ksconf.conf.parser import (ConfParserException, ParserConfig,
                                detect_by_bom, parse_conf, smart_write_conf,
                                write_conf)
from ksconf.consts import EXIT_CODE_BAD_CONF_FILE, EXIT_CODE_NO_SUCH_FILE, SMART_CREATE, SmartEnum
from ksconf.util import debug_traceback, memoize

__all__ = [
    "KsconfCmd",
    "ConfDirProxy",
    "ConfFileProxy",
    "ConfFileType",
    "dedent",
    "get_all_ksconf_cmds",
    "get_entrypoints",
    "add_splunkd_access_args",
    "add_splunkd_namespace",
]


class ConfDirProxy:
    def __init__(self, name, mode, parse_profile=None):
        self.name = name
        self._mode = mode
        self._parse_profile = parse_profile

    def get_file(self, relpath):
        path = os.path.join(self.name, relpath)
        return ConfFileProxy(path, self._mode, parse_profile=self._parse_profile, is_file=True)


class ConfFileProxy:
    def __init__(self, name, mode, stream=None, parse_profile=None, is_file=None):
        self.name = name
        self._mode = mode
        if is_file is not None:
            self._is_file = is_file
        elif stream:
            self._is_file = False
        elif self.writable() or os.path.isfile(name):
            self._is_file = True
        else:
            self._is_file = False
        self._stream = stream

        # Not sure if there's a good reason to keep a copy of the data locally?
        self._data = None
        self._parse_profile = parse_profile or {}

    def __del__(self):
        if self.is_file():
            self.close()

    def exists(self):
        return os.path.isfile(self.name)

    def readable(self):
        return "r" in self._mode

    def writable(self):
        return "+" in self._mode or "w" in self._mode

    def is_file(self):
        # Is "seekable" a more appropriate distinction?  (match IOBase)
        return self._is_file

    def _type(self):    # pragma: no cover  (only used in exceptions)
        if self._is_file:
            return "file"
        else:
            return "stream"

    def close(self):
        if self._stream:
            if not self._stream.closed:
                try:
                    self._stream.close()
                finally:
                    del self._stream
        self._stream = None

    def reset(self):
        if self._data is not None:
            self._data = None
            if self.is_file():
                self.close()
            else:
                self.stream.seek(0)

    def set_parser_option(self, **kwargs):
        """ Setting a key to None will remove that setting. """
        profile = dict(self._parse_profile)
        for (k, v) in kwargs.items():
            if v is None:
                if k in profile:
                    del profile[k]
            else:
                cv = profile.get(k, None)
                if cv != v:
                    profile[k] = v
        if self._parse_profile != profile:
            self._parse_profile = profile
            self.reset()

    @property
    def stream(self):
        if self._stream is None:
            self._stream = open(self.name, self._mode)
        return self._stream

    @property
    def data(self):
        if self._data is None:
            self._data = self.load()
        return self._data

    @property
    def mtime(self):
        return os.stat(self.name).st_mtime

    def load(self, profile=None):
        if not self.readable():
            # Q: Should we mimic the exception caused by doing a read() on a write-only file object?
            raise ValueError(f"Unable to load() from {self._type()} with mode '{self._mode}'")
        parse_profile = dict(self._parse_profile)
        if profile:
            parse_profile.update(profile)
        data = parse_conf(self.stream, profile=parse_profile)
        return data

    def dump(self, data, **kwargs) -> SmartEnum:
        if not self.writable():      # pragma: no cover
            raise ValueError(f"Unable to dump() to {self._type()} with mode '{self._mode}'")
        # Feels like the right thing to do????  OR self._data = data
        self._data = None
        # write vs smart write here ----
        if self._is_file:
            self.close()
            return smart_write_conf(self.name, data, **kwargs)
        else:
            write_conf(self._stream, data, **kwargs)
            return SMART_CREATE

    def unlink(self):
        # Eventually this could trigger some kind of backup or recovery mechanism
        self.close()
        return os.unlink(self.name)

    '''
    def backup(self, bkname=None):
        # One option:  Write this file directly to the git object store.  Just need to store some
        # kind of index to allow the users to pull it back.   (Sill, would need of fall-back
        # mechanism).  Git shouldn't be a hard-dependency
        raise NotImplementedError

    def checksum(self, hash="sha256"):
        raise NotImplementedError
    '''


class ConfFileType:
    """Factory for creating conf file object types;  returns a lazy-loader ConfFile proxy class

    Started from FileType() and then changed everything.   With our use case, it's often
    necessary to delay writing, or read before writing to a conf file (depending on whether or not
    --dry-run mode is enabled, for example.)

    Instances of FileType are typically passed as type= arguments to the
    ArgumentParser add_argument() method.


    :param mode: How the file is to be opened.  Accepts "r", "w", and "r+".
    :type mode: str
    :param action: Determine how much work should be handled during argument parsing vs handed off
                   to the caller.  Supports 'none', 'open', 'load'.  Full descriptions below.
    :type action: str
    :param parse_profile: parsing configuration settings passed along to the parser
    :param bool accept_dir: Should the CLI accept a directory of config files instead of an
                            individual file.  Defaults to `False`.

    **Values for action**

    ========    =============
    Action      Description
    ========    =============
    ``none``    No preparation or testing is done on the filename.
    ``open``    Ensure the file exists and can be opened.
    ``load``    Ensure the file can be opened and parsed successfully.
    ========    =============


    Once invoked, instances of this class will return a :class:`ConfFileProxy` object, or a
    :class:`ConfDirProxy` object if a directory is passed in via the CLI.
    """

    def __init__(self, mode='r', action="open",
                 parse_profile: ParserConfig = None,
                 accept_dir: bool = False):
        self._mode = mode
        self._action = action
        self._parse_profile = parse_profile or {}
        self._accept_dir = accept_dir

    def __call__(self, string):
        # the special argument "-" means sys.std{in,out}
        if string == '-':
            if 'r' in self._mode:
                cfp = ConfFileProxy("<stdin>", "r", stream=sys.stdin, is_file=False)
                if self._action == "load":
                    try:
                        cfp.data  # noqa: F841
                    except ConfParserException as e:
                        raise ArgumentTypeError(f"failed to parse <stdin>: {e}")
                return cfp
            elif 'w' in self._mode:
                return ConfFileProxy("<stdout>", "w", stream=sys.stdout, is_file=False)
            else:
                raise ValueError(f'argument "-" with mode {self._mode}')
        if self._accept_dir and os.path.isdir(string):
            return ConfDirProxy(string, self._mode, parse_profile=self._parse_profile)
        if self._action == "none":
            return ConfFileProxy(string, self._mode, parse_profile=self._parse_profile)
        else:
            try:
                # Another possible option is using:  seekable()  but that only works ONCE the stream is open
                if os.path.isfile(string):
                    encoding = detect_by_bom(string)
                    stream = open(string, self._mode, encoding=encoding)
                    cfp = ConfFileProxy(string, self._mode, stream=stream,
                                        parse_profile=self._parse_profile, is_file=True)
                else:
                    # Could be an explicit link to /dev/stdin; or /dev/fd/63; a bash <(cmd) input
                    # Assume UTF-8 here because that's the default encoding expected by Splunk
                    stream = open(string, self._mode, encoding="utf-8")
                    cfp = ConfFileProxy(string, self._mode, stream=stream,
                                        parse_profile=self._parse_profile, is_file=False)
                if self._action == "load":
                    # Force file to be parsed by accessing the 'data' property
                    cfp.data  # noqa: F841
                return cfp
            except IOError as e:
                debug_traceback()
                raise ArgumentTypeError(f"can't open '{string}': {e}")
            except ConfParserException as e:
                debug_traceback()
                raise ArgumentTypeError(f"failed to parse '{string}': {e}")
            except TypeError as e:
                debug_traceback()
                raise ArgumentTypeError(f"Parser config error '{string}': {e}")

    def __repr__(self):     # pragma: no cover
        args = self._mode, self._action, self._parse_profile
        args_str = ', '.join(repr(arg) for arg in args if arg != -1)
        return f"{type(self).__name__}({args_str})"


class DescriptionFormatterNoReST(argparse.HelpFormatter):
    @staticmethod
    def strip_simple_rest(s):
        # No handling of embedded backticks for now...  let's keep this simple
        # Replace literals ``X`` with single quote version:  'X'
        s = re.sub(r'``([^`]*)``', r"'\1'", s)
        # Handle simple references and other named inline markups
        # Handle explicitly named entry first, Use "<title>"
        s = re.sub(r':[a-z][a-z-]{1,10}[a-z]:`[^`]*? <([^`>]*)>\s*`', r"\1", s)
        # Just keep the content of the ref name as-is.  (no "<title>")
        s = re.sub(r':[a-z][a-z-]{1,10}[a-z]:`([^`]*)`', r"'\1'", s)
        return s

    def _fill_text(self, text, width, indent):
        text = self.strip_simple_rest(text)
        text = self._whitespace_matcher.sub(' ', text).strip()
        return textwrap.fill(text, width, initial_indent=indent,
                             subsequent_indent=indent)

    def _split_lines(self, text, width):
        text = self.strip_simple_rest(text)
        text = self._whitespace_matcher.sub(' ', text).strip()
        return textwrap.wrap(text, width)


class DescriptionHelpFormatterPreserveLayout(DescriptionFormatterNoReST):

    def _fill_text(self, text, width, indent):
        text = self.strip_simple_rest(text)
        # Looks like this one is ONLY used for the top-level description
        return ''.join([indent + line for line in text.splitlines(True)])


class KsconfCmdReadConfException(Exception):
    def __init__(self, rc):
        self.returncode = rc


class KsconfCmd:
    """ Ksconf command specification base class. """
    help = None
    description = None
    format = "default"
    maturity = "alpha"
    version_extra = None

    def __init__(self, name):
        self.name = name.lower()
        # XXX:  Add logging support.  Find clean lines between logging and UI/console output.
        self.logger = logging.getLogger(f"ksconf.cmd.{self.name}")
        self.stdin = sys.stdin
        self.stdout = sys.stdout
        self.stderr = sys.stderr
        self.parse_profile = {}

    @classmethod
    def _handle_imports(cls):
        """ Child classes can override this to provide a save place to import 3rd party modules.

        Any ImportErrors thrown here are handled as a special case.  Allow the user of external
        module without killing the entire suite due to one missing library. """
        pass

    '''
    def redirect_io(self, stdin=None, stdout=None, stderr=None):
        if stdin is not None:
            self.stdin = stdin
        if stdout is not None:
            self.stdout = stdout
        if stderr is not None:
            self.stderr = stderr

    def exit(self, exit_code):
        """ Allow overriding for unittesting or other high-level functionality, like an
        interactive interface. """
        sys.exit(exit_code)
    '''

    def add_parser(self, subparser):
        # Passing in the object return by 'ArgumentParser.add_subparsers()'
        kwargs = {
            "help": self.help,
            "description": self.description,
        }
        if self.format == "manual":
            kwargs["formatter_class"] = DescriptionHelpFormatterPreserveLayout
        else:
            kwargs["formatter_class"] = DescriptionFormatterNoReST
        self.parser = subparser.add_parser(self.name, **kwargs)
        self.parser.set_defaults(funct=self.launch)
        self.register_args(self.parser)

    def register_args(self, parser: ArgumentParser):        # pragma: no cover
        """ This function in passed the """
        raise NotImplementedError

    def launch(self, args):
        """ Handle flow control between pre_run() / run() / post_run() """
        # If this fails, exception is passed up, no handling errors/logging done here.
        return_code = self.pre_run(args)
        if return_code:
            return return_code

        exc = None
        try:
            return_code = self.run(args)
        except KsconfCmdReadConfException as e:
            return_code = e.returncode
        except BrokenPipeError:    # pragma: no cover
            try:
                self.stderr.write("Broken pipe\n")
            except Exception:
                pass
        except BaseException:     # pragma: no cover
            exc = sys.exc_info()
            raise
        finally:
            # No matter what, if run() was called, so is post_run()
            self.post_run(args, exc)
        return return_code

    def pre_run(self, args):
        """ Optional pre-run hook.
        Any exceptions or non-0 return code, will prevent run()/post_run() from being called. """
        pass

    def run(self, args):    # pragma: no cover
        """ Actual works happens here.  Return code should be an EXIT_CODE_* from consts. """
        raise NotImplementedError

    def post_run(self, args, exec_info=None):
        """ Optional custom clean up method.
        Always called if run() was.  The presence of exc_info indicates failure. """
        pass

    # Helper functions

    def _parse_conf(self, path, mode, profile):
        p = dict(self.parse_profile)
        if profile:
            p.update(profile)
        if path == "-":
            cfp = ConfFileProxy("<stdin>", "r", stream=sys.stdin, is_file=False)
        else:
            encoding = detect_by_bom(path)
            stream = open(path, mode, encoding=encoding)
            cfp = ConfFileProxy(path, mode, stream=stream,
                                parse_profile=p, is_file=True)
        d = cfp.data
        del d
        return cfp

    def parse_conf(self, path: str, mode: str = "r",
                   profile: ParserConfig = None,
                   raw_exec: bool = False) -> ConfFileProxy:
        if raw_exec:
            return self._parse_conf(path, mode, profile)
        try:
            return self._parse_conf(path, mode, profile)
        except IOError as e:
            # debug_traceback()
            self.stderr.write(f"can't open '{path}': {e}\n")
            raise KsconfCmdReadConfException(EXIT_CODE_NO_SUCH_FILE)
        except ConfParserException as e:
            # debug_traceback()
            self.stderr.write(f"Failed to parse '{path}':  {e}\n")
            raise KsconfCmdReadConfException(EXIT_CODE_BAD_CONF_FILE)
        except TypeError as e:
            # debug_traceback()
            self.stderr.write(f"Parser config error '{path}': {e}\n")
            # I guess bad conf file.... can't remember what this one is for.
            raise KsconfCmdReadConfException(EXIT_CODE_BAD_CONF_FILE)


def add_splunkd_access_args(parser: ArgumentParser) -> ArgumentParser:
    parser.add_argument("--url", default="https://localhost:8089",
                        help="URL of Splunkd.  Default:  %(default)s")
    parser.add_argument("--user", default="admin",
                        help="Login username Splunkd.  Default:  %(default)s")
    parser.add_argument("--pass", dest="password", default="changeme",
                        help="Login password Splunkd.  Default:  %(default)s")
    parser.add_argument("-k", "--insecure", action="store_true", default=False,
                        help="Disable SSL cert validation.")
    parser.add_argument("--session-key", default=None,
                        help="Use an existing session token instead of using a "
                             "username and password to login.")
    return parser


def add_splunkd_namespace(parser: ArgumentParser) -> ArgumentParser:
    parser.add_argument("--app", default="$SPLUNK_APP",
                        help="Set the namespace (app name) for the endpoint")
    parser.add_argument("--owner", default="nobody",
                        help="Set the user who owns the content.  "
                             "The default of 'nobody' works well for app-level sharing.")
    parser.add_argument("--sharing", default="global", choices=["user", "app", "global"],
                        help="Set the sharing mode.")
    return parser


def _get_entrypoints_lib(group, name=None):
    import entrypoints

    # Monkey patch some attributes for better API compatibility
    entrypoints.EntryPoint.dist = property(lambda self: self.distro)

    if name:
        return entrypoints.get_single(group, name)
    else:
        return entrypoints.get_group_named(group)


# TODO:  Switch to importlib.metadata once ksconf is Python 3.8+ (Could use importlib_metadata backport)
# TODO:  Find out if Splunk ships with importlib.metadata

""" Disabling this.   Because the DistributionNotFound isn't thrown until the entrypoint.load()
function is called outside of our control.   Going with 'entrypoints' module or local fallback,
giving up on the built-in utility...

def _get_pkgresources_lib(group, name=None):
    # Part of setuptools (widely used but quite slow); It's presence can't be assumed
    if name: raise NotImplementedError
    import pkg_resources
    d = {}
    try:
        for entrypoint in pkg_resources.iter_entry_points(group):
            d[entrypoint.name] = entrypoint
    except pkg_resources.DistributionNotFound:
        # Not really the same thing, but for our purposes; it's close enough, and we can't catch
        # this directly as we can't guarantee pkg_resources is available in the first place...
        raise ImportError
    return d
"""


def _get_fallback(group, name=None):
    from ksconf.setup_entrypoints import get_entrypoints_fallback
    entrypoints = get_entrypoints_fallback(group)
    if name is None:
        return entrypoints
    else:
        return entrypoints[name]


# Removed _get_pkgresources_lib as middle option
__get_entity_resolvers = [_get_entrypoints_lib, _get_fallback]

if "ksconf_cmd" in os.environ.get("KSCONF_DISABLE_PLUGINS", ""):    # pragma: no cover
    # Only use the fallback built in mechanism.  This is helpful when unittesting and building docs
    # as we don't want to accidentally document/test code from other packages.
    __get_entity_resolvers = [_get_fallback]


# This caching is *mostly* beneficial for unittest CLI testing
@memoize
def get_entrypoints(group, name=None):

    for resolver in list(__get_entity_resolvers):
        results = None
        try:
            results = resolver(group, name=name)
        except ImportError:    # pragma: no cover
            __get_entity_resolvers.remove(resolver)
        if results:
            return results
        # Otherwise try next technique ...


KsconfCmdEntryPoint = namedtuple("KsconfCmdEntryPoint", ["name", "entry", "cmd_cls", "error"])


def get_all_ksconf_cmds(on_error="warn"):
    for (name, entry) in get_entrypoints("ksconf_cmd").items():
        try:
            cmd_cls = entry.load()
        except (ImportError, NameError, SyntaxError) as e:
            if on_error == "warn":
                warn(f"Unable to load entrypoint for {name}.  Disabling.\n"
                     f"Base exception {e}.", KsconfPluginWarning)
            elif on_error == "return":
                error = f"Internal error:  {e}"
                yield KsconfCmdEntryPoint(name, entry, None, error)
            else:
                raise e
            continue
        if not issubclass(cmd_cls, KsconfCmd):
            msg = "Issue loading class for entrypoint:  Disabling.\n" \
                  f"{entry!r} is not derived from KsconfCmd.  "
            if on_error == "warn":
                warn(msg, KsconfPluginWarning)
            elif on_error == "return":
                yield KsconfCmdEntryPoint(name, entry, cmd_cls, msg)
            else:
                raise RuntimeError(msg)
            continue
        try:
            cmd_cls._handle_imports()
        except ImportError as e:
            if hasattr(e, "name"):         # PY3
                module = e.name
            else:
                module = e
            if on_error == "warn":
                warn(f"Unable to load external modules for {name}.  Disabling.  "
                     f"{module}.", KsconfPluginWarning)
            elif on_error == "return":
                error = f"Missing 3rd party module:  {module}"
                yield KsconfCmdEntryPoint(name, entry, cmd_cls, error)
            else:
                raise e
            continue
        yield KsconfCmdEntryPoint(name, entry, cmd_cls, None)
