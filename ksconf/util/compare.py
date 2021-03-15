from __future__ import unicode_literals


def fileobj_compare(f1, f2):
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


def file_compare(fn1, fn2):
    with open(fn1, "rb") as f1, \
            open(fn2, "rb") as f2:
        return fileobj_compare(f1, f2)


def cmp_sets(a, b):
    """ Result tuples in format (a-only, common, b-only) """
    set_a = set(a)
    set_b = set(b)
    a_only = sorted(set_a.difference(set_b))
    common = sorted(set_a.intersection(set_b))
    b_only = sorted(set_b.difference(set_a))
    return (a_only, common, b_only)


# For backwards compability
_cmp_sets = cmp_sets
