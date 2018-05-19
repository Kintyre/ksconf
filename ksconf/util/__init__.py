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
