Plugins
-------

Ksconf supports a growing number of plugins to enable custom workflow and and elegantly handle custom use cases that don't make sense to implement in the core tool.
Plugins functionality is implemented using `pluggy`_.

Note that, much like the pluggy docs themselves, we use the term "hook" and "plugin" are used interchangeably at times.
Generally, the term "hook" is a specific handoff point where control can be passed from the ksconf codebase to some hook function that you've implemented to perform a specific operation.
The term "plugin" refers to a package (or collection) of implemented hooks.

There are multiple ways of enabling these hooks or collections, but the easiest way is by means of registration process built into Python's packaging system.
This means that by simply installing a package, brand new functionality can be enabled within your ``ksconf`` command line.
Over time, we hope that more of these plugins can be published and made available to a wider audience on pypi.


Using plugins
=============

Existing plugins can be found on pypi by search for the `ksconf-* <https://pypi.org/search/?q=ksconf&o=&c=Environment+%3A%3A+Plugins>`__ package prefix.
With a little bit of Python experience, it's relatively simple to write your own.

Installation should be as simple as using your favorite package manager to install the plugin.  For example:

.. code-block:: sh

    pip install ksconf-<plugin-name>

Once installed, you can confirm which plugins are loaded and activated using ``--version``.


.. code-block:: sh

    ksconf --version

Output:

::

    _                   ___
    | |_ ___ ___ ___ ___|  _|
    | '_|_ -|  _| . |   |  _|
    |_,_|___|___|___|_|_|_|

    ksconf 0.11.6.dev3+e508597.dirty
    Python: 3.9.16  (/Users/username/venv/bin/python)
    Git SHA1 e508597d committed on 2023-09-20
    Installed at: /Users/username/sandbox/ksconf
    Platform:  Darwin Kernel Version 22.6.0: Wed Jul  5 22:22:05 PDT 2023; root:xnu-8796.141.3~6/RELEASE_ARM64_T6000
    Git support:  (/usr/bin/git) git version 2.39.2 (Apple Git-143)
    Plugins:
      package ksconf-jinja-markdown (1.0.0) from /Users/lalleman/ksconf/plugins/jinja-markdown/ksconf_jinja_markdown.py
        hook    modify_jinja_env via add_jinja_filters
    ...

Note that your installation will likely look different.


Troubleshooting
===============

Review hook execution
~~~~~~~~~~~~~~~~~~~~~

Currently enabling hook monitoring is handled by ``KSCONF_DEBUG`` which also controls several other troubleshooting operations, such as enabling stack traces when exceptions occur.


Disable individual plugins
~~~~~~~~~~~~~~~~~~~~~~~~~~


Plugins can be temporarily banned by using the ``KSCONF_PLUGIN_DISABLE`` environment variable.

..  code-block:: sh

    # Block for your entire session (or add to ~/.bashrc?)
    export KSCONF_PLUGIN_DISABLE="jinja-markdown test-plugin2"

    # Quick interactive ban (for a quick test)
    KSCONF_PLUGIN_DISABLE=jinja-markdown ksconf package ...

To permanently ban the plugin, simply remove the corresponding python package.

..  code-block:: sh

    pip uninstall ksconf-jinja-markdown



List of plugins
===============

All plugins are defined within :py:class:`~ksconf.hookspec.KsconfHookSpecs`.

.. it would be nice to have a table here...  Not sure how to do that easily... (more importantly, how to keep that in-sync with the code.


Plugin examples
===============


Modify Jinja Environment
~~~~~~~~~~~~~~~~~~~~~~~~

The :py:func:`~ksconf.hookspec.KsconfHookSpecs.modify_jinja_env` hook allows for modification of the Jinja2 environment so that custom filters can be added.
This very specific hook allows a rendered Jinja2 layer file to use custom Jinja filter, so that in this case, markdown content can be rendered as HTML.

.. code-block:: python

    from ksconf.hook import ksconf_hook
    from jinja2 import Environment

    def markdown_to_html(md):
        """ Jinja filter for markdown to html """
        import commonmark
        return commonmark.commonmark(md)

    @ksconf_hook(specname="modify_jinja_env")
    def add_jinja_filters(env: Environment):
        """ Register new filter(s) to the Jinja environment, for use within templates. """
        env.filters["markdown2html"] = markdown_to_html


This specific example is bundled up as python package and is installable via:

..  code-block:: sh

    pip install ksconf-jinja-markdown



Packaging a Plugin
==================

Packing is fairy easy, and there are examples in the ``plugins`` folder in the ksconf GitHub repository.
This example assumes your packing a plugin that lives in a ``ksconf/plugins/fancy_plugin.py``.
Note that the ``ksconf/plugins`` is a top-level directory that puts your new plugin in the ``ksconf.plugins`` namespace.
(This isn't technically required, but it's the recommended approach.)

Here's an example of a ``setup.py`` file:

.. code-block:: python

    from setuptools import setup

    setup(name="ksconf-fancy-plugin",
          version="0.5.0",
          install_requires=[
              "ksconf>=0.13.0",
              "some-fancy-library",   # Add 3rd party libraries here, if needed
          ],
          entry_points={"ksconf_plugin": ["fancy-plugin = ksconf.plugins.fancy_plugin"]},
          packages=["ksconf.plugins"],
          description="Adds general fanciness within Ksconf",
          classifiers=["Environment :: Plugins"],
          author="Your name",
          author_email="your@name.example",
          url="Repo",
          zip_safe=False)


Then simply build and install your package.

..  code-block:: sh

    pip install .


If you need to remove it, you can always run:

..  code-block:: sh

    pip uninstall ksconf-fancy-plugin

All python package building and general development best practices apply, but this should be enough to get you started.


..  include:: common
