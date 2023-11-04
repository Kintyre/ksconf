
from pathlib import Path, PurePath

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ksconf.hook import ksconf_hook, plugin_manager
from ksconf.layer import LayerRenderedFile, register_file_handler


class LayerFile_Jinja2(LayerRenderedFile):
    @staticmethod
    def match(path: PurePath):
        return path.suffix == ".j2"

    @staticmethod
    def transform_name(path: PurePath):
        return path.with_name(path.name[:-3])

    @property
    def jinja2_env(self):
        # Use context object to 'cache' the jinja2 environment
        if not hasattr(self.layer.context, "jinja2_environment"):
            self.layer.context.jinja2_environment = self._build_jinja2_env()
        return self.layer.context.jinja2_environment

    def _build_jinja2_env(self):
        environment = Environment(
            undefined=StrictUndefined,
            loader=FileSystemLoader(self.layer.root),
            auto_reload=False)

        # Call plugin for jinja environment tweaking
        plugin_manager.hook.modify_jinja_env(env=environment)

        environment.globals.update(self.layer.context.template_variables)
        return environment

    def render(self, template_path: Path) -> str:
        rel_template_path = template_path.relative_to(self.layer.root)
        template = self.jinja2_env.get_template("/".join(rel_template_path.parts))
        value = template.render()
        return value


@ksconf_hook
def ksconf_cli_init():
    register = register_file_handler("jinja", priority=50, enabled=False)
    register(LayerFile_Jinja2)
