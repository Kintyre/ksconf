..  _ksconf_cmd_attr-set:


ksconf attr-set
================


.. argparse::
    :module: ksconf.cli
    :func: build_cli_parser
    :path: attr-set
    :nodefault:



Example
^^^^^^^


Update build during CI/CD

..  code-block:: sh

    ksconf attr-set build/default.app -s launcher -a version 1.1.2
    ksconf attr-set build/default.app -s launcher -a build --value-type env GITHUB_RUN_NUMBER

Rewrite a saved search to match the new cooperate initiative to relabel all "CRITICAL" messages as "WHOOPSIES".

..  code-block:: sh

    ksconf attr-get savedsearches.conf -s "Internal System Errors" -a search \
        | sed -re 's/CRITICAL/WHOOPSIES/g' \
        | ksconf attr-set savedsearches.conf -s "Internal System Errors" -a search --value-type file -



..  note::  What if you want to write multiple stanza/attributes at once?

    Of course it's possible to call ``ksconf attr-set`` multiple times, but that may be awkward or inefficient if many updates are needed.
    In the realm of shell scripting, another option is to use :ref:`ksconf_cmd_merge` which is designed to merge multiple stanzas, or even multiple files, at once.
    With a little bit of creatively, it's possible to add (or update) and entire new stanza in-line using a single command like so:

    ..  code-block:: sh

        printf '[drop_field(1)]\ndefinition=| fields - $field$\nargs=field\niseval=0\n' | ksconf merge --in-place --target macros.conf -

        # which is identical to:
        ksconf merge --in-place --target macros.conf <(printf '[drop_field(1)]\ndefinition=| fields - $field$\nargs=field\niseval=0\n')

    Of course, neither of these are super easy to read.  If your content is static, then an easy answer it to use a static conf file.
    However, at some point it may be easier to just edit these using Python where any arbitrary level of complexity is possible.

    Ksconf has some built in utility functions to make this kind of simple update-in-place workflow super simple.
    For example, the :py:class:`~ksconf.conf.parser.update_conf` context manager allows access to existing conf values and quick modification.
    If no modification is necessary, then the file is left untouched.

    ..  code-block:: py

            from ksconf.conf.parser import update_conf, conf_attr_boolean

            # Update app.conf for a build release
            with update_conf("app.conf") as conf:
                conf["launcher"]["version"] = "1.0.2"
                conf["install"]["build"] = "33"

            # Update sourcetype references in all saved searches; place marker in description
            with update_conf("savedsearches.conf") as conf:
                for report in conf:
                    if not conf_attr_boolean(conf[report].get("disabled", "0")):
                        # Update enabled search
                        search = conf[report].get("search", "")
                        conf[report]["search"] = search.replace("cisco:old-understood-tech", "cisco:new-fangled-tech")
                        conf[report]["description"] = f"We did an update.\n Old description: {conf[report].get('description', '')}"

    ..  Yes, we need an API intro for simple use cases like this.  For now, I guess this is it!?!
