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


hookspec = HookspecMarker(PLUGGY_HOOK)


# Definitions of ksconf defined hooks

# Additional hooks to add someday:
#
#
# ksconf_cli_exit(return_code)
# ksconf_cli_unhandled_exception(exc_info...)
#


@hookspec
def ksconf_cli_init():
    """
    Simple hook that is run before CLI initialization.  This can be use to modify
    the runtime environment.

    This can be used to register additional handlers, such as:

    * :py:func:`ksconf.combine.register_handler` - Add a combination file handler (based on pattern matching)
    * :py:func:`ksconf.layer.register_file_handler` - Add file handlers for layer processing for template processing
    """
    ...


@hookspec
def ksconf_cli_modify_argparse(parser: ArgumentParser, name: str):
    """
    Manipulate argparse rules.  This could be used to add additional CLI options
    for other hook-added features added features

    Note that this hook is called for both the top-level argparse instance as well as each subparser.
    The ``name`` argument should be inspected to determine if the parse instances is the parent
    (top-level) parser, or some other named subcommands.
    """
    ...


@hookspec
def ksconf_cli_process_args(args: Namespace):
    """
    Hook to capture any custom arguments added to the CLI by the ``ksconf_cli_modify_argparse()`` hook.
    """
    ...


@hookspec
def post_combine(target: Path, usage: str):
    """
    ``usage`` should be either "combine" or "package" depending on which ksconf
    command was invoked.  Internally the combine process is used by both.
    """
    ...


@hookspec
def package_pre_archive(app_dir: Path, app_name: str):
    """
    During a ``ksconf package`` process, this hook executes right before the final archive is
    created.
    """


@hookspec
def modify_jinja_env(env: Environment):
    """
    Modify the Jinja2 environment object in place.  This can be used to add
    custom filters or tests, for example.
    Invoked by :py:class:`ksconf.layer.LayerFile_Jinja2` immediately after
    initial Environment creation.  ``env`` should be mutated in place.
    """
    ...
