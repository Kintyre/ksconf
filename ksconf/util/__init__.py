from __future__ import unicode_literals

import sys

from ksconf.ext.six import PY2, binary_type

from ksconf.consts import KSCONF_DEBUG


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


try:
    # Available in Python 3.2 and later.
    from functools import lru_cache

    # the LRU functionality is not really needed
    memoize = lru_cache(maxsize=None)
except ImportError:
    # Modified from http://book.pythontips.com/en/latest/function_caching.html
    from functools import wraps

    def memoize(function):
        memo = {}

        @wraps(function)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            if key in memo:
                return memo[key]
            else:
                rv = function(*args, **kwargs)
                memo[key] = rv
                return rv
        return wrapper


def debug_traceback():  # pragma: no cover
    """ If the 'KSCONF_DEBUG' environmental variable is set, then show a stack trace. """
    level = 10
    from os import environ
    if KSCONF_DEBUG in environ:
        # TODO:  Pop one off the top of the stack to hide THIS function
        import traceback
        if PY2:
            exc_str = traceback.format_exc(level)
            if isinstance(exc_str, binary_type):
                exc_str = exc_str.decode('utf-8')
            sys.stderr.write(exc_str)
        else:
            traceback.print_exc(level)


def handle_py3_kw_only_args(kw, *default_args):
    """ Python 2.7 workaround for Python 3 style kw arg after '*' arg.

    Example Python 3 syntax:

    ..  code-block:: py

        def f(arg, *args, a=True, b=False):
            ...

    Example Python 2 syntax with this helper function:

    ..  code-block:: py

        def f(arg, *args, **kw_only):
            a, b = handle_py3_kw_only_args(kw_only, ("a", True), ("b", False))
            ...

    :param dict kw: keyword arguments provided to the calling function. Be aware
                    that this dict will be empty after this function is done.
    :param tuple default_args: pairs of keyword argument to the caller function
                               in argument (arg_name, default_value) order.
    :raises TypeError: if ``kw`` contains any keys not defined in ``args``
                       This mirrors Python's native behavior when an unexpected
                       argument is passed to a function.
    """
    out = []
    for arg_name, arg_default in default_args:
        try:
            out.append(kw.pop(arg_name))
        except KeyError:
            out.append(arg_default)
    if kw:
        import inspect
        caller = inspect.currentframe().f_back.f_code.co_name
        # Should all unexpected args be reported?  feels like this good enough
        raise TypeError("{} got an unexpected keyword argument '{}'"
                        .format(caller, list(kw)[0]))
    return out
