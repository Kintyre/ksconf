from __future__ import absolute_import, unicode_literals

import argparse
import logging
import os
import sys
import textwrap

from io import open

# Used by ksconf.commands.* (not locally here)
from textwrap import dedent

from ksconf.conf.parser import parse_conf, smart_write_conf, write_conf, ConfParserException, \
                               detect_by_bom
from ksconf.consts import SMART_CREATE
from ksconf.util import memoize, debug_traceback


class ConfDirProxy(object):
    def __init__(self, name, mode, parse_profile=None):
        self.name = name
        self._mode = mode
        self._parse_profile = parse_profile

    def get_file(self, relpath):
        path = os.path.join(self.name, relpath)
        return ConfFileProxy(path, self._mode, parse_profile=self._parse_profile, is_file=True)


class ConfFileProxy(object):
    def __init__(self, name, mode, stream=None, parse_profile=None, is_file=None):
        self.name = name
        if is_file is not None:
            self._is_file = is_file
        elif stream:
            self._is_file = False
        else:
            self._is_file = True
        self._stream = stream
        self._mode = mode
        # Not sure if there's a good reason to keep a copy of the data locally?
        self._data = None
        self._parse_profile = parse_profile or {}

    def is_file(self):
        return self._is_file

    def _type(self):
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
                try:
                    self.stream.seek(0)
                except:
                    raise

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

    def load(self, profile=None):

        if "r" not in self._mode:
            # Q: Should we mimic the exception caused by doing a read() on a write-only file object?
            raise ValueError("Unable to load() from {} with mode '{}'".format(self._type(),
                                                                              self._mode))
        parse_profile = dict(self._parse_profile)
        if profile:
            parse_profile.update(profile)
        data = parse_conf(self.stream, profile=parse_profile)
        return data

    def dump(self, data):
        if "+" not in self._mode and "w" not in self._mode:
            raise ValueError("Unable to dump() to {} with mode '{}'".format(self._type(),
                                                                            self._mode))
        # Feels like the right thing to do????  OR self._data = data
        self._data = None
        # write vs smart write here ----
        if self._is_file:
            self.close()
            return smart_write_conf(self.name, data)
        else:
            write_conf(self._stream, data)
            return SMART_CREATE

    def unlink(self):
        # Eventually this could trigger some kind of backup or recovery mechanism
        self.close()
        return os.unlink(self.name)

    def backup(self, bkname=None):
        # One option:  Write this file directly to the git object store.  Just need to store some
        # kind of index to allow the users to pull it back.   (Sill, would need of fall-back
        # mechanism).  Git shouldn't be a hard-dependency
        raise NotImplementedError

    def checksum(self, hash="sha256"):
        raise NotImplementedError


class ConfFileType(object):
    """Factory for creating conf file object types;  returns a lazy-loader ConfFile proxy class

    Started from argparse.FileType() and then changed everything.   With our use case, it's often
    necessary to delay writing, or read before writing to a conf file (depending on weather or not
    --dry-run mode is enabled, for example.)

    Instances of FileType are typically passed as type= arguments to the
    ArgumentParser add_argument() method.

    Keyword Arguments:
        - mode      A string indicating how the file is to be opened.  Accepts "r", "w", and "r+".
        - action    'none', 'open', 'load'.   'none' means no preparation or tests;  'open' means
                    make sure the file exists/openable;  'load' means make sure the file can be
                    opened and parsed successfully.
    """

    def __init__(self, mode='r', action="open", parse_profile=None, accept_dir=False):
        self._mode = mode
        self._action = action
        self._parse_profile = parse_profile or {}
        self._accept_dir = accept_dir

    def __call__(self, string):
        from argparse import ArgumentTypeError
        # the special argument "-" means sys.std{in,out}
        if string == '-':
            if 'r' in self._mode:
                cfp = ConfFileProxy("<stdin>", "r", stream=sys.stdin, is_file=False)
                if self._action == "load":
                    try:
                        d = cfp.data
                        del d
                    except ConfParserException as e:
                        raise ArgumentTypeError("failed to parse <stdin>: {}".format(e))
                return cfp
            elif 'w' in self._mode:
                return ConfFileProxy("<stdout>", "w", stream=sys.stdout, is_file=False)
            else:
                raise ValueError('argument "-" with mode {}'.format(self._mode))
        if self._accept_dir and os.path.isdir(string):
            return ConfDirProxy(string, self._mode, parse_profile=self._parse_profile)
        if self._action == "none":
            return ConfFileProxy(string, self._mode, parse_profile=self._parse_profile)
        else:
            try:
                encoding = detect_by_bom(string)
                stream = open(string, self._mode, encoding=encoding)
                cfp = ConfFileProxy(string, self._mode, stream=stream,
                                    parse_profile=self._parse_profile, is_file=True)
                if self._action == "load":
                    # Force file to be parsed by accessing the 'data' property
                    d = cfp.data
                    del d
                return cfp
            except IOError as e:
                message = "can't open '%s': %s"
                debug_traceback()
                raise ArgumentTypeError(message % (string, e))
            except ConfParserException as e:
                debug_traceback()
                raise ArgumentTypeError("failed to parse '%s': %s" % (string, e))
            except TypeError as e:
                debug_traceback()
                raise ArgumentTypeError("Parser config error '%s': %s" % (string, e))

    def __repr__(self):     # pragma: no cover
        args = self._mode, self._action, self._parse_profile
        args_str = ', '.join(repr(arg) for arg in args if arg != -1)
        return '%s(%s)' % (type(self).__name__, args_str)



# For now, just effectively a copy of RawDescriptionHelpFormatter
class MyDescriptionHelpFormatter(argparse.HelpFormatter):
    def _fill_text(self, text, width, indent):
        # Looks like this one is ONLY used for the top-level description
        return ''.join([indent + line for line in text.splitlines(True)])

    def _split_lines(self, text, width):
        text = self._whitespace_matcher.sub(' ', text).strip()
        return textwrap.wrap(text, width)




class KsconfCmd(object):
    """ Ksconf command specification base class. """
    help = None
    description = None
    format = "default"
    maturity = "alpha"

    def __init__(self, name):
        self.name = name.lower()
        # XXX:  Add logging support.  Find clean lines between logging and UI/console output.
        self.logger = logging.getLogger("ksconf.cmd.{}".format(self.name))
        self.stdin = sys.stdin
        self.stdout = sys.stdout
        self.stderr = sys.stderr

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

    def add_parser(self, subparser):
        # Passing in the object return by 'ArgumentParser.add_subparsers()'
        kwargs = {
            "help" : self.help,
            "description" : self.description,
        }
        if self.format == "manual":
            kwargs["formatter_class"] = MyDescriptionHelpFormatter
        self.parser = subparser.add_parser(self.name, **kwargs)
        self.parser.set_defaults(funct=self.launch)
        self.register_args(self.parser)

    def register_args(self, parser):
        """ This function in passed the """
        raise NotImplementedError

    def launch(self, args):
        """ Handle flow control between pre_run() / run() / post_run() """
        # If this fails, exception is passed up, no handling errors/logging done here.
        self.pre_run(args)

        exc = None
        try:
            return_code = self.run(args)
        except:
            exc = sys.exc_info()
            raise
        finally:
            # No matter what, post_run is called.
            self.post_run(args, exc)
        return return_code

    def pre_run(self, args):
        """ Pre-run hook.  Any exceptions here prevent run() from being called. """
        pass

    def run(self, args):
        """ Actual works happens here.  Return code should be an EXIT_CODE_* from consts. """
        raise NotImplementedError

    def post_run(self, args, exec_info=None):
        """ Any custom clean up work that needs done.  Allways called if run() was.  Presence of
       exc_info indicates failure. """
        pass



def _get_entrypoints_lib(group, name=None):
    import entrypoints

    # Monkey patch some attributes for better API compatibility
    entrypoints.EntryPoint.dist = property(lambda self: self.distro)

    if name:
        return entrypoints.get_single(group, name)
    else:
        from collections import OrderedDict
        # Copied from 'get_group_named()' except that it preserves order
        result = OrderedDict()
        for ep in entrypoints.get_group_all(group):
            if ep.name not in result:
                result[ep.name] = ep
        return result

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
    if name: raise NotImplementedError
    return get_entrypoints_fallback(group)

# Removed _get_pkgresources_lib as middle option
__get_entity_resolvers = [ _get_entrypoints_lib, _get_fallback ]

if "ksconf_cmd" in os.environ.get("KSCONF_DISABLE_PLUGINS", ""):
    # Only use the fallback built in mechanism.  This is helpful when unittesting and building docs
    # as we don't want to accidentally document/test code from other packages.
    __get_entity_resolvers = [ _get_fallback ]


# This caching is *mostly* beneficial for unittest CLI testing
@memoize
def get_entrypoints(group, name=None):

    for resolver in list(__get_entity_resolvers):
        results = None
        try:
            results = resolver(group, name=name)
        except ImportError:
            __get_entity_resolvers.remove(resolver)
        if results:
            return results
        # Otherwise try next technique ...
