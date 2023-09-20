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

del sys

__all__ = [
    "Dict",
    "List",
    "Set",
    "Tuple",
    "cache",
]
