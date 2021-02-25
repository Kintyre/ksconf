from __future__ import absolute_import, unicode_literals

import inspect
import re
import sys
from subprocess import Popen

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
    __slots__ = ["build_path", "source_path", "config", "verbosity", "_output"]

    def __init__(self, build, source=None, output=sys.stdout):
        self.build_path = build
        self.source_path = source
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
        self._log("EXEC:  {}".format(" ".join(args)), VERBOSE)
        process = Popen(args, cwd=self.build_path)
        process.wait()
        if process.returncode != 0:
            raise BuildExternalException("Exit code of {} while executing {}".format(
                process.returncode, executable))


from ksconf.builder.core import BuildManager
