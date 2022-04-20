from __future__ import unicode_literals

import re
import sys
from enum import Enum


class SmartEnum(Enum):
    CREATE = "created"
    UPDATE = "updated"
    NOCHANGE = "unchanged"

    def __str__(self):
        return self.value


# Legacy names
SMART_CREATE = SmartEnum.CREATE
SMART_UPDATE = SmartEnum.UPDATE
SMART_NOCHANGE = SmartEnum.NOCHANGE


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

EXIT_CODE_CLI_ARG_DEPRECATED = 10

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
EXIT_CODE_BAD_PY_VERSION = 121


# This gets properly supported in Python 3.6, but until then....
RegexType = type(re.compile(r'.'))


KSCONF_DEBUG = "KSCONF_DEBUG"


# Cleanup namespace for wildcard imports
del re, sys
