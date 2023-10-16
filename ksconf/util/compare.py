from __future__ import unicode_literals

from typing import IO, List, Set, Tuple, TypeVar

from ksconf.types import PathType


def fileobj_compare(f1: IO, f2: IO) -> bool:
    # Borrowed from filecmp
    f1.seek(0)
    f2.seek(0)
    buffsize = 8192
    while True:
        b1 = f1.read(buffsize)
        b2 = f2.read(buffsize)
        if b1 != b2:
            return False
        if not b1:
            return True


def file_compare(fn1: PathType, fn2: PathType) -> bool:
    with open(fn1, "rb") as f1, \
            open(fn2, "rb") as f2:
        return fileobj_compare(f1, f2)


T = TypeVar("T")


def cmp_sets(a: Set[T], b: Set[T]) -> Tuple[List[T], List[T], List[T]]:
    """ Result tuples in format (a-only, common, b-only) """
    set_a = set(a)
    set_b = set(b)
    a_only = sorted(set_a.difference(set_b))
    common = sorted(set_a.intersection(set_b))
    b_only = sorted(set_b.difference(set_a))
    return (a_only, common, b_only)


# For backwards compatibility
_cmp_sets = cmp_sets
