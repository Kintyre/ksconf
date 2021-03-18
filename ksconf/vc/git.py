from __future__ import absolute_import, unicode_literals

from collections import Counter, namedtuple
from subprocess import PIPE, Popen, call, list2cmdline

from ksconf.util import _xargs, memoize

try:
    from shutil import which
except ImportError:
    from backports.shutil_which import which


GIT_BIN = "git"
GitCmdOutput = namedtuple("GitCmdOutput", ["cmd", "returncode", "stdout", "stderr", "lines"])

unitesting = False


class GitNotAvailable(Exception):
    pass


def git_cmd(args, shell=False, cwd=None, capture_std=True, encoding="utf-8"):
    if isinstance(args, tuple):
        args = list(args)
    cmdline_args = [GIT_BIN] + args
    out = None
    if capture_std:
        out = PIPE
    proc = Popen(cmdline_args, stdout=out, stderr=out, shell=shell, cwd=cwd)
    (stdout, stderr) = proc.communicate()
    if hasattr(stdout, "decode"):
        stdout = stdout.decode(encoding)
        stderr = stderr.decode(encoding)
    return GitCmdOutput(cmdline_args, proc.returncode, stdout, stderr, None)


def git_cmd_iterable(args, iterable, cwd=None, cmd_len=1024):
    base_len = sum([len(s) + 1 for s in args])
    for chunk in _xargs(iterable, cmd_len - base_len):
        p = git_cmd(args + chunk, cwd=cwd)
        if p.returncode != 0:  # pragma: no cover
            raise RuntimeError("git exited with code {}.  Command: {}".format(
                p.returncode, list2cmdline(args + chunk)))


# Shave time off of unit testing; or anyting that does CLI calls from the API
@memoize
def git_version():
    git_path = which(GIT_BIN)
    if not git_path:
        return None
    try:
        cmd = git_cmd(["--version"])
    except GitNotAvailable:
        return None
    return {
        "version": cmd.stdout.strip(),
        "path": git_path,
    }


def git_status_summary(path):
    c = Counter()
    cmd = git_cmd(["status", "--porcelain", "--ignored", "."], cwd=path)
    if cmd.returncode != 0:  # pragma: no cover
        raise RuntimeError("git command returned exit code {}.".format(cmd.returncode))
    # XY:  X=index, Y=working tree.   For our simplistic approach we consider them together.
    for line in cmd.stdout.splitlines():
        state = line[0:2]
        if state == "??":
            c["untracked"] += 1
        elif state == "!!":
            c["ignored"] += 1
        else:
            c["changed"] += 1
    return c


'''
def get_gitdir(path=None):
    # May not need this.  the 'git status' was missing '.' to make it specific to JUST the app folder
    # I thought I needed this because of my local testing git-inside-of-git scenario...
    p = git_cmd(["rev-parse", "--git-dir"], cwd=path)
    if p.returncode == 0:
        gitdir = p.stdout.strip()
        return gitdir
    # Then later you can use  git --git-dir=apps/.git --working-tree apps Splunk_TA_aws
'''


def git_is_working_tree(path=None):
    return git_cmd(["rev-parse", "--is-inside-work-tree"], cwd=path).returncode == 0


def git_is_clean(path=None, check_untracked=True, check_ignored=False):
    # ANY change to the index or working tree is considered unclean.
    c = git_status_summary(path)
    total_changes = c["changed"]
    if check_untracked:
        total_changes += c["untracked"]
    if check_ignored:
        total_changes += c["ignored"]
    '''
    print "GIT IS CLEAN?:   path={} check_untracked={} check_ignored={} total_changes={} c={}".format(
        path, check_untracked, check_ignored, total_changes, c)
    '''
    return total_changes == 0


def git_ls_files(path, *modifiers):
    # staged=True
    args = ["ls-files"]
    for m in modifiers:
        args.append("--" + m)
    proc = git_cmd(args, cwd=path)
    if proc.returncode != 0:  # pragma: no cover
        raise RuntimeError("Bad return code from git... {} add better exception handling here.."
                           .format(proc.returncode))
    return proc.stdout.splitlines()


def git_status_ui(path, *args):  # pragma: no cover
    # For unittesting purposes, this function is a nuisance
    if unitesting:
        return
    # Don't redirect the std* streams; let the output go straight to the console
    cmd = [GIT_BIN, "status", "."]
    cmd.extend(args)
    call(cmd, cwd=path)
