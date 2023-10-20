from __future__ import absolute_import, unicode_literals

import fnmatch
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Callable, Dict, Optional, Sequence, Type, Union

from ksconf.conf.parser import GLOBAL_STANZA
from ksconf.util.file import splglob_to_regex

# Note on future direction:
#
# It seems like each item on the list should be capable of having it's own type and flags (which
# could be inherited, at may not be known at the time the rules are first initialized).
#
# There should still be a phase that each "Rule" goes though to (1) set core attributes, (2) prep
# things that can be compiled, syntax checked, and any default flags should be available by this
# time, and (3) evaluate against a specific values for true/false.  This would allow things like a
# special prefix to lazy-switch modes (for example: ~regex~, or only do fnmatching if there's a
# wildcard otherwise stick with simple string matching, for efficiency...)


class FilteredList:
    IGNORECASE = 1
    INVERT = 2
    VERBOSE = 4

    def __init__(self, flags: int = 0, default: bool = True):
        self.data = []
        self.rules = None
        self.counter: Counter = Counter()
        self.flags: int = flags
        self._prep = True
        #  If no patterns defined, return default.  (True => match everything)
        self.default = default

    def _feed_from_file(self, path: Union[str, Path]):
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

    def feed(self, item: str, filter: Optional[Callable[[str], str]] = None):
        """
        Fee a new rule into the
        Use :py:obj:`filter` to enable calling a transformation function on :py:obj:`item` at
        the last minute.
        This allows item to contain ``file://...`` entries to include a list from the filesystem and
        yet still manipulate item is some pre-defined way.
        """
        if isinstance(item, Path):
            item = os.fspath(item)

        if item.startswith("file://"):
            # File ingestion mode
            filename = item[7:]
            # Technically we allow 'file://' inside a file.   No recursion depth limits in place.  (Stack overflow)
            '''
            for item in self._feed_from_file(filename):
                self.feed(item, filter)
            '''
            self.feedall(self._feed_from_file(filename), filter)
        else:
            if filter:
                item = filter(item)
            self.data.append(item)
        # New items added.  Mark prep-work as incomplete
        self._prep = False

    def feedall(self, iterable: Sequence[str], filter: Optional[Callable[[str], str]] = None):
        if iterable:
            for i in iterable:
                self.feed(i, filter)
        return self

    def prep(self):
        """
        Prepare for matching activities.

        Called automatically by :py:meth:`match`, but it could helpful to call directly to ensure
        there are no user input errors (which is accomplished by calling :py:meth:`_pre_match`).
        """
        # Kick off any first-time preparatory activities
        if self._prep is False:
            self._pre_match()
            self.counter = self.init_counter()
            self._prep = True

    def _pre_match(self):  # pragma: no cover
        pass

    def match(self, item: str) -> bool:
        """ See if given item matches any of the given patterns.  If no patterns were provided,
        :py:obj:default: will be returned.
        """
        if self.data:
            self.prep()
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

    def match_path(self, path) -> bool:
        """ Same as :py:meth:`match` except with special handling of path normalization.
        Patterns must be given with unix-style paths.
        """
        if isinstance(path, Path):
            path = os.fspath(path)
        if os.path.sep != "/":
            path = path.replace(os.path.sep, "/")
        return self.match(path)

    def match_stanza(self, stanza) -> bool:
        """ Same as :py:meth:`match`, but handle GLOBAL_STANZA gracefully. """
        if stanza is GLOBAL_STANZA:
            stanza = "default"
        return self.match(stanza)

    def init_counter(self) -> Counter:
        return Counter({n: 0 for n in self.data})

    @property
    def has_rules(self) -> bool:
        return bool(self.data)

    def _match(self, item) -> Union[str, bool]:
        """ Return name of rule, indicating a match or not. """
        raise NotImplementedError  # pragma: no cover


class FilteredListString(FilteredList):
    """ Handle simple string comparisons """

    def _pre_match(self):
        if self.flags & self.IGNORECASE:
            # Lower-case all strings in self.data.  (Only need to do this once)
            self.rules = {i.lower() for i in self.data}
        else:
            self.rules = set(self.data)
        return self.rules

    def _match(self, item: str) -> Union[str, bool]:
        if self.flags & self.IGNORECASE:
            item = item.lower()
        if item in self.rules:
            return item
        else:
            return False

    def init_counter(self) -> Counter:
        # Set all the counters to 0, so the caller can know which filters had 0 hits
        return Counter({n: 0 for n in self.rules})


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

    def _match(self, item: str) -> Union[str, bool]:
        for name, pattern_re in self.rules:
            if pattern_re.match(item):
                return name
        return False

    def init_counter(self) -> Counter:
        return Counter({n: 0 for n in self.data})


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


class_mapping: Dict[str, Type[FilteredList]] = {
    "string": FilteredListString,
    "wildcard": FilteredListWildcard,
    "regex": FilteredListRegex,
    "splunk": FilteredListSplunkGlob,
}


def create_filtered_list(match_mode: str, flags: int = 0, default=True) -> FilteredList:
    try:
        class_ = class_mapping[match_mode]
    except KeyError:  # pragma: no cover
        raise NotImplementedError(f"Matching mode {match_mode!r} undefined")
    return class_(flags, default)
