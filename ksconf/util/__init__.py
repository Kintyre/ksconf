from __future__ import unicode_literals

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


def debug_traceback():  # pragma: no cover
    """ If the 'KSCONF_DEBUG' environmental variable is set, then show a stack trace. """
    level = 10
    from os import environ
    if KSCONF_DEBUG in environ:
        # TODO:  Pop one off the top of the stack to hide THIS function
        import traceback
        traceback.print_exc(level)
