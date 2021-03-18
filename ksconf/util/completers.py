from __future__ import absolute_import, unicode_literals

# Optional argcomplete library for CLI (BASH-based) tab completion
try:
    from argcomplete import autocomplete
    from argcomplete.completers import DirectoriesCompleter, FilesCompleter
except ImportError:

    def _argcomplete_noop(*args, **kwargs):
        del args, kwargs

    autocomplete = _argcomplete_noop
    # noinspection PyPep8Naming
    FilesCompleter = DirectoriesCompleter = _argcomplete_noop

# Someday add *.meta (once more testing is done with those files
conf_files_completer = FilesCompleter(allowednames=["*.conf"])
