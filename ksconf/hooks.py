from pluggy import HookimplMarker, PluginManager

from ksconf.consts import PLUGGY_HOOK

# decorator to mark ksconf hooks
ksconf_hook = HookimplMarker(PLUGGY_HOOK)


_pm = None


def get_plugin_manager() -> PluginManager:   # noqa: E302
    """
    Return the shared pluggy PluginManager (singleton) instance.
    """
    import ksconf.hookspec
    global _pm
    if _pm is None:
        pm = PluginManager(PLUGGY_HOOK)
        pm.add_hookspecs(ksconf.hookspec)
        pm.load_setuptools_entrypoints("ksconf_plugin")
        _pm = pm
    return _pm


if __name__ == '__main__':
    pm = get_plugin_manager()
    print(pm.list_name_plugin())
