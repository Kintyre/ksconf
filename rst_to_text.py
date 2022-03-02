"""
https://stackoverflow.com/a/57120114/315892
Jul '19, By Hatshepsut, CC BY-SA 4.0
"""

import sys
import textwrap
import types

import docutils.nodes
import docutils.parsers.rst
import docutils.utils
import sphinx.builders.text
import sphinx.util.osutil
import sphinx.writers.text


def parse_rst(text) -> docutils.nodes.document:
    parser = docutils.parsers.rst.Parser()
    components = (docutils.parsers.rst.Parser,)
    settings = docutils.frontend.OptionParser(
        components=components
    ).get_default_values()
    document = docutils.utils.new_document("<rst-doc>", settings=settings)
    parser.parse(text, document)
    return document


if __name__ == "__main__":
    source = textwrap.dedent(
        """\
    ============
    Introduction
    ============

    Hello world.

    .. code-block:: bash

        $ echo Greetings.


    """
    )

    document = parse_rst(source)

    app = types.SimpleNamespace(
        srcdir=None,
        confdir=None,
        outdir=None,
        doctreedir="/",
        config=types.SimpleNamespace(
            text_newlines="native",
            text_sectionchars="=",
            text_add_secnumbers=False,
            text_secnumber_suffix=".",
        ),
        tags=set(),
        registry=types.SimpleNamespace(
            create_translator=lambda self, something, new_builder: sphinx.writers.text.TextTranslator(
                document, new_builder
            )
        ),
    )

    builder = sphinx.builders.text.TextBuilder(app)

    translator = sphinx.writers.text.TextTranslator(document, builder)

    document.walkabout(translator)

    print(translator.body)
