"""
This module contains all the plugin definitions (or hook "specifications") for various customization
or integration points with ksconf.  Not all of these have been fully tested so please let us know if
something is not working as expected, or if additional arguments are needed.

See `ksconf plugins <https://pypi.org/search/?q=ksconf&o=&c=Environment+%3A%3A+Plugins>`__ on pypi
for a list of currently available plugins.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from pluggy import HookspecMarker

from ksconf.consts import PLUGGY_HOOK

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace

    from jinja2 import Environment
else:
    Environment = Any
    ArgumentParser = Namespace = Any

# For Python 3.7 (Protocol added in 3.8)
try:
    from typing import Protocol
except ImportError:
    class Protocol:
        pass


class KsconfPluginWarning(Warning):
    pass


hookspec = HookspecMarker(PLUGGY_HOOK)


# Definitions of ksconf defined hooks

# Additional hooks to add someday:
#
#
# ksconf_cli_exit(return_code)
# ksconf_cli_unhandled_exception(exc_info...)
#


class KsconfHookSpecs(Protocol):
    """ Ksconf plugin specifications for all known supported functions.

    Grouping these functions together in a single class allows for type support
    it supports typing.  This adds a level of validation to the code base where
    a hook is invoked via ``plugin_manger.hook.<hook_name>()``.

    If you are implementing one of these hooks, please note that you can simple
    make top-level function, no need to implement a class.
    """
    # All methods are decorated with staticmethod, for equivalence with a plain function.

    @staticmethod
    @hookspec
    def ksconf_cli_init():
        """
        Simple hook that is run before CLI initialization.  This can be use to
        modify the runtime environment.

        This can be used to register additional handlers, such as:

        * :py:func:`ksconf.combine.register_handler` - Add a combination file handler.
          File types are limited to pattern matching.
        * :py:func:`ksconf.layer.register_file_handler` - Add file handlers for
          layer processing for template processing
        """
        ...

    @staticmethod
    @hookspec
    def ksconf_cli_modify_argparse(parser: ArgumentParser, name: str):
        """
        Manipulate argparse rules.  This could be used to add additional CLI
        options for other hook-added features added features

        Note that this hook is called for both the top-level argparse instance
        as well as each subparser.  The :py:obj:`name` argument should be
        inspected to determine if the parse instances is the parent (top-level)
        parser, or some other named subcommands.
        """
        ...

    @staticmethod
    @hookspec
    def ksconf_cli_process_args(args: Namespace):
        """
        Hook to capture all parsed arguments, includes any custom arguments
        added to the CLI via the the :py:func:`ksconf_cli_modify_argparse` hook.
        :py:obj:`args` can be mutated directly, if needed.
        """
        ...

    @staticmethod
    @hookspec
    def post_combine(target: Path, usage: str):
        """
        Trigger a custom action after a layer combining operation.  This is used
        by multiple ksconf subcommands and the API.

        This trigger could be used to modify the file system, trigger external
        operations, track/audit behaviors, and so on.

        When using CLI commands, :py:obj:`usage` should be either "combine" or
        "package" depending on which ksconf command was invoked.
        Direct invocation of :py:class:`~ksconf.combine.LayerCombiner` can pass
        along a custom usage label and avoid impacting CLI, when desirable.

        If your goal is to only trigger an action during the app packaging
        process, also consider the :py:func:`package_pre_archive` hook, which
        may be more appropriate.
        """
        ...

    @staticmethod
    @hookspec
    def package_pre_archive(app_dir: Path, app_name: str):
        """
        Modify, inventory, or test the contents of an app before the final
        packaging commands.  This can be triggered from the ``ksconf package``
        command or via the API.

        During a ``ksconf package`` process, this hook executes right before
        the final archive is created.  All local merging, app version or build
        updates, and so on are completed before this hook is executed.

        From an API perspective, this hook is  called from
        :py:class:`ksconf.package.AppPackager` whenever a content freeze occurs,
        which is typically when
        :py:meth:`~ksconf.package.AppPackager.make_archive` or
        :py:meth:`~ksconf.package.AppPackager.make_manifest` is invoked.
        """

    @staticmethod
    @hookspec
    def modify_jinja_env(env: Environment):
        """
        Modify the Jinja2 environment object.  This can be used to add custom
        filters or tests, for example.

        Invoked by :py:class:`~ksconf.layer.LayerFile_Jinja2` immediately after
        initial Environment creation.  :py:obj:`env` should be mutated in place.
        """
        ...
