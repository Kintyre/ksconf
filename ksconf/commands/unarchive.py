""" SUBCOMMAND:  ``ksconf unarchive <tarball>``

Usage example:

.. code-block:: sh

    ksconf unarchive splunk-add-on-for-amazon-web-services_111.tgz

"""

from __future__ import absolute_import, print_function, unicode_literals

import os
import re
from io import StringIO
from subprocess import list2cmdline

from ksconf.archive import (extract_archive, gaf_filter_name_like,
                            gen_arch_file_remapper, sanity_checker)
from ksconf.commands import KsconfCmd, dedent
from ksconf.conf.parser import PARSECONF_LOOSE, ConfParserException, default_encoding, parse_conf
from ksconf.consts import EXIT_CODE_FAILED_SAFETY_CHECK, EXIT_CODE_GIT_FAILURE, KSCONF_DEBUG
from ksconf.filter import create_filtered_list
from ksconf.util.compare import _cmp_sets
from ksconf.util.completers import DirectoriesCompleter, FilesCompleter
from ksconf.util.file import dir_exists, file_hash, relwalk
from ksconf.vc.git import (git_cmd, git_cmd_iterable, git_is_clean,
                           git_is_working_tree, git_ls_files, git_status_ui,
                           git_version)

allowed_extentions = ("*.tgz", "*.tar.gz", "*.spl", "*.zip")


# XXX:  Add a git status --ignored --porcelain APPNAME check to list out files/dirs that are excluded...

# XXX:  Update code base to use ksconf.layer, as was done for the 'ksconf combine' command.


DEFAULT_DIR = "default"


class UnarchiveCmd(KsconfCmd):
    help = "Install or upgrade an existing app in a git-friendly and safe way"
    description = dedent("""
    Install or overwrite an existing app in a git-friendly way.
    If the app already exists, steps will be taken to upgrade it safely.

    The ``default`` folder can be redirected to another path (i.e., ``default.d/10-upstream`` or
    other desirable path if you're using the ``ksconf combine`` tool to manage extra layers).
    """)
    format = "manual"
    maturity = "beta"

    def register_args(self, parser):
        parser.add_argument("tarball", metavar="SPL",
                            help="The path to the archive to install."
                            ).completer = FilesCompleter(allowednames=allowed_extentions)
        parser.add_argument("--dest", metavar="DIR", default=".", help=dedent("""\
            Set the destination path where the archive will be extracted.
            By default, the current directory is used.  Sane values include: etc/apps,
            etc/deployment-apps, and so on.""")
                            ).completer = DirectoriesCompleter()
        parser.add_argument("--app-name", metavar="NAME", default=None, help=dedent("""\
            The app name to use when expanding the archive.
            By default, the app name is taken from the archive as the top-level path included
            in the archive (by convention).
            """))
        parser.add_argument("--default-dir", default=DEFAULT_DIR, metavar="DIR", help=dedent("""\
            Name of the directory where the default contents will be stored.
            This is a useful feature for apps that use a dynamic default directory
            that's created and managed by the 'combine' mode.""")
                            ).completer = DirectoriesCompleter()
        parser.add_argument("--exclude", "-e", action="append", default=[], help=dedent("""\
            Add a file pattern to exclude from extraction.
            Splunk's pseudo-glob patterns are supported here.
            ``*`` for any non-directory match,
            ``...`` for ANY (including directories),
            and ``?`` for a single character."""))
        parser.add_argument("--keep", "-k", action="append", default=[],
                            help=dedent("""\
            Specify a pattern for files to preserve during an upgrade.
            Repeat this argument to keep multiple patterns."""))
        parser.add_argument("--allow-local", default=False, action="store_true", help=dedent("""\
            Allow local/* and local.meta files to be extracted from the archive.
            """))
        parser.add_argument("--git-sanity-check",
                            choices=["off", "changed", "untracked", "ignored"],
                            default="untracked", help=dedent("""\
            By default, 'git status' is run on the destination folder to detect working tree or
            index modifications before the unarchive process start.

            Sanity check choices go from least restrictive to most thorough:

            'off' prevents all safety checks.
            'changed' aborts only upon local modifications to files tracked by git.
            'untracked' (the default) looks for changed and untracked files.
            'ignored' aborts is (any) local changes, untracked, or ignored files are found.
            """))
        parser.add_argument("--git-mode", default="stage",
                            choices=["nochange", "stage", "commit"], help=dedent("""\
            Set the desired level of git integration.
            The default mode is *stage*, where new, updated, or removed files are automatically
            handled for you.

            To prevent any ``git add`` or ``git rm`` commands from being run, pick the
            'nochange' mode.
            """))
        parser.add_argument("--no-edit",
                            action="store_true", default=False, help=dedent("""\
            Tell git to skip opening your editor on commit.
            By default, you will be prompted to review/edit the commit message.
            (Git Tip:  Delete the content of the default message to abort the commit.)"""))
        parser.add_argument("--git-commit-args", "-G", default=[], action="append",
                            help="Extra arguments to pass to 'git'")

    def run(self, args):
        """ Install / upgrade a Splunk app from an archive file """
        # Handle ignored files by preserving them as much as possible.
        # Add --dry-run mode?  j/k - that's what git is for!

        DEBUG = KSCONF_DEBUG in os.environ

        if not os.path.isfile(args.tarball):
            self.stderr.write("No such file or directory {}\n".format(args.tarball))
            return EXIT_CODE_FAILED_SAFETY_CHECK

        if not os.path.isdir(args.dest):
            self.stderr.write("Destination directory does not exist: {}\n".format(args.dest))
            return EXIT_CODE_FAILED_SAFETY_CHECK

        f_hash = file_hash(args.tarball)
        self.stdout.write("Inspecting archive:               {}\n".format(args.tarball))

        # TODO: Grab and share wit ksconf_shared.py in https://github.com/Kintyre/ansible-collection-splunk
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
                conffile = StringIO(gaf.payload.decode(default_encoding))
                conffile.name = os.path.join(args.tarball, gaf.path)
                app_conf = parse_conf(conffile, profile=PARSECONF_LOOSE)
                del conffile
            elif gaf_relpath.startswith("local" + os.path.sep) or \
                    gaf_relpath.endswith("local.meta"):
                local_files.add(gaf_relpath)
            app_name.add(gaf.path.split("/", 1)[0])
            del gaf_app, gaf_relpath
        if len(app_name) > 1:
            self.stderr.write("The 'unarchive' command only supports extracting a single splunk"
                              " app at a time.\nHowever the archive {} contains {} apps:  {}\n"
                              "".format(args.tarball, len(app_name), ", ".join(app_name)))
            return EXIT_CODE_FAILED_SAFETY_CHECK
        else:
            app_name = app_name.pop()
        del a
        if local_files:
            self.stderr.write("Local {} files found in the archive.  ".format(len(local_files)))
            if args.allow_local:
                self.stderr.write("Keeping these due to the '--allow-local' flag\n")
            else:
                self.stderr.write("Excluding local files by default.  "
                                  "Use '--allow-local' to override.")

        if not new_app_name and True:  # if not --no-app-name-fixes
            if app_name.endswith("-master"):
                self.stdout.write("Automatically dropping '-master' from the app name.  "
                                  "This is often the result of a github export.\n")
                # Trick, but it works...
                new_app_name = app_name[:-7]
            mo = re.search(r"(.*)-\d+\.[\d.-]+$", app_name)
            if mo:
                self.stdout.write("Automatically removing the version suffix from the app name.  "
                                  "'{}' will be extracted as '{}'\n".format(app_name, mo.group(1)))
                new_app_name = mo.group(1)

        app_basename = new_app_name or app_name
        dest_app = os.path.join(args.dest, app_basename)
        self.stdout.write("Inspecting destination folder:    {}\n".format(os.path.abspath(dest_app)))

        # FEEDBACK TO THE USER:   UPGRADE VS INSTALL, GIT?, APP RENAME, ...
        app_name_msg = app_name

        git_ver = git_version()
        if git_ver is None:
            vc_msg = "without version control support (git not present)"
            is_git = False
        else:
            vc_msg = "without version control support"

        old_app_conf = {}

        if os.path.isdir(dest_app):
            mode = "upgrade"
            if git_ver:
                is_git = git_is_working_tree(dest_app)
            try:
                # Ignoring the 'local' entries since distributed apps shouldn't contain local
                old_app_conf_file = os.path.join(dest_app, args.default_dir, "app.conf")
                old_app_conf = parse_conf(old_app_conf_file, profile=PARSECONF_LOOSE)
            except (ConfParserException, FileNotFoundError):
                self.stderr.write("Unable to read app.conf from existing install.\n")
                # Assume upgrade form unknown version
        else:
            mode = "install"
            if git_ver:
                is_git = git_is_working_tree(args.dest)
        if is_git:
            vc_msg = "with git support"
        if new_app_name and new_app_name != app_name:
            app_name_msg = "{} (renamed from {})".format(new_app_name, app_name)

        def show_pkg_info(conf, label):
            self.stdout.write("{} packaging info:    '{}' by {} (version {})\n".format(
                label,
                conf.get("ui", {}).get("label", "Unknown"),
                conf.get("launcher", {}).get("author", "Unknown"),
                conf.get("launcher", {}).get("version", "Unknown")))

        if old_app_conf:
            show_pkg_info(old_app_conf, " Installed app")
        if app_conf:
            show_pkg_info(app_conf, "   Tarball app")

        self.stdout.write("About to {} the {} app {}.\n".format(mode, app_name_msg, vc_msg))

        existing_files = set()
        if mode == "upgrade":
            if is_git:
                existing_files.update(git_ls_files(dest_app))
                if not existing_files:
                    self.stderr.write("App is in a git repository but no files have been staged "
                                      "or committed.  Either commit or remove '{}' and try again."
                                      "\n".format(dest_app))
                    return EXIT_CODE_FAILED_SAFETY_CHECK
                if args.git_sanity_check == "off":
                    self.stdout.write("The 'git status' safety checks have been disabled via CLI"
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
                        self.stdout.write("Git folder is clean.  "
                                          "Okay to proceed with the upgrade.\n")
                    else:
                        self.stderr.write("Unable to move forward without a clean working tree.\n"
                                          "Clean up and try again.  "
                                          "Modifications are listed below.\n\n")
                        self.stderr.flush()
                        if args.git_sanity_check == "changed":
                            git_status_ui(dest_app, "--untracked-files=no")
                        elif args.git_sanity_check == "ignored":
                            git_status_ui(dest_app, "--ignored")
                        else:
                            git_status_ui(dest_app)
                        return EXIT_CODE_FAILED_SAFETY_CHECK
            else:
                for (root, dirs, filenames) in relwalk(dest_app):
                    for fn in filenames:
                        existing_files.add(os.path.join(root, fn))
            self.stdout.write("Before upgrade.  App has {} files\n".format(len(existing_files)))
        elif is_git:
            self.stdout.write("Git clean check skipped.  Not needed for a fresh app install.\n")

        def fixup_pattern_bw(patterns, prefix=None):
            modified = []
            for pattern in patterns:
                if pattern.startswith("./"):
                    if prefix:
                        pattern = "{0}/{1}".format(prefix, pattern[2:])
                    else:
                        pattern = pattern[2:]
                    modified.append(pattern)
                # If a pattern like 'tags.conf' or '*.bak' is provided, use basename match (any dir)
                elif "/" not in pattern:
                    modified.append("(^|.../)" + pattern)
                else:
                    modified.append(pattern)
            return modified

        # PREP ARCHIVE EXTRACTION
        installed_files = set()
        excludes = list(args.exclude)
        if not args.allow_local:
            for pattern in local_files:
                excludes.append("./" + pattern)
        excludes = fixup_pattern_bw(excludes, app_basename)
        self.stderr.write("Extraction exclude patterns:  {!r}\n".format(excludes))
        exclude_filter = create_filtered_list("splunk", default=False)
        exclude_filter.feedall(excludes)

        # Calculate path rewrite operations
        path_rewrites = []
        files_iter = extract_archive(args.tarball)
        if True:
            files_iter = sanity_checker(files_iter)
        if args.default_dir != DEFAULT_DIR:
            rep = r"\1/{}/".format(args.default_dir.strip("/"))
            path_rewrites.append((re.compile(r"^(/?[^/]+)/{}/".format(DEFAULT_DIR)), rep))
            del rep
        if new_app_name:
            # We do have the "app_name" extracted from our first pass above, but
            regex = re.compile(r'^([^/]+)(?=/)')
            path_rewrites.append((regex, new_app_name))
        if path_rewrites:
            files_iter = gen_arch_file_remapper(files_iter, path_rewrites)

        # Filer out "removed" files; and let us keep some based on a keep-allowlist
        self.stdout.write("Extracting app now...\n")
        for gaf in files_iter:
            if exclude_filter.match(gaf.path):
                self.stdout.write("Skipping [blocklist] {}\n".format(gaf.path))
                continue
            if not is_git or args.git_mode in ("nochange", "stage"):
                self.stdout.write("{0:60s} {2:o} {1:-6d}\n".format(gaf.path, gaf.size, gaf.mode))
            installed_files.add(gaf.path.split("/", 1)[1])
            full_path = os.path.join(args.dest, gaf.path)
            dir_exists(os.path.dirname(full_path))
            with open(full_path, "wb") as fp:
                fp.write(gaf.payload)
            os.chmod(full_path, gaf.mode)
            del fp, full_path

        files_new, files_upd, files_del = _cmp_sets(installed_files, existing_files)

        if DEBUG:
            print("New: \n\t{}".format("\n\t".join(sorted(files_new))))
            print("Existing: \n\t{}".format("\n\t".join(sorted(files_upd))))
            print("Removed:  \n\t{}".format("\n\t".join(sorted(files_del))))

        self.stdout.write("Extracted {} files:  {} new, {} existing, and {} removed\n".format(
            len(installed_files), len(files_new), len(files_upd), len(files_del)))

        # Filer out "removed" files; and let us keep some based on a keep-allowlist:  This should
        # include things like local, ".gitignore", ".gitattributes" and so on

        keep_list = [".git*"]
        keep_list.extend(args.keep)
        if not args.allow_local:
            keep_list += ["local/...", "local.meta"]
        keep_list = fixup_pattern_bw(keep_list)
        self.stderr.write("Keep file patterns:  {!r}\n".format(keep_list))

        keep_filter = create_filtered_list("splunk", default=False)
        keep_filter.feedall(keep_list)

        files_to_delete = []
        files_to_keep = []
        for fn in files_del:
            if keep_filter.match(fn):
                # How to handle a keep of "default.d/..." when we DO want to cleanup the default
                # redirect folder of "default.d/10-upstream"?
                # This may be an academic question since most apps will continue to send
                # an ever increasing list of default files (to mask out old/unused ones)
                self.stdout.write("Keeping {}\n".format(fn))
                files_to_keep.append(fn)
            else:
                files_to_delete.append(fn)
        if files_to_keep:
            self.stdout.write("Keeping {} of {} files marked for deletion due to allow list.\n"
                              .format(len(files_to_keep), len(files_del)))
        git_rm_queue = []

        if files_to_delete:
            self.stdout.write("Removing files not present in the upgraded version of the app.\n")
        for fn in files_to_delete:
            path = os.path.join(dest_app, fn)
            if is_git and args.git_mode in ("stage", "commit"):
                self.stdout.write("git rm -f {}\n".format(path))
                git_rm_queue.append(fn)
            else:
                self.stdout.write("rm -f {}\n".format(path))
                os.unlink(path)

        if git_rm_queue:
            # Run 'git rm file1 file2 file3 ..." (using an xargs like mechanism)
            git_cmd_iterable(["rm"], git_rm_queue, cwd=dest_app)
        del git_rm_queue

        if is_git:
            if args.git_mode in ("stage", "commit"):
                git_cmd(["add", "--all", os.path.basename(dest_app)], cwd=os.path.dirname(dest_app))
                # self.stdout.write("git add {}\n".format(os.path.basename(dest_app)))
            '''
            else:
                self.stdout.write("git add {}\n".format(dest_app))
            '''

            # Is there anything to stage/commit?
            if git_is_clean(os.path.dirname(dest_app), check_untracked=False):
                self.stderr.write("No changes detected.  Nothing to {}\n".format(args.git_mode))
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
                proc = git_cmd(git_commit_cmd, cwd=os.path.dirname(dest_app),
                               capture_std=capture_std)
                if proc.returncode == 0:
                    self.stderr.write(dedent("""\
                    Your changes have been committed.  Please review before pushing.  If you
                    find any issues, here are some possible solutions:


                    To fix issues in the last commit, edit and add the files to be fixed, then run:

                        git commit --amend

                    To roll back the last commit but KEEP the app upgrade, run:

                        git reset --soft HEAD^1

                    To roll back the last commit and REVERT the app upgrade, run:

                        git reset --hard HEAD^1

                    NOTE:  Make sure you have *no* other uncommitted changes before running 'reset'.
                    """))
                else:
                    self.stderr.write("Git commit failed.  Return code {}.  Git args:  git {}\n"
                                      .format(proc.returncode, list2cmdline(git_commit_cmd)))
                    return EXIT_CODE_GIT_FAILURE
            elif args.git_mode == "stage":
                self.stdout.write("To commit later, use the following\n")
                self.stdout.write(
                    "\tgit {}\n".format(list2cmdline(git_commit_cmd).replace("\n", "\\n")))
            # When in 'nochange' mode, no point in even noting these options to the user.
