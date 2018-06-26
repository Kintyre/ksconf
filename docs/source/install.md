# Installation Guide

The following doc describes installation options for Kintyre's Splunk Configuration tool.
This tool is available as a normal Python package that should require very minimal effort to install
and upgrade.  However, sometimes Python packaging gets ugly and the one-liner may not work.

A portion of this document is targeted at those who can't install packages as Admin or are forced to
use Splunk's embedded Python.  For everyone else, please start with the one-liner!


## Quick install

Using pip:

    pip install kintyre-splunk-conf

System-level install:  (For Mac/Linux)

    curl https://bootstrap.pypa.io/get-pip.py | sudo python - kintyre-splunk-conf

Note:  This will also install/update `pip` and work around some known TLS/SSL issues

### Enable Bash completion

If you're on a Mac or Linux, and would like to enable bash completion, run these commands:

    pip install argcomplete
    echo 'eval "$(register-python-argcomplete ksconf)"' >> ~/.bashrc



## Requirements

 * [Python][python-download]  Supports Python 2.7, 3.4+
 * [PIP][pip-install] (strongly recommended)
 * Tested on Mac, Linux, and Windows


### Check Python version

Check your installed python version by running:

    python --version

Note that Linux distributions and Mac OS X that ship with multiple version of Python may have
renamed this to `python2`, `python2.7` or similar.

### Check PIP Version

    pip --version

If you are running a different python interpreter version, you can instead run this as:

    python2.7 -m pip --version


## Installation

There are several ways to install ksconf.  Technically all standard python packaging approaches
should work just fine, there's no compiled code or external runt-time dependencies so installation
is fairly easy, but for non-python developers there are some gotchas.   Installation options are
listed from the most easy and recommended to more obscure and difficult:


### Install from PyPI with PIP

The preferred installation method is to install via the standard Python package tool 'pip'.  Ksconf
can be installed via the registered `kintyre-splunk-conf` package using the standard python process.

There are 2 popular variations, depending on whether or not you would like to install for all users
or just play around with it locally.


#### Install ksconf into a virtual environment

***Use this option if you don't have admin access***

Installing `ksconf` with [virtualenv][virtualenv] is a great way to test the tool without requiring
admin privileges and has many advantages for a production install too.  Here are the basic steps to
get started.

Please change `venv` to a suitable path for your environment.

    # Install Python virtualenv package (if not already installed)
    pip install virtualenv

    # Create and activte new 'venv' virtual environment
    virtualenv venv
    source venv/bin/activate

    pip install kintyre-splunk-conf

*Windows users:*  The above virtual environment activation should be run as
`venv\Scripts\activate.bat`.


#### Install ksconf system-wide

***Note:  This requires admin access.***

This is the absolute easiest install method where 'ksconf' is available to all users on the system
but it requires root access.

On Mac or Linux, run:

    sudo pip install kintyre-splunk-conf

On Windows, run this commands from an Administrator console.

    pip install kintyre-splunk-conf


### Install from GIT

If you'd like to contribute to ksconf, or just build the latest and greatest, then install from the
git repository is a good choice.  (Technically this is still installing with `pip`, so it's easy to
switch between a PyPI install, and a local install.)

    git clone https://github.com/Kintyre/ksconf.git
    cd ksconf
    pip install .

See [developer docs](devel.html) for additional details about contributing to ksconf.


## Use the standalone executable

Ksconf can be installed as a standalone executable zip app.  This approach still requires a python
interpreter to be present either from the OS or the one embedded with Splunk Enterprise.  This works
well for testing or when all other options fail.  

From the [GitHub releases][gh-releases] page, grab the file name `ksconf-*.pyz`, download it, copy
it to a `bin` folder in your PATH and rename it `ksconf`.  The default shebang looks for 'python' in
the PATH, but this can be adjusted as needed.  Since installing with Splunk is a common use case, a
second file named `ksconf-*-splunk.pyz` already has the shebang set for the standard `/opt/splunk`
install path.

Typical embedded Splunk install example:

    VER=0.5.0
    curl https://github.com/Kintyre/ksconf/releases/download/v${VER}/ksconf-${VER}-splunk.pyz
    mv ksconf-${VER}-splunk.pyz /opt/splunk/bin/
    cd /opt/splunk/bin
    ln -sf ksconf-${VER}-splunk.pyz ksconf
    chmod +x ksconf
    ksconf --version


Reasons why this is a non-ideal install approach:

 * Lower performance since all python files live in a zip file, and precompiled version's can be
   cached.
 * No standard install pathway (doesn't use pip); user must manually copy the executable into place.
 * Uses a non-standard build process.  (May not be a big deal, but could cause things to break in
  the future.)



### Install the Wheel manually (offline mode)

Download the latest "Wheel" file file from [PyPI][pypi-files], copy it to the destination server
and install with pip.

Offline pip install:

    pip install ~/Downloads/kintyre-splunk-conf-0.4.2-py2.py3-none-any.whl


### Install with Splunk's Python

Splunk Enterprise 6.x and later installs an embedded Python 2.7 environment.
However, Splunk does not provide packing tools (such as `pip` or the `distutils` standard library
which is required to bootstrap install `pip`).  For these reasons, it's typically easier and cleaner
to install `ksconf` with the system provided Python.  However, sometimes the system-provided Python
environment is the wrong version, is missing (like on Windows), or security restrictions prevent the
installation of additional packages.  In such cases, Splunk's embedded Python becomes a beacon of
hope.

#### On Linux or Mac

Download the latest "Wheel" file file from [PyPI][pypi-files].  The path to this download will be
set in the `pkg` variable as shown below.

Setup the shell:

    export SPLUNK_HOME=/opt/splunk
    export pkg=~/Downloads/kintyre_splunk_conf-0.4.9-py2.py3-none-any.whl

Run the following:

    cd $SPLUNK_HOME
    mkdir Kintyre
    cd Kintyre
    # Unzip the 'kconf' folder into SPLUNK_HOME/Kintyre
    unzip "$pkg"

    cat > $SPLUNK_HOME/bin/ksconf <<HERE
    #!/bin/sh
    export PYTHONPATH=$PYTHONPATH:$SPLUNK_HOME/Kintyre
    exec $SPLUNK_HOME/bin/python -m ksconf.cli \$*
    HERE
    chmod +x $SPLUNK_HOME/bin/ksconf

Test the install:

    ksconf --version

#### On Windows

 1. Open a browser and download the latest "Wheel" file file from [PyPI][pypi-files].
 2. Rename the `.whl` extension to `.zip`.  (This may require showing file extensions in Explorer.)
 3. Extract the zip file to a temporary folder.  (This should create a folder named "ksconf")
 4. Create a new folder called "Kintyre" under the Splunk installation path (aka `SPLUNK_HOME`)
    By default this is `C:\Program Files\Splunk`.
 5. Copy the "ksconf" folder to "SPLUNK_HOME\Kintyre".
 6. Create a new batch file called `ksconf.bat` and paste in the following.  Be sure to
    adjust for a non-standard `%SPLUNK_HOME%` value, if necessary.

        @echo off
        SET SPLUNK_HOME=C:\Program Files\Splunk
        SET PYTHONPATH=%SPLUNK_HOME%\bin;%SPLUNK_HOME%\Python-2.7\Lib\site-packages\win32;%SPLUNK_HOME%\Python-2.7\Lib\site-packages;%SPLUNK_HOME%\Python-2.7\Lib
        SET PYTHONPATH=%PYTHONPATH%;%SPLUNK_HOME%\Kintyre
        CALL "%SPLUNK_HOME%\bin\python.exe" -m ksconf.cli %*

 7. Move `ksconf.bat` to the `Splunk\bin` folder.  (This assumes that `%SPLUNK_HOME%/bin` is part of
    your `%PATH%`.  If not, add it, or find an appropriate install location.)
 8. Test this by running `ksconf --version` from the command line.


## Validate the install

Confirm installation with the following command:

    ksconf --help

If this works, it means that `ksconf` installed and is part of your `PATH` and should be useable
everywhere in your system.  Go forth and conquer!


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

    # Reload your bashrc (Alternative:  restart your shell)
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


## Frequent gotchas

### PIP Install TLS Error

If `pip` throws an error message like the following:

    There was a problem confirming the ssl certificate: [SSL: TLSV1_ALERT_PROTOCOL_VERSION] tlsv1 alert protocol version
    ...
    No matching distribution found for setuptools


The problem is likely caused by changes to PyPI website in April 2018 when support for TLS v1.0 and
1.1 were removed.  Downloading new packages requires upgrading to a new version of pip.  Like so:

Upgrade pip as follows:

    curl https://bootstrap.pypa.io/get-pip.py | python

Note:  Use `sudo python` above if not in a virtual environment.

Helpful links:

 * [Not able to install Python packages [SSL: TLSV1_ALERT_PROTOCOL_VERSION]](https://stackoverflow.com/a/49769015/315892)
 * ['pip install' fails for every package ("Could not find a version that satisfies the requirement")](https://stackoverflow.com/a/49748494/315892)


## Resources

 * [Python packaging][python-packaging] docs provide a general
   overview on installing Python packages, how to install per-user vs install system-wide.
 * [Install PIP][pip-install] docs explain how to bootstrap or upgrade
   `pip` the Python packaging tool.  Recent versions of Python come with this by default, but
   releases before Python 2.7.9 do not.



[argcomplete]: https://argcomplete.readthedocs.io/en/latest/
[argcomplete-142]: https://github.com/kislyuk/argcomplete/issues/142
[gh-releases]: https://github.com/Kintyre/ksconf/releases/latest
[pip-install]: https://pip.pypa.io/en/stable/installing/
[pypi-files]: https://pypi.org/project/kintyre-splunk-conf/#files
[python-download]: https://www.python.org/downloads/
[python-packaging]: https://docs.python.org/3/installing/index.html
[virtualenv]: https://virtualenv.pypa.io/en/stable/
