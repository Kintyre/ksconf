from __future__ import absolute_import, annotations, unicode_literals

import argparse
import inspect
import re
import sys
from pathlib import Path
from subprocess import Popen
from typing import Callable, List, Optional, TextIO

from ksconf.consts import EXIT_CODE_INTERNAL_ERROR, is_debug

QUIET = -1
NORMAL = 0
VERBOSE = 1


class BuildExternalException(Exception):
    pass


class BuildCacheException(Exception):
    pass


class BuildStep:
    __slots__ = ["build_path", "source_path", "dist_path", "config", "verbosity", "_output"]

    def __init__(self,
                 build: Path,
                 source: Optional[Path] = None,
                 dist: Optional[Path] = None,
                 output: TextIO = sys.stdout):
        self.build_path = build
        self.source_path = source
        self.dist_path = dist
        self.config = {}
        self.verbosity = 0
        self._output = output

    def alternate_path(self, path) -> BuildStep:
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

    def get_logger(self, prefix: Optional[str] = None) -> Callable:
        if prefix is None:
            prefix = inspect.currentframe().f_back.f_code.co_name
        elif re.match(r'[\w_]+', prefix):
            prefix = f"[{prefix}] "

        def log(message, *args, **kwargs):
            message = f"{prefix} {message}"
            return self._log(message, *args, **kwargs)
        return log

    def _log(self, message, verbosity=0):
        """ verbosity:  lower=more important,
            -1 = quiet
             0 = default
            +1 verbose
        """
        if int(verbosity) <= self.verbosity:
            self._output.write(message)
            self._output.write("\n")

    def run(self, executable, *args, cwd=None):
        """ Execute an OS-level command regarding the build process.
        The process will run withing the working directory of the build folder.

        :param str executable: Executable to launch for a build step.
        :param str args: Additional argument(s) for the new process.
        :param str cwd:  Optional kw arg to change the working directory.  This
                         defaults to the build folder.
        """
        # XXX: Update the external pip call to detach stdout / stderr if self.is_quiet
        args = [executable] + [str(s) for s in args]
        cwd = cwd or str(self.build_path)
        exec_info = " ".join(str(s) for s in args)
        self._log(f"EXEC:  {exec_info}  cwd={cwd}", VERBOSE)
        process = Popen(args, cwd=cwd)
        process.wait()
        if process.returncode != 0:
            raise BuildExternalException(f"Exit code of {process.returncode} "
                                         f"while executing {executable}")

    def run_ksconf(self, *args, cwd=None):
        """ Execute 'ksconf' command in the build folder.
        Currently this runs as a separate process, but in the future is may be
        optimized to run from within the same python process.  This is an
        implementation detail the caller shouldn't care about.

        :param str args: Additional argument(s) for the ksconf command.
        :param str cwd:  Optional kw arg to change the working directory.  This
                         defaults to the build folder.
        """
        # Historically '-m ksconf' was used, but here safely skip python version check
        return self.run(sys.executable, "-m", "ksconf.cli", *args, cwd=cwd)


from ksconf.builder.core import BuildManager  # noqa


def default_cli(build_manager: BuildManager,
                build_funct: Callable,
                argparse_parents: List[argparse.ArgumentParser] = ()):
    """
    This is the function you stick in the:  ``if __name__ == '__main__'`` section of your code :-)

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
    if not build_manager.is_folders_set():
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
        if is_debug():
            # XXX: instead of re-raising; write out traceback (with this final frame removed)?
            # Allow stack track to be dumped to screen for developer review/debugging
            raise
        sys.stderr.write(f"Unhandled exception in build process:  {e}\n")
        sys.exit(EXIT_CODE_INTERNAL_ERROR)
