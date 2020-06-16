from __future__ import absolute_import
from __future__ import unicode_literals

import fnmatch
import re
import sys

from collections import Counter

from ksconf.conf.parser import GLOBAL_STANZA


class FilteredList(object):
    IGNORECASE = 1
    INVERT = 2
    VERBOSE = 4

    def __init__(self, flags=0):
        self.data = []
        self.rules = None
        self.counter = Counter()
        self.flags = flags
        self._prep = True

    def _feed_from_file(self, path):
        items = []
        with open(path) as f:
            for line in f:
                line = line.rstrip()
                # Skip empty or "comment" lines
                if line and line[0] != "#":
                    items.append(line)
        if self.flags & self.VERBOSE:
            sys.stderr.write("Loaded {} patterns from {}\n".format(len(items), path))
        return items

    def feed(self, item):
        if item.startswith("file://"):
            # File ingestion mode
            filename = item[7:]
            self.data.extend(self._feed_from_file(filename))
        else:
            self.data.append(item)
        # New items added.  Mark prep-work as incomplete
        self._prep = False

    def feedall(self, iterable):
        if iterable:
            for i in iterable:
                self.feed(i)
        return self

    def _pre_match(self):  # pragma: no cover
        pass

    def match(self, item):
        if self.data:
            # Kick off any first-time preparatory activities
            if self._prep is False:
                self._pre_match()
                self.reset_counters()
                self._prep = True

            # Q:  Is this the best way to handle global entries?
            if item is GLOBAL_STANZA:
                item = "default"

            ret = self._match(item)
            if ret:
                self.counter[ret] += 1
                result = True
            else:
                result = False

        else:
            #  No patterns defined.  No filter rule(s) => allow all through
            return True
        if self.flags & self.INVERT:
            return not result
        else:
            return result

    def reset_counters(self):
        # Set all the counters to 0, so the caller can know which filters had 0 hits
        self.counter = Counter()
        self.counter.update((n, 0) for n in self.data)

    @property
    def has_rules(self):
        return bool(self.data)

    def _match(self, item):  # pragma: no cover
        """ Return name of rule, indicating a match or not. """
        raise NotImplementedError


class FilteredListString(FilteredList):
    """ Handle simple string comparisons """

    def _pre_match(self):
        if self.flags & self.IGNORECASE:
            # Lower-case all strings in self.data.  (Only need to do this once)
            self.rules = {i.lower() for i in self.data}
        else:
            self.rules = set(self.data)
        return self.rules

    def _match(self, item):
        if self.flags & self.IGNORECASE:
            item = item.lower()
        if item in self.rules:
            return item
        else:
            return False

    def reset_counters(self):
        self.counter = Counter()
        self.counter.update({n: 0 for n in self.rules})


class FilteredListRegex(FilteredList):
    """ Regular Expression support """

    def calc_regex_flags(self):
        re_flags = 0
        if self.flags & self.IGNORECASE:
            re_flags |= re.IGNORECASE
        return re_flags

    def _pre_match(self):
        # Compile all regular expressions
        re_flags = self.calc_regex_flags()
        # XXX: Add better error handling here for friendlier user feedback
        self.rules = [(pattern, re.compile(pattern, re_flags)) for pattern in self.data]

    def _match(self, item):
        for name, pattern_re in self.rules:
            if pattern_re.match(item):
                #self.counter[name] += 1
                return name
        return False

    def reset_counters(self):
        self.counter = Counter()
        self.counter.update({i[0]: 0 for i in self.rules})


class FilterListWildcard(FilteredListRegex):
    """ Wildcard support (handling '*' and ?')
    Technically fnmatch also supports [] and [!] character ranges, but we don't advertise that
    """

    def _pre_match(self):
        # Use fnmatch to translate wildcard expression to a regex, and compile regex
        re_flags = self.calc_regex_flags()
        self.rules = [(wc, re.compile(fnmatch.translate(wc), re_flags)) for wc in self.data]


def create_filtered_list(match_mode, flags=0):
    if match_mode == "string":
        return FilteredListString(flags)
    elif match_mode == "wildcard":
        return FilterListWildcard(flags)
    elif match_mode == "regex":
        return FilteredListRegex(flags)
    else:
        raise NotImplementedError("Matching mode {!r} undefined".format(match_mode))
