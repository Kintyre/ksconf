# Installation Guide

The following doc describes installation options for Kintyre's Splunk Configuration tool.
This tool is available as a normal Python package that should require very minimal effort to install
and upgrade.  However, sometimes Python packaging gets ugly and the one-liner may not work.

This document covers the most common scenarios.  If you are still running into issues, please
consider using the KSCONF app for Splunk as a means to install `ksconf` on your system.  

But since there are times when a python-level install is preferable, and since I already written up
tons of notes on how to do it, please take a look at the [Advanced Installation Guide](install_advanced.html)

## Quick install

Download and install the **[KSCONF App for Splunk][ksconfapp]**.  Then open a shell, switch to the
Splunk user account and run this one-time bootstrap command.

    splunk cmd python $SPLUNK_HOME/etc/apps/ksconf/bin/bootstrap_bin.py 

**Using pip**:

    pip install kintyre-splunk-conf

**System-level install**:  (For Mac/Linux)

    curl https://bootstrap.pypa.io/get-pip.py | sudo python - kintyre-splunk-conf

Note:  This will also install/update `pip` and work around some known TLS/SSL issues

**Enable Bash completion:**

If you're on a Mac or Linux, and would like to enable bash completion, run these commands:

    pip install argcomplete
    echo 'eval "$(register-python-argcomplete ksconf)"' >> ~/.bashrc

(Currently unavaiable for Splunk APP installs; not because it can't work, but because it's not
documented or tested yet.  Pull request welcome.)


## Requirements


_Python package install:_
 * [Python][python-download]  Supports Python 2.7, 3.4+
 * [PIP][pip-install] (strongly recommended)
 * Tested on Mac, Linux, and Windows

_Splunk app install:_
  * Splunk 6.0 or greater is installed


### Check Python version

Check your installed python version by running:

    python --version

Note that Linux distributions and Mac OS X that ship with multiple version of Python may have
renamed this to `python2`, `python2.7` or similar.

### Check PIP Version

    pip --version

If you are running a different python interpreter version, you can instead run this as:

    python2.7 -m pip --version


## Install from GIT

If you'd like to contribute to ksconf, or just build the latest and greatest, then install from the
git repository is a good choice.  (Technically this is still installing with `pip`, so it's easy to
switch between a PyPI install, and a local install.)

    git clone https://github.com/Kintyre/ksconf.git
    cd ksconf
    pip install .

See [developer docs](devel.html) for additional details about contributing to ksconf.



## Command line completion

Bash completion allows for a more intuitive interactive workflow by providing quick access to
command line options and file completions.  Often this saves time since the user can avoid mistyping
file names or be reminded of which command line actions and arguments are available without
switching contexts.  For example, if the user types `ksconf d` and hits *<TAB>* then the `ksconf
diff` is completed.  Or if the user types `ksconf` and hits tab twice, the full list of command
actions are listed.

This feature is use the [argcomplete][argcomplete] python package and supports Bash, zsh, tcsh.

Install via pip:

    pip install argcomplete

Enable command line completion for ksconf can be done in two ways.  The easiest option is to enable
it for ksconf only.  (However, it only works for the current user, it can break if the ksconf
command is referenced in a non-standard way.)  The alternate option is to enable global command line
completion for all python scripts at once, which is preferable if you use this module with many
python tool.

Enable argcomplete for ksconf only:

    # Edit your bashrc script
    vim ~.bashrc

    # Add the following line
    eval "$(register-python-argcomplete ksconf)"

    # Restart you shell, or just reload by running
    source ~/.bashrc

To enable argcomplete globally, run the command:

    activate-global-python-argcomplete

This adds new script to your the `bash_completion.d` folder, which can be use for all scripts and
all users, but it does add some minor overhead to each completion command request.


OS-specific notes:

 * **Mac OS X**: The global registration option has issue due the old version of Bash shipped by
   default.  So either use the one-shot registration or install a later version of bash with
   homebrew:   `brew install bash` then.  Switch to the newer bash by default with
   `chsh /usr/local/bin/bash`.
 * **Windows**:  Argcomplete doesn't work on windows Bash for GIT.
   See [argcomplete issue 142][argcomplete-142] for more info.  If you really want this, use Linux
   subsystem for Windows instead.


[argcomplete-142]: https://github.com/kislyuk/argcomplete/issues/142
[argcomplete]: https://argcomplete.readthedocs.io/en/latest/
[ksconfapp]:  https://github.com/Kintyre/ksconf/releases/latest
[pip-install]: https://pip.pypa.io/en/stable/installing/
[python-download]: https://www.python.org/downloads/
