from __future__ import absolute_import
from __future__ import unicode_literals

import os
import shutil
import sys
from copy import deepcopy

import ksconf.ext.six as six
from ksconf.commands import ConfFileProxy
from ksconf.conf.delta import compare_cfgs, show_diff
from ksconf.conf.parser import GLOBAL_STANZA, _extract_comments, inject_section_comments, \
    parse_conf, write_conf
from ksconf.consts import SMART_UPDATE
from ksconf.util.file import relwalk

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
    # type: (str, ConfFileProxy, bool, str, bool) -> dict
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
        show_diff(sys.stdout, compare_cfgs(dest_cfg, merged_cfg),
                  headers=(dest.name, dest.name + "-new"))
        return SMART_UPDATE
    return dest.dump(merged_cfg)


def merge_update_conf_file(dest, sources, remove_source=False):
    # args: (str, list(str), bool
    """ Dest is treated as both the output, and the highest priority source.
    """
    # XXX:  If dest is missing/empty, and only one non-empty source, use file move
    # XXX:  If dest is present and no sources are present/non-empty, no-op
    remove = []
    confs = []
    if os.path.isfile(dest):
        confs.append(parse_conf(dest))
    for source in sources:
        if os.path.isfile(source):
            confs.append(parse_conf(source))
            remove.append(source)
    if confs:
        # Put in correct order.  (Last read has highest priority)
        confs.reverse()
        write_conf(dest, merge_conf_dicts(*confs))

    if remove_source:
        for name in remove:
            os.unlink(name)


def merge_update_any_file(dest, sources, remove_source=False):
    # XXX: Set this up in a shared function somewhere, we have to figure this out multiple places
    remove = []
    if dest.endswith(".conf") or dest.endswith(".meta"):
        #self.output.write("Merge   {} -> {}\n".format(local, default))
        merge_update_conf_file(dest, sources, remove_source=remove_source)
        # merge_conf(default, local)
    else:
        sources = [s for s in sources if os.path.isfile(s)]
        if os.path.isfile(dest):
            # Keep dest file, cleanup sources if requested
            remove.extend(sources)
        else:
            if sources:
                # The highest priority (first one on the list) always wins
                source = sources.pop(0)
                if remove_source:
                    shutil.move(source, dest)
                    remove.extend(sources)
                else:
                    shutil.copy(source, dest)
    if remove_source:
        for name in remove:
            os.unlink(name)


def merge_app_local(app_folder, cleanup=True):
    """
    Find everything in local, if it has a corresponding file in default, merge.
    This function assumes standard Splunk app path names.
    """
    local_dir = os.path.join(app_folder, "local")
    default_dir = os.path.join(app_folder, "default")
    local_meta = os.path.join(app_folder, "metadata", "local.meta")
    default_meta = os.path.join(app_folder, "metadata", "default.meta")

    # Handle 'local/', recursively, if present  (assume that symlinks have already been handled)
    if os.path.isdir(local_dir):
        for (root, dirs, files) in relwalk(local_dir):
            default_d = os.path.join(default_dir, root)
            if not os.path.isdir(default_d):
                os.mkdir(default_d)
            for file in files:
                local_file = os.path.join(local_dir, root, file)
                default_file = os.path.join(default_dir, root, file)
                merge_update_any_file(default_file, [local_file], cleanup)

    # Handle metadata, if present
    merge_update_conf_file(default_meta, [local_meta], cleanup)
