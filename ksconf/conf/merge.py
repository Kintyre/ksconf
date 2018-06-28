from __future__ import absolute_import
from __future__ import unicode_literals

import os
import sys
from copy import deepcopy

import six

from ksconf.conf.delta import compare_cfgs, show_diff
from ksconf.conf.parser import GLOBAL_STANZA, _extract_comments, inject_section_comments
from ksconf.consts import SMART_UPDATE

####################################################################################################
## Merging logic

# TODO: Replace this with "<<DROP_STANZA>>" on ANY key.  Let's use just ONE mechanism for all of
# these merge hints/customizations
STANZA_MAGIC_KEY = "_stanza"
STANZA_OP_DROP = "<<DROP>>"


def _merge_conf_dicts(base, new_layer):
    """ Merge new_layer on top of base.  It's up to the caller to deal with any necessary object
    copying to avoid odd referencing between the base and new_layer"""
    for (section, items) in six.iteritems(new_layer):
        if STANZA_MAGIC_KEY in items:
            magic_op = items[STANZA_MAGIC_KEY]
            if STANZA_OP_DROP in magic_op:
                # If this section exist in a parent (base), then drop it now
                if section in base:
                    del base[section]
                continue  # pragma: no cover  (peephole optimization)
        if section in base:
            # TODO:  Support other magic here...
            # Rip all the comments out of the new_layer, and prepend them (sequentially) to base
            comments = _extract_comments(items)
            if comments:
                inject_section_comments(base[section], prepend=comments)
            base[section].update(items)
        else:
            # TODO:  Support other magic here too..., though with no parent info
            base[section] = items
    # Nothing to return, base is updated in-place


def merge_conf_dicts(*dicts):
    result = {}
    for d in dicts:
        d = deepcopy(d)
        if not result:
            result = d
        else:
            # Merge each subsequent layer on one at a time
            _merge_conf_dicts(result, d)
    return result


def merge_conf_files(dest, configs, dry_run=False, banner_comment=None):
    # Parse all config files
    cfgs = [conf.data for conf in configs]
    # Merge all config files:
    merged_cfg = merge_conf_dicts(*cfgs)
    if banner_comment:
        if not banner_comment.startswith("#"):
            banner_comment = "#" + banner_comment
        inject_section_comments(merged_cfg.setdefault(GLOBAL_STANZA, {}), prepend=[banner_comment])

    # Either show the diff (dry-run mode) or write to the destination file
    if dry_run and dest.is_file():
        if os.path.isfile(dest.name):
            dest_cfg = dest.data
        else:
            dest_cfg = {}
        show_diff(sys.stdout, compare_cfgs(merged_cfg, dest_cfg),
                  headers=(dest.name, dest.name + "-new"))
        return SMART_UPDATE
    return dest.dump(merged_cfg)
