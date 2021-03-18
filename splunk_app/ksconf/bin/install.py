# No shebang here.  Why?  Ask AppInspect  ;-(
import os
import sys

import _bootstrap

print("ksconf_app: {}".format(_bootstrap.ksconf_app))

template_unix = """\
#!{0[splunk_python]}
import os
import sys

# Bootstrap CLI
ksconf_home={0[ksconf_home]!r}
sys.path.append(ksconf_home)

if __name__ == '__main__':
    from ksconf.__main__ import cli
    cli()
"""

template_win = """\
@echo off
set PYTHONPATH=%PYTHONPATH%;{0[ksconf_home]}
call python -m ksconf "%*"
"""


splunk_home = os.environ.get("SPLUNK_HOME")

if not splunk_home:
    print("SPLUNK_HOME not set.\nPlease run as:\n\tsplunk cmd python {}".format(__file__))
    sys.exit(1)


def install_to(ksconf_home, bin_path, platform="nix"):
    bin_file = os.path.join(bin_path, "ksconf")

    if platform == "nix":
        template = template_unix
    elif platform == "windows":
        bin_file = bin_file + ".bat"
        template = template_win

    d = {}
    d["splunk_python"] = os.path.join(splunk_home, "bin", "python")  # or python.exe
    d["ksconf_home"] = ksconf_home

    print("Writing script {}".format(bin_file))
    with open(bin_file, "w") as script:
        script.write(template.format(d))

    if platform == "nix":
        os.chmod(bin_file, 0o777)


def check_path():
    # XXX:  Check to ensure that 'ksconf' (or ksconf.bat) is in $PATH
    # Careful not to get tripped up by the 'ksconf.py' in THIS directory.
    pass


if __name__ == '__main__':
    if sys.platform == "win32":
        plat = "windows"
    elif sys.platform == 'darwin' or sys.platform.startswith('linux'):
        plat = "nix"
    else:
        print("Unsupported platform:  {}".format(sys.platform))
        sys.exit(1)

    install_to(_bootstrap.ksconf_modules, os.path.join(splunk_home, "bin"), plat)

    # XXX: Report if installation path is NOT part of the user's $PATH
    check_path()

    print("Try running 'ksconf --version' to ensure that install worked correctly.")
