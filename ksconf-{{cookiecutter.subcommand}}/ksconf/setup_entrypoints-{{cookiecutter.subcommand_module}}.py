
_entry_points = {
    "ksconf_cmd" : [
############################################################################################
# ADD THIS LINE to setup_entrypoint.py:
        Ep("{{cookiecutter.subcommand}}",   "ksconf.commands.{{cookiecutter.subcommand_module}}",  "{{cookiecutter.subcommand_class}}"),
############################################################################################

    ],
}
