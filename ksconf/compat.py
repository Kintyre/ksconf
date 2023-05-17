"""
Silly simple Python version compatibility items
"""

import sys

# Since 'list' in Python 3.7 doesn't support __class_getitem__ (See PEP 560)
# We could just always import from typing, but that appears to cause some issues
# with type hinting, and this appears to work correctly.  Most of this appears
# to have changed in Python 3.8 and 3.9 (differs by type. hence the test-and-see approach)

''' # Alternate, needs more testing; not sure about the assignment part
# Another option would be to just assign directly into the typing module, what could go wrong?

from typing import Dict, List, Set, Tuple
for t in ("dict", "list", "set", "tuple"):
    try:
        T = t.capitalize()
        eval(f"{t}[str]")
        globals()[T] = globals[t]
    except TypeError:
        pass
'''

if sys.version_info < (3, 9):
    from typing import Dict, List, Set, Tuple
else:
    Dict = dict
    List = list
    Set = set
    Tuple = tuple


try:
    # Python 3.9 and later
    from functools import cache
except ImportError:
    from functools import lru_cache
    cache = lru_cache(maxsize=None)


def handle_py3_kw_only_args(kw, *default_args):
    """ Fake support for Python 3.8+ style keyword-only style arguments, or ``*`` arg syntax.

    Example Python 3.8+ syntax:

    ..  code-block:: py

        def f(arg, *args, a=True, b=False):
            ...

    Example Python 3.7 (and earlier) syntax with this helper function:

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


del sys

__all__ = [
    "Dict",
    "List",
    "Set",
    "Tuple",
    "cache",
    "handle_py3_kw_only_args",
]
