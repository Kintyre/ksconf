#!/usr/bin/python

import os
import sys

from glob import glob
from collections import defaultdict
from urllib import unquote

from ksconf.conf.parser import parse_conf
from ksconf.conf.merge import merge_conf_dicts as merge_conf



def get_app_conf(app_path, cfg_name, dirs=["default", "local"]):
    cfg_dict = {}
    for d in dirs:
        p = os.path.join(app_path, d, cfg_name + ".conf")
        if os.path.isfile(p):
            cfg = parse_conf(p)
            cfg_dict = merge_conf(cfg_dict, cfg)
    return cfg_dict



def check_references(metadata):
    app_dir = os.path.abspath(os.path.dirname(os.path.dirname(metadata.name)))
    print "Looking at metadata file for app %s" % app_dir
    db = collect_info(app_dir)

    show_app_inventory(db)

    md = parse_conf(metadata)
    for (meta_entry, meta_facts) in md.iteritems():
        cfg_path = [unquote(p) for p in meta_entry.split("/") ]
        #(cfg_file, stanza) = meta_entry.split("/",1)

        if len(cfg_path) == 1:
            print "Skipping global stanza"
            print meta_facts
            continue

        cfg_file = cfg_path[0]
        stanza = cfg_path[1]
        #print "Looking in %s for [%s]" % (cfg_file, stanza)

        assert len(cfg_path) <=3, "Too may components.  Aborting... %r" % (cfg_path)

        key = None
        if len(cfg_path) > 2:
            key = cfg_path[2]
        try:
            db[cfg_file][stanza]
            if key:
                db[cfg_file][stanza][key]
                print "Key match for    %s/%s [%s]" % (cfg_file, stanza, key)
            else:
                print "Stanza match for %s/%s" % (cfg_file, stanza)
        except KeyError:
            if key:
                print "Missing         %s/%s [%s]" % (cfg_file, stanza, key)

            else:
                print "Missing         %s/%s" % (cfg_file, stanza)




def collect_info_confs(app_dir, dir_, db):
    conf_files = glob(os.path.join(app_dir, dir_, "*.conf"))
    for cf in conf_files:
        cfg_name = os.path.splitext(os.path.basename(cf))[0]
        cfg_data = parse_conf(cf)
        print "Import %s (Found %d entries)" % (cf, len(cfg_data))
        db[cfg_name] = merge_conf(db[cfg_name], cfg_data)


def collect_info_lookups(app_dir, db, read_files=True):
    obj_type = "lookups"
    data = {}
    pattern = os.path.join(os.path.join(app_dir, "lookups", "*.csv"))
    print "Looking for %s based on files matching %s" % (obj_type, pattern)
    for fn in glob(pattern):
        obj_name = os.path.basename(fn)
        if read_files:
            data[obj_name] = list(open(fn))
        else:
            data[obj_name] = "Present"
    db[obj_type].update(data)



def collect_info_data(app_dir, dir_, path_parts, db, obj_type=None, read_files=True):
    if not obj_type:
        obj_type = path_parts[-2]
    data = {}
    pattern = os.path.join(os.path.join(app_dir, dir_, "data", *path_parts))
    print "Looking for %s based on files matching %s" % (obj_type, pattern)
    for fn in glob(pattern):
        obj_name = os.path.splitext(os.path.basename(fn))[0]
        if read_files:
            data[obj_name] = open(fn).read()
        else:
            data[obj_name] = "Present"
    db[obj_type].update(data)


def collect_info(app_dir):
    db = defaultdict(dict)
    for path_type in ("default", "local"):
        collect_info_confs(app_dir, path_type, db)
        collect_info_data(app_dir, path_type, ("ui", "views", "*.xml"), db, "views")
        collect_info_data(app_dir, path_type, ("ui", "nav", "*.xml"), db, "nav")
        collect_info_data(app_dir, path_type, ("models", "*.json"), db, "datamodel")

    collect_info_lookups(app_dir, db)
    return db


def show_app_inventory(db):
    print "=" * 80
    for (obj_type, obj_data) in db.iteritems():
        print " --- %s ---"  % (obj_type,)
        for (stanza_name, stanza_data) in obj_data.iteritems():
            print "\t%s / %-50s \t\t(size=%d)" % (obj_type, stanza_name, len(stanza_data))
    print "=" * 80



if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("metadata", metavar="FILE", #nargs="+",
                        type=argparse.FileType('r'), default=[sys.stdin],
                        help="Input file to sort, or standard input.")
    args = parser.parse_args()
    check_references(args.metadata)
