import os
import sys

from pluggy import HookimplMarker, PluginManager

from ksconf.consts import EXIT_CODE_BROKEN_PLUGIN, PLUGGY_DISABLE_HOOK, PLUGGY_HOOK, is_debug
from ksconf.hookspec import KsconfHookSpecs

# decorator to mark ksconf hooks
ksconf_hook = HookimplMarker(PLUGGY_HOOK)


class BadPluginWarning(UserWarning):
    """ Issue with one or more plugins """
    pass


class _plugin_manager:
    """
    Lazy loading PluginManager proxy that allows simple module-level access to
    'plugin_manager.hook.x' with typing.  This follows the singleton pattern.
    Everything is loaded upon first use.
    """

    def __init__(self):
        self.__plugin_manager = None
        self.__output = sys.stderr
        self.__revert_funct = None

    def log(self, message):
        self.__output.write(f"ksconf-plugin: {message}\n")

    def _startup(self):
        # This runs on demand, exactly once.
        self.__plugin_manager = pm = PluginManager(PLUGGY_HOOK)

        if PLUGGY_DISABLE_HOOK in os.environ:
            disabled_hooks = os.environ[PLUGGY_DISABLE_HOOK].split()
            for hook in disabled_hooks:
                self.log(f"Disabling {hook} by request!\n")
                pm.set_blocked(hook)

        pm.add_hookspecs(KsconfHookSpecs)

        # Disable *ALL* 'ksconf_plugin' hooks
        disabled_things = os.environ.get("KSCONF_DISABLE_PLUGINS", "").split()
        if "ksconf_plugin" in disabled_things:
            if is_debug:
                self.log("All plugins are disabled")
            return

        # XXX: Find a way to report *which* plugin failed.  For now, use traceback
        try:
            pm.load_setuptools_entrypoints("ksconf_plugin")
        except ModuleNotFoundError as e:
            self.log("Unable to load one or more ksconf plugins.  "
                     f"Please correct or uninstall the offending plugin.\n  {e}\n"
                     "Run with KSCONF_DEBUG=1 to see a traceback")
            if is_debug():
                raise e
            else:
                sys.exit(EXIT_CODE_BROKEN_PLUGIN)

        # Maybe this should be it's own setting someday?  (disconnected from KSCONF_DEBUG)
        if is_debug():
            self.enable_monitoring()

    def enable_monitoring(self):
        def before(hook_name, hook_impls, kwargs):
            if hook_impls:
                self.log(f"call start {hook_name}, impl={hook_impls} kwargs={kwargs}")

        def after(outcome, hook_name, hook_impls, kwargs):
            if hook_impls:
                self.log(f"call-end   {hook_name}, impl={hook_impls} kwargs={kwargs} "
                         f"return={outcome}\n")
        self.__revert_funct = self._plugin_manager.add_hookcall_monitoring(before, after)

    def disable_monitoring(self):
        if callable(self.__revert_funct):
            self.__revert_funct()
            return True
        return False

    @property
    def _plugin_manager(self) -> PluginManager:
        if self.__plugin_manager is None:
            self._startup()
        return self.__plugin_manager

    @property
    def hook(self) -> KsconfHookSpecs:
        return self._plugin_manager.hook

    def __getattr__(self, name: str):
        # Proxy all other content to PluginManager
        return getattr(self._plugin_manager, name)


# Shared singleton
plugin_manager = _plugin_manager()


def get_plugin_manager() -> _plugin_manager:
    """
    Return the shared pluggy PluginManager (singleton) instance.

    This is for backwards compatibility.  This was only added in v0.11.6; and replaced immediately after.
    """
    from warnings import warn
    warn("Please use 'plugin_manager' directly and not 'get_plugin_manager()'. "
         "This function will be removed in v0.13 or sooner.", DeprecationWarning)
    return plugin_manager


if __name__ == '__main__':
    print(plugin_manager.list_name_plugin())
