import sys
import os

this_script = os.path.abspath(__file__ or sys.argv[0])
ksconf_app = os.path.dirname(this_script)
ksconf_modules = os.path.join(ksconf_app, "lib")

print("ksconf_app: {}".format(ksconf_app))


template = """\
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
splunk_home = os.environ.get("SPLUNK_HOME")

def install_to(ksconf_home, bin_path):
    bin_file = os.path.join(bin_path, "ksconf")
    # if windows:  bin_file = bin_file + ".py"

    d = {}
    d["splunk_python"] = os.path.join(splunk_home, "bin", "python") # or python.exe
    d["ksconf_home"] = ksconf_home
    print("Writing script {}".format(bin_file))
    with open(bin_file, "w") as script:
        script.write(template.format(d))
    os.chmod(bin_file, 0o777)


if __name__ == '__main__':
    install_to(ksconf_modules, os.path.join(splunk_home, "bin"))
