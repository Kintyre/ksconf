from __future__ import absolute_import, unicode_literals

import inspect
import re
import os
import sys
from subprocess import Popen
from pathlib import Path
import argparse

from ksconf.consts import KSCONF_DEBUG, EXIT_CODE_INTERNAL_ERROR
from ksconf.ext.six import text_type

if sys.version_info < (3, 6):
    from ksconf.util.file import pathlib_compat
    Popen = pathlib_compat(Popen)
    del pathlib_compat


QUIET = -1
NORMAL = 0
VERBOSE = 1


class BuildExternalException(Exception):
    pass


class BuildCacheException(Exception):
    pass




class BuildStep(object):
    __slots__ = ["build_path", "source_path", "dist_path", "config", "verbosity", "_output"]

    def __init__(self, build, source=None, dist=None, output=sys.stdout):
        self.build_path = build
        self.source_path = source
        self.dist_path = dist
        self.config = {}
        self.verbosity = 0
        self._output = output

    def alternate_path(self, path):
        """ Construct a new BuildStep instance with only 'build_path' altered. """
        cls = self.__class__
        instance = cls(path)
        for slot in cls.__slots__:
            if slot != "build_path":
                setattr(instance, slot, getattr(self, slot))
        return instance

    @property
    def is_quiet(self):
        return self.verbosity <= QUIET

    def is_verbose(self):
        return self.verbosity >= VERBOSE

    def get_logger(self, prefix=None):
        # type: (str) -> typing.Callable[str, int]
        if prefix is None:
            prefix = inspect.currentframe().f_back.f_code.co_name
        elif re.match(r'[\w_]+', prefix):
            prefix = "[{}] ".format(prefix)

        def log(message, *args, **kwargs):
            message = "{} {}".format(prefix, message)
            return self._log(message, *args, **kwargs)
        return log

    def _log(self, message, verbosity=0):
        """ verbosity:  lower=more important,
            -1 = quiet
             0 = default
            +1 verbose
        """
        if verbosity <= self.verbosity:
            self._output.write(message)
            self._output.write("\n")

    def run(self, *args):
        """ Execute an OS-level command regarding the build process.
        The process will run withing the working directory of the build folder.
        """
        # X: Update the external pip call to detach stdout / stderr if self.is_quiet
        executable = args[0]
        self._log("EXEC:  {}".format(" ".join(text_type(s) for s in args), VERBOSE))
        process = Popen(args, cwd=self.build_path)
        process.wait()
        if process.returncode != 0:
            raise BuildExternalException("Exit code of {} while executing {}".format(
                process.returncode, executable))


from ksconf.builder.core import BuildManager


def default_cli(build_manager, build_funct, argparse_parents=()):
    # args: (BuildManager, Callable[BuildStep, argparse.Namespace], List[argparse.ArgumentParser]
    """
    This is the function you stick in the:  if __name__ == '__main__' section of your code :-)

    Pass in a BuildManager instance, and a callback function.  The callback function must accept
    (steps, args).  If you have need for custom arguments, you can add them to your own
    ArgumentParser instance and pass them to the argparse_parents keyword argument, and then handle
    additional 'args' passed into the callback function.
    """
    parser = argparse.ArgumentParser(parents=argparse_parents)
    parser.add_argument("--verbose", "-v", action="count", default=0)
    parser.add_argument("--quiet", "-q", action="count", default=0)
    parser.add_argument("--build", metavar="DIR", default="build",
                        help="Set build folder destination")
    parser.add_argument("--no-cache", action="store_true", default=False,
                        help="Disable caching")
    parser.add_argument("--taint-cache",
                        action="store_true", default=False)
    args = parser.parse_args()

    verbosity = args.verbose - args.quiet
    build_manager.set_folders(".", args.build)
    if args.no_cache:
        build_manager.disable_cache()
    if args.taint_cache:
        build_manager.taint_cache()
    step = build_manager.get_build_step()
    step.verbosity = verbosity

    try:
        return build_funct(step, args)
    except Exception as e:
        if KSCONF_DEBUG in os.environ:
            # XXX: instead of re-raising; write out traceback (with this final frame removed)?
            # Allow stack track to be dumped to screen for developer review/debugging
            raise
        sys.stderr.write("Unhandled exception in build process:  {}\n".format(e))
        sys.exit(EXIT_CODE_INTERNAL_ERROR)
