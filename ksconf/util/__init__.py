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
