#!/usr/bin/env python

from __future__ import absolute_import, unicode_literals

import os
import sys
import unittest

from io import open

# Allow interactive execution from CLI,  cd tests; ./test_meta.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from ksconf.filter import (FilteredList, create_filtered_list,
                           FilteredListString, FilteredListRegex, FilterListWildcard)


class FilterTestCase(unittest.TestCase):

    sample01 = [
        "ftp:exchange",
        "ftp:transfer",
        "ftp:auth",
        "ftp:debug",
        "http:exchange",
        "http:auth",
    ]

    def test_helper_function(self):
        self.assertIsInstance(create_filtered_list("string"), FilteredListString)
        self.assertIsInstance(create_filtered_list("regex"), FilteredListRegex)
        self.assertIsInstance(create_filtered_list("wildcard"), FilterListWildcard)

    def filter(self, filter_type, filters, items, flags=0):
        fl = create_filtered_list(filter_type, flags)
        fl.feedall(filters)
        return (fl, [item for item in items if fl.match(item)])

    def test_string(self):
        fl, res = self.filter("string", ("ftp:auth", "http:auth"), self.sample01)
        self.assertEqual(res, ["ftp:auth", "http:auth"])

    def test_string_blackslist(self):
        fl, res = self.filter("string", ("ftp:auth", "http:auth"), self.sample01,
                              flags=FilteredList.BLACKLIST)
        self.assertEqual(res, ["ftp:exchange", "ftp:transfer", "ftp:debug", "http:exchange"])

    def test_regex(self):
        fl, res = self.filter("regex", ("ftp:\w+",), self.sample01)
        self.assertEqual(res, ["ftp:exchange", "ftp:transfer", "ftp:auth", "ftp:debug"])

        fl, res = self.filter("regex", ("\w+:auth",), self.sample01)
        self.assertEqual(res, ["ftp:auth", "http:auth"])

    def test_wildcard(self):
        fl, res = self.filter("wildcard", ("http:*",), self.sample01)
        self.assertEqual(res, ["http:exchange", "http:auth"])

    def test_reload_and_counter_reset(self):
        sample = self.sample01
        fl, res = self.filter("wildcard", ("http:*",), sample)
        self.assertEqual(res, ["http:exchange", "http:auth"])
        self.assertEqual(fl.counter["http:*"], 2)
        # After running the filter once, add another filter rule and add more items.
        fl.feed("ftp:*")
        res2 = [item for item in sample if fl.match(item)]
        self.assertEqual(len(fl.rules), 2)
        self.assertEqual(res2, sample)
        # Note that 'http:*' is 2 again, and NOT 4.   Counters were reset after earlier match() call.
        self.assertEqual(fl.counter["http:*"], 2)
        self.assertEqual(fl.counter["ftp:*"], 4)

    def test_string_counter(self):
        fl, res = self.filter("string", ("http:auth", "ftp:auth", "ftp:bogus"), self.sample01)
        self.assertEqual(res, ["ftp:auth", "http:auth"])
        self.assertEqual(fl.counter["ftp:auth"], 1)
        self.assertEqual(fl.counter["http:auth"], 1)
        # Ensure that 0 matches still gets reported
        self.assertEqual(fl.counter["ftp:bogus"], 0)
        self.assertEqual(len(fl.counter), 3)

    def test_wildcard_counter(self):
        fl, res = self.filter("wildcard", ("http:*",), self.sample01)
        self.assertEqual(res, ["http:exchange", "http:auth"])
        self.assertEqual(fl.counter["http:*"], 2)
        self.assertEqual(len(fl.counter), 1)

        fl, res = self.filter("wildcard", ("*:auth", "*nomatch*"), self.sample01)
        self.assertEqual(res, ["ftp:auth", "http:auth"])
        self.assertEqual(fl.counter["*:auth"], 2)
        self.assertEqual(fl.counter["*nomatch*"], 0)
        self.assertEqual(len(fl.counter), 2)

    def test_string_blacklist_counter(self):
        # Note that blacklist (match inversion) doesn't change the counter numbers calculation.
        fl, res = self.filter("string", ("http:auth", "ftp:auth", "ftp:bogus"), self.sample01,
                              flags=FilteredList.BLACKLIST)
        self.assertEqual(res, ["ftp:exchange", "ftp:transfer", "ftp:debug", "http:exchange"])
        self.assertEqual(fl.counter["ftp:auth"], 1)
        self.assertEqual(fl.counter["http:auth"], 1)
        # Ensure that 0 matches still gets reported
        self.assertEqual(fl.counter["ftp:bogus"], 0)
        self.assertEqual(len(fl.counter), 3)

    def test_string_ignorecase_counter(self):
        # Note that blacklist (match inversion) doesn't change the counter numbers calculation.
        sample = list(self.sample01)
        sample[4] = sample[4].upper()
        fl, res = self.filter("string", ("http:AUTH", "fTp:AuTh"), self.sample01, flags=FilteredList.IGNORECASE)
        self.assertEqual(res, ["ftp:auth", "http:auth"])
        # Note that the counter values are now lower case too
        self.assertEqual(fl.counter["ftp:auth"], 1)
        self.assertEqual(fl.counter["http:auth"], 1)
        self.assertEqual(len(fl.counter), 2)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
