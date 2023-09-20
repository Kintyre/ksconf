from __future__ import unicode_literals

from functools import partial, wraps
from typing import Callable

from ksconf.consts import is_debug


def _xargs(iterable, cmd_len=1024):
    fn_len = 0
    buf = []
    iterable = list(iterable)
    while iterable:
        s = iterable.pop(0)
        l = len(s) + 1
        if fn_len + l >= cmd_len:
            yield buf
            buf = []
            fn_len = 0
        buf.append(s)
        fn_len += l
    if buf:
        yield buf


def decorator_with_opt_kwargs(decorator: Callable) -> Callable:
    """
    Make a decorator that can work with or without args.
    Heavily borrowed from:  https://gist.github.com/ramonrosa/402af55633e9b6c273882ac074760426
    Thanks to GitHub user ramonrosa
    """
    @wraps(decorator)
    def decorator_wrapper(*args, **kwargs):
        if len(kwargs) == 0 and len(args) == 1 and callable(args[0]):
            return decorator(args[0])
        if len(args) == 0:
            return partial(decorator, **kwargs)
        raise TypeError(f"{decorator.__name__} expects either a single Callable "
                        "or keyword arguments")
    return decorator_wrapper


def debug_traceback():  # pragma: no cover
    """ If the 'KSCONF_DEBUG' environmental variable is set, then show a stack trace. """
    level = 10
    if is_debug():
        # TODO:  Pop one off the top of the stack to hide THIS function
        import traceback
        traceback.print_exc(level)
