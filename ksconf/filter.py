from __future__ import absolute_import
from __future__ import unicode_literals

import fnmatch
import re
import sys

from ksconf.conf.parser import GLOBAL_STANZA


class FilteredList(object):
    IGNORECASE = I = 1
    BLACKLIST = B = 2
    VERBOSE = V = 4

    def __init__(self, flags=0):
        self.data = []
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
                self._prep = True

            # Q:  Is this the best way to handle global entries?
            if item is GLOBAL_STANZA:
                item = "default"

            result = self._match(item)
        else:
            #  No patterns defined.  No filter rule(s) => allow all through
            return True
        if self.flags & self.BLACKLIST:
            return not result
        else:
            return result

    @property
    def has_rules(self):
        return len(self.data) > 0

    def _match(self, item):  # pragma: no cover
        raise NotImplementedError


class FilteredListString(FilteredList):
    """ Handle simple string comparisons """

    def _pre_match(self):
        if self.flags & self.IGNORECASE:
            # Lower-case all strings in self.data.  (Only need to do this once)
            self.data = {i.lower() for i in self.data}

    def _match(self, item):
        if self.flags & self.IGNORECASE:
            item = item.lower()
        return item in self.data


class FilteredListRegex(FilteredList):
    """ Regular Expression support """
    def _pre_match(self):
        re_flags = 0
        if self.flags & self.IGNORECASE:
            re_flags |= re.IGNORECASE
        # Compile all regular expressions
        # XXX: Add better error handling here for friendlier user feedback
        self.data = [re.compile(pattern, re_flags) for pattern in self.data]

    def _match(self, item):
        for pattern_re in self.data:
            if pattern_re.match(item):
                return True
        return False


class FilterListWildcard(FilteredListRegex):
    """ Wildcard support (handling '*' and ?')
    Technically fnmatch also supports [] and [!] character ranges, but we don't advertise that
    """

    def _pre_match(self):
        # Use fnmatch to translate wildcard expression to a regex
        self.data = [fnmatch.translate(pat) for pat in self.data]
        # Now call regex (parent version)
        super(FilterListWildcard, self)._pre_match()


def create_filtered_list(match_mode, flags):
    if match_mode == "string":
        return FilteredListString(flags)
    elif match_mode == "wildcard":
        return FilterListWildcard(flags)
    elif match_mode == "regex":
        return FilteredListRegex(flags)
    else:
        raise NotImplementedError("Matching mode {!r} undefined".format(match_mode))
