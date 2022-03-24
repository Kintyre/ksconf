from __future__ import absolute_import, unicode_literals

import fnmatch
import os
import re
import sys
from collections import Counter

from ksconf.conf.parser import GLOBAL_STANZA
from ksconf.util.file import splglob_to_regex

# It seems like each item on the list should be capability of having it's own type and flags (which could be inherited, at may not be known at the time the rules are first initialized)
# The should still be some phase that each "Rule" goes though (1) creation to set core attributes, (2) prep where things can be compiled, syntax checked, and any default flags should be available by this time, and (3) evalute against a specific value for true/false.
# This would allow things like a special prefix to lazy-switch modes (for example:  ~regex~, or only do fnmatching if there's a wildcard otherwise stick with simple string matching, ...)


class FilteredList:
    IGNORECASE = 1
    INVERT = 2
    VERBOSE = 4

    def __init__(self, flags=0, default=True):
        self.data = []
        self.rules = None
        self.counter = Counter()
        self.flags = flags
        self._prep = True
        #  If no patterns defined, return default.  (True => match everything)
        self.default = default

    def _feed_from_file(self, path):
        items = []
        with open(path) as f:
            for line in f:
                line = line.rstrip()
                # Skip empty or "comment" lines
                if line and line[0] != "#":
                    items.append(line)
        if self.flags & self.VERBOSE:
            sys.stderr.write(f"Loaded {len(items)} patterns from {path}\n")
        return items

    def feed(self, item, filter=None):
        if item.startswith("file://"):
            # File ingestion mode
            filename = item[7:]
            for item in self._feed_from_file(filename):
                self.feed(item, filter)
        else:
            if filter:
                item = filter(item)
            self.data.append(item)
        # New items added.  Mark prep-work as incomplete
        self._prep = False

    def feedall(self, iterable, filter=None):
        if iterable:
            for i in iterable:
                self.feed(i, filter)
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

            ret = self._match(item)
            if ret:
                self.counter[ret] += 1
                result = True
            else:
                result = False

        else:
            #  No patterns defined, use default
            return self.default
        if self.flags & self.INVERT:
            return not result
        else:
            return result

    def match_path(self, path):
        if os.path.sep != "/":
            path = path.replace(os.path.sep, "/")
        return self.match(path)

    def match_stanza(self, stanza):
        """ Same as match(), but handle GLOBAL_STANZA gracefully. """
        if stanza is GLOBAL_STANZA:
            stanza = "default"
        return self.match(stanza)

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
                return name
        return False

    def reset_counters(self):
        self.counter = Counter()
        self.counter.update({i[0]: 0 for i in self.rules})


class FilteredListWildcard(FilteredListRegex):
    """ Wildcard support (handling '*' and ?')
    Technically fnmatch also supports [] and [!] character ranges, but we don't advertise that
    """

    def _pre_match(self):
        # Use fnmatch to translate wildcard expression to a regex, and compile regex
        re_flags = self.calc_regex_flags()
        self.rules = [(wc, re.compile(fnmatch.translate(wc), re_flags)) for wc in self.data]


class FilteredListSplunkGlob(FilteredListRegex):
    """ Classic wildcard support ('*' and ?') plus '...' or '**' for multiple-path components with
    some (non-advertised) pass-through regex behavior
    """

    def _pre_match(self):
        # Use splglob_to_regex to translate wildcard expression to a regex, and compile regex
        re_flags = self.calc_regex_flags()
        self.rules = [(wc, splglob_to_regex(wc, re_flags)) for wc in self.data]


class_mapping = {
    "string": FilteredListString,
    "wildcard": FilteredListWildcard,
    "regex": FilteredListRegex,
    "splunk": FilteredListSplunkGlob,
}


def create_filtered_list(match_mode, flags=0, default=True):
    try:
        class_ = class_mapping[match_mode]
    except KeyError:
        raise NotImplementedError(f"Matching mode {match_mode!r} undefined")
    return class_(flags, default)
