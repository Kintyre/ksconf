from __future__ import unicode_literals

SMART_CREATE = "created"
SMART_UPDATE = "updated"
SMART_NOCHANGE = "unchanged"

# EXIT_CODE_* constants:  Use consistent exit codes for scriptability
#
#   0-9    Normal/successful conditions
#   20-49  Error conditions (user caused)
#   50-59  Externally caused (should retry)
#   100+   Internal error (developer required)
#   120+   Environmental error

EXIT_CODE_SUCCESS = 0
EXIT_CODE_NOTHING_TO_DO = 1
EXIT_CODE_USER_QUIT = 2
EXIT_CODE_NO_SUCH_FILE = 5
EXIT_CODE_MISSING_ARG = 6
EXIT_CODE_BAD_ARGS = 7

EXIT_CODE_DIFF_EQUAL = 0
EXIT_CODE_DIFF_CHANGE = 3
EXIT_CODE_DIFF_NO_COMMON = 4
EXIT_CODE_FORMAT_APPLIED = 8
EXIT_CODE_SORT_APPLIED = 9

# Errors caused by users
EXIT_CODE_BAD_CONF_FILE = 20
EXIT_CODE_FAILED_SAFETY_CHECK = 22
EXIT_CODE_COMBINE_MARKER_MISSING = 30

# Errors caused by GIT interactions
EXIT_CODE_GIT_FAILURE = 40

# Retry or temporary failure
EXIT_CODE_EXTERNAL_FILE_EDIT = 50

# Unresolvable issues (developer required)
EXIT_CODE_INTERNAL_ERROR = 100
EXIT_CODE_FEAT_NOT_IMPLEMENTED = 101     # Too bad we can't use 404 :=)

# Environmental error
EXIT_CODE_ENV_BUSTED = 120


# This gets properly supported in Python 3.6, but until then....
import re
RegexType = type(re.compile(r'.'))
del re

# Environmental vars are treated as bytes in PY2, and unicode in PY3.  (This wouldn't be needed,
# except that we import unicode_literals, which we need for other constant strings.)  UGH!
# Oh the joys of supporting 2 + 3 at the same time!

# PY2 - Six may be missing when 'setup.py' is first called.  (Breaks pre-commit)
import sys
PY2 = sys.version_info[0] == 2
del sys

if PY2:
    KSCONF_DEBUG = b"KSCONF_DEBUG"
else:
    KSCONF_DEBUG = "KSCONF_DEBUG"
del PY2
