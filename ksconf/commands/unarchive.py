import os
import re
import sys
from StringIO import StringIO
from subprocess import list2cmdline

from ksconf.archive import extract_archive, gaf_filter_name_like, sanity_checker, \
    gen_arch_file_remapper
from ksconf.conf.parser import parse_conf, PARSECONF_LOOSE, ConfParserException
from ksconf.consts import EXIT_CODE_FAILED_SAFETY_CHECK, EXIT_CODE_GIT_FAILURE
from ksconf.util.compare import _cmp_sets
from ksconf.util.file import file_hash, match_bwlist, dir_exists
from ksconf.vc.git import git_is_working_tree, git_ls_files, git_is_clean, git_status_ui, \
    git_cmd_iterable, git_cmd


def do_unarchive(args):
    """ Install / upgrade a Splunk app from an archive file """
    # Handle ignored files by preserving them as much as possible.
    # Add --dry-run mode?  j/k - that's what git is for!

    if not os.path.isfile(args.tarball):
        sys.stderr.write("No such file or directory {}\n".format(args.tarball))
        return EXIT_CODE_FAILED_SAFETY_CHECK

    if not os.path.isdir(args.dest):
        sys.stderr.write("Destination directory does not exist: {}\n".format(args.dest))
        return EXIT_CODE_FAILED_SAFETY_CHECK

    f_hash = file_hash(args.tarball)
    sys.stdout.write("Inspecting archive:               {}\n".format(args.tarball))

    new_app_name = args.app_name
    # ARCHIVE PRE-CHECKS:  Archive must contain only one app, no weird paths, ...
    app_name = set()
    app_conf = {}
    files = 0
    local_files = set()
    a = extract_archive(args.tarball, extract_filter=gaf_filter_name_like("app.conf"))
    for gaf in sanity_checker(a):
        gaf_app, gaf_relpath = gaf.path.split("/", 1)
        files += 1
        if gaf.path.endswith("app.conf") and gaf.payload:
            conffile = StringIO(gaf.payload)
            conffile.name = os.path.join(args.tarball, gaf.path)
            app_conf = parse_conf(conffile, profile=PARSECONF_LOOSE)
            del conffile
        elif gaf_relpath.startswith("local") or gaf_relpath.endswith("local.meta"):
            local_files.add(gaf_relpath)
        app_name.add(gaf.path.split("/", 1)[0])
        del gaf_app, gaf_relpath
    if len(app_name) > 1:
        sys.stderr.write("The 'unarchive' command only supports extracting a single splunk app at "
                         "a time.\nHowever the archive {} contains {} apps:  {}\n"
                         "".format(args.tarball, len(app_name), ", ".join(app_name)))
        return EXIT_CODE_FAILED_SAFETY_CHECK
    else:
        app_name = app_name.pop()
    del a
    if local_files:
        sys.stderr.write("Local {} files found in the archive.  ".format(len(local_files)))
        if args.allow_local:
            sys.stderr.write("Keeping these due to the '--allow-local' flag\n")
        else:
            sys.stderr.write("Excluding these files by default.  Use '--allow-local' to override.")

    if not new_app_name and True:  # if not --no-app-name-fixes
        if app_name.endswith("-master"):
            sys.stdout.write("Automatically dropping '-master' from the app name.  This is often "
                             "the result of a github export.\n")
            # Trick, but it works...
            new_app_name = app_name[:-7]
        mo = re.search(r"(.*)-\d+\.[\d.-]+$", app_name)
        if mo:
            sys.stdout.write("Automatically removing the version suffix from the app name.  '{}' "
                             "will be extracted as '{}'\n".format(app_name, mo.group(1)))
            new_app_name = mo.group(1)

    app_basename = new_app_name or app_name
    dest_app = os.path.join(args.dest, app_basename)
    sys.stdout.write("Inspecting destination folder:    {}\n".format(os.path.abspath(dest_app)))

    # FEEDBACK TO THE USER:   UPGRADE VS INSTALL, GIT?, APP RENAME, ...
    app_name_msg = app_name
    vc_msg = "without version control support"

    old_app_conf = {}
    if os.path.isdir(dest_app):
        mode = "upgrade"
        is_git = git_is_working_tree(dest_app)
        try:
            # Ignoring the 'local' entries since distributed apps should never modify local anyways
            old_app_conf_file = os.path.join(dest_app, args.default_dir or "default", "app.conf")
            old_app_conf = parse_conf(old_app_conf_file, profile=PARSECONF_LOOSE)
        except ConfParserException:
            sys.stderr.write("Unable to read app.conf from existing install.\n")
    else:
        mode = "install"
        is_git = git_is_working_tree(args.dest)
    if is_git:
        vc_msg = "with git support"
    if new_app_name and new_app_name != app_name:
        app_name_msg = "{} (renamed from {})".format(new_app_name, app_name)

    def show_pkg_info(conf, label):
        sys.stdout.write("{} packaging info:    '{}' by {} (version {})\n".format(
            label,
            conf.get("ui", {}).get("label", "Unknown"),
            conf.get("launcher", {}).get("author", "Unknown"),
            conf.get("launcher", {}).get("version", "Unknown")))

    if old_app_conf:
        show_pkg_info(old_app_conf, " Installed app")
    if app_conf:
        show_pkg_info(app_conf, "   Tarball app")

    sys.stdout.write("About to {} the {} app {}.\n".format(mode, app_name_msg, vc_msg))

    existing_files = set()
    if mode == "upgrade":
        if is_git:
            existing_files.update(git_ls_files(dest_app))
            if not existing_files:
                sys.stderr.write("App appears to be in a git repository but no files have been "
                                 "staged or committed.  Either commit or remove '{}' and try "
                                 "again.\n".format(dest_app))
                return EXIT_CODE_FAILED_SAFETY_CHECK
            if args.git_sanity_check == "off":
                sys.stdout.write("The 'git status' safety checks have been disabled via CLI"
                                 "argument.  Skipping.\n")
            else:
                d = {
                    #        untracked, ignored
                    "changed": (False, False),
                    "untracked": (True, False),
                    "ignored": (True, True)
                }
                is_clean = git_is_clean(dest_app, *d[args.git_sanity_check])
                del d
                if is_clean:
                    sys.stdout.write("Git folder is clean.   Okay to proceed with the upgrade.\n")
                else:
                    sys.stderr.write("Unable to move forward without a clean working directory.\n"
                                     "Clean up and try again.  Modifications are listed below.\n\n")
                    sys.stderr.flush()
                    if args.git_sanity_check == "changed":
                        git_status_ui(dest_app, "--untracked-files=no")
                    elif args.git_sanity_check == "ignored":
                        git_status_ui(dest_app, "--ignored")
                    else:
                        git_status_ui(dest_app)
                    return EXIT_CODE_FAILED_SAFETY_CHECK
        else:
            for (root, dirs, filenames) in os.walk(dest_app):
                for fn in filenames:
                    existing_files.add(os.path.join(root, fn))
        sys.stdout.write("Before upgrade.  App has {} files\n".format(len(existing_files)))
    elif is_git:
        sys.stdout.write("Git clean check skipped.  Not needed for a fresh app install.\n")

    def fixup_pattern_bw(patterns, prefix=None):
        modified = []
        for pattern in patterns:
            if pattern.startswith("./"):
                if prefix:
                    pattern = "{0}/{1}".format(prefix, pattern[2:])
                else:
                    pattern = pattern[2:]
                modified.append(pattern)
            # If a pattern like 'tags.conf' or '*.bak' is provided, assume basename match (any dir)
            elif "/" not in pattern:
                modified.append("(^|.../)" + pattern)
            else:
                modified.append(pattern)
        return modified

    # PREP ARCHIVE EXTRACTION
    installed_files = set()
    excludes = list(args.exclude)
    '''
    for pattern in args.exclude:
        # If a pattern like 'default.meta' or '*.bak' is provided, assume it's a basename match.
        if "/" not in pattern:
            excludes.append(".../" + pattern)
        else:
            excludes.append(pattern)
    '''
    if not args.allow_local:
        for pattern in local_files:
            excludes.append("./" + pattern)
    excludes = fixup_pattern_bw(excludes, app_basename)
    sys.stderr.write("Extraction exclude patterns:  {!r}\n".format(excludes))
    path_rewrites = []
    files_iter = extract_archive(args.tarball)
    if True:
        files_iter = sanity_checker(files_iter)
    if args.default_dir:
        rep = "/{}/".format(args.default_dir.strip("/"))
        path_rewrites.append(("/default/", rep))
        del rep
    if new_app_name:
        # We do have the "app_name" extracted from our first pass above, but
        regex = re.compile(r'^([^/]+)(?=/)')
        path_rewrites.append((regex, new_app_name))
    if path_rewrites:
        files_iter = gen_arch_file_remapper(files_iter, path_rewrites)

    sys.stdout.write("Extracting app now...\n")
    for gaf in files_iter:
        if match_bwlist(gaf.path, excludes, escape=False):
            print "Skipping [blacklist] {}".format(gaf.path)
            continue
        if not is_git or args.git_mode in ("nochange", "stage"):
            print "{0:60s} {2:o} {1:-6d}".format(gaf.path, gaf.size, gaf.mode)
        installed_files.add(gaf.path.split("/", 1)[1])
        full_path = os.path.join(args.dest, gaf.path)
        dir_exists(os.path.dirname(full_path))
        with open(full_path, "wb") as fp:
            fp.write(gaf.payload)
        os.chmod(full_path, gaf.mode)
        del fp, full_path

    files_new, files_upd, files_del = _cmp_sets(installed_files, existing_files)
    '''
    print "New: \n\t{}".format("\n\t".join(sorted(files_new)))
    print "Existing: \n\t{}".format("\n\t".join(sorted(files_upd)))
    print "Removed:  \n\t{}".format("\n\t".join(sorted(files_del)))
    '''

    sys.stdout.write("Extracted {} files:  {} new, {} existing, and {} removed\n".format(
        len(installed_files), len(files_new), len(files_upd), len(files_del)))

    # Filer out "removed" files; and let us keep some based on a keep-whitelist:  This should
    # include things like local, ".gitignore", ".gitattributes" and so on

    keep_list = [".git*"]
    keep_list.extend(args.keep)
    if not args.allow_local:
        keep_list += ["local/...", "local.meta"]
    keep_list = fixup_pattern_bw(keep_list)
    sys.stderr.write("Keep file patterns:  {!r}\n".format(keep_list))

    files_to_delete = []
    files_to_keep = []
    for fn in files_del:
        if match_bwlist(fn, keep_list, escape=False):
            # How to handle a keep of "default.d/..." when we DO want to cleanup the default
            # redirect folder of "default.d/10-upstream"?
            # Practially this probably isn't mucn of an issue since most apps will continue to send
            # an ever increasing list of default files (to mask out old/unused ones)
            sys.stdout.write("Keeping {}\n".format(fn))
            files_to_keep.append(fn)
        else:
            files_to_delete.append(fn)
    if files_to_keep:
        sys.stdout.write("Keeping {} of {} files marked for deletion due to whitelist.\n"
                         .format(len(files_to_keep), len(files_del)))
    git_rm_queue = []

    if files_to_delete:
        sys.stdout.write("Removing files that are no longer in the upgraded version of the app.\n")
    for fn in files_to_delete:
        path = os.path.join(dest_app, fn)
        if is_git and args.git_mode in ("stage", "commit"):
            print "git rm -f {}".format(path)
            git_rm_queue.append(fn)
        else:
            print "rm -f {}".format(path)
            os.unlink(path)

    if git_rm_queue:
        # Run 'git rm file1 file2 file3 ..." (using an xargs like mechanism)
        git_cmd_iterable(["rm"], git_rm_queue, cwd=dest_app)
    del git_rm_queue

    if is_git:
        if args.git_mode in ("stage", "commit"):
            git_cmd(["add", os.path.basename(dest_app)], cwd=os.path.dirname(dest_app))
            # sys.stdout.write("git add {}\n".format(os.path.basename(dest_app)))
        '''
        else:
            sys.stdout.write("git add {}\n".format(dest_app))
        '''

        # Is there anything to stage/commit?
        if git_is_clean(os.path.dirname(dest_app), check_untracked=False):
            sys.stderr.write("No changes detected.  Nothing to {}\n".format(args.git_mode))
            return

        git_commit_app_name = app_conf.get("ui", {}).get("label", os.path.basename(dest_app))
        git_commit_new_version = app_conf.get("launcher", {}).get("version", None)
        if mode == "install":
            git_commit_message = "Install {}".format(git_commit_app_name)

            if git_commit_new_version:
                git_commit_message += " version {}".format(git_commit_new_version)
        else:
            # Todo:  Specify Upgrade/Downgrade/Refresh
            git_commit_message = "Upgrade {}".format(
                git_commit_app_name)
            git_commit_old_version = old_app_conf.get("launcher", {}).get("version", None)
            if git_commit_old_version and git_commit_new_version:
                git_commit_message += " version {} (was {})".format(git_commit_new_version,
                                                                    git_commit_old_version)
            elif git_commit_new_version:
                git_commit_message += " to version {}".format(git_commit_new_version)
        # Could possibly include some CLI arg details, like what file patterns were excluded
        git_commit_message += "\n\nSHA256 {} {}\n\nSplunk-App-managed-by: ksconf" \
            .format(f_hash, os.path.basename(args.tarball))
        git_commit_cmd = ["commit", os.path.basename(dest_app), "-m", git_commit_message]

        if not args.no_edit:
            git_commit_cmd.append("--edit")

        git_commit_cmd.extend(args.git_commit_args)

        if args.git_mode == "commit":
            capture_std = True if args.no_edit else False
            proc = git_cmd(git_commit_cmd, cwd=os.path.dirname(dest_app), capture_std=capture_std)
            if proc.returncode == 0:
                sys.stderr.write("You changes have been committed.  Please review before pushing "
                                 "If you find any issues, here are some helpful options:\n\n"
                                 "To fix some minor issues in the last commit, edit and add the "
                                 "files to be fixed, then run:\n"
                                 "\tgit commit --amend\n\n"
                                 "To roll back the last commit but KEEP the app upgrade, run:\n"
                                 "\t git reset --soft HEAD^1\n\n"
                                 "To roll back the last commit and REVERT the app upgrade, run:\n"
                                 "\tgit reset --hard HEAD^1\n\n")
            else:
                sys.stderr.write("Git commit failed.  Return code {}. Git args:  git {}\n"
                                 .format(proc.returncode, list2cmdline(git_commit_cmd)))
                return EXIT_CODE_GIT_FAILURE
        elif args.git_mode == "stage":
            sys.stdout.write("To commit later, use the following\n")
            sys.stdout.write("\tgit {}\n".format(list2cmdline(git_commit_cmd).replace("\n", "\\n")))
        # When in 'nochange' mode, no point in even noting these options to the user.
