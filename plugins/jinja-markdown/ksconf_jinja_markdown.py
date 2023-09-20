import commonmark
from jinja2 import Environment

from ksconf.hook import ksconf_hook


def markdown_to_html(md: str) -> str:
    """ Jinja filter for markdown to html """
    return commonmark.commonmark(md)


@ksconf_hook(specname="modify_jinja_env")
def add_jinja_filters(env: Environment):
    """ Register new filter(s) to the Jinja environment, for use within templates. """
    env.filters["markdown2html"] = markdown_to_html
