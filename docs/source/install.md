# Installation Guide

The following doc describes installation options for Kintyre's Splunk Configuration tool.
For most people, the simple one-line install should work fine, but if for more complex situations,
one of the below options should work.

_One-line install_ (**Try this first!**)

    pip install kintyre-splunk-conf

## Requirements

 * [Python 2.7][python-download]
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

Ksconf can be installed as a standalone executable.  This works well for testing or when all other
options fail.

From the [GitHub releases][gh-releases] page , grab the file name `ksconf-*-standalone`
and copy it to a `bin` folder and rename it `ksconf`.

This file is just a zip file, prepended with a shebang that tricks the OS to launch Python, and then
Python run the __main__.py module located inside of the zip file.  This is more officially supported
in Python 3.x, but works as far back as Python 2.6.  It worked during testing.  Good luck!


Reasons why this is a non-ideal install approach:

 * Lower performance since all python file live in a zip file, and precompiled version's can be
   cached (in Python 2.7).
 * No standard install pathway (doesn't use pip); user must manually copy the executable into place.
 * Uses a non-standard build process.  (May not be a big deal, but could cause things to break in
  the future.)



### Install the Wheel manually


Download the latest "Wheel" file file from [PyPI][pypi-files].  This example uses the name
`kintyre-splunk-conf-0.4.2-py2.py3-none-any.whl`


Option 1:  (Use `pip`, but this works offline)

    pip install ~/Downloads/kintyre-splunk-conf-0.4.2-py2.py3-none-any.whl

Option 2:  (**Broken**)

    python -m wheel unpack ~/Downloads/kintyre-splunk-conf-0.4.2-py2.py3-none-any.whl -d $(python -m site --user-site)

Option 3:  (**Ugly; should work in theroy**)

    # Switch to the local python 'site-packages' folder
    cd $(python -m site --user-site)

    # Extract the wheel
    unzip ~/Downloads/kintyre-splunk-conf-0.4.2-py2.py3-none-any.whl 
    alias ksconf='python -m ksconf.cli'
    ksconf --version


### Install with Splunk's Python

Splunk Enterprise 6.x and later installs an embedded Python 2.7 environment.
However, Splunk does not provide packing tools (such as `pip` and the `distutils` standard library
which is required to bootstrap install `pip`).  For these reasons, it's typically easier and cleaner
to install `ksconf` with the system provided Python.  However, sometime the system-provided Python
environment is the wrong version, is missing (like on Windows), or security restrictions prevent the
installation of additional packages.  In such cases, Splunk's embedded Python becomes a beacon of
hope.


***Note:  These sections need updated to use wheels instead of git/github release files***

#### On Linux or Mac

    cd $SPLUNK_HOME
    git clone https://github.com/Kintyre/ksconf.git
    # or:  tar -xzvf ksconf-x.y.z.tar.gz; mv ksconf-* ksconf
    # or:  Download wheel?  (This may be a better suggestion)

    echo > $SPLUNK_HOME/bin/ksconf <<HERE
    #!/bin/sh
    export PYTHONPATH=$SPLUNK_HOME/ksconf
    exec $SPLUNK_HOME/bin/python -m ksconf.cli $*
    HERE
    chmod +x $SPLUNK_HOME/bin/ksconf

    # Test
    ksconf --version

    # Known issue:  Version will be 'None'


#### On Windows

 1. Open a browser to [ksconf releases][gh-releases] on GitHub
 2. Download the "Source code (zip)" file.
 3. Extract the zip file to a temporary folder.  (This should create a folder named "ksconf" with
    the version number appended.)
 4. Rename the extracted folder to simply "ksconf" (Removing the appended version string.)
 5. Copy the "ksconf" folder to the "SPLUNK_HOME", `C:\Program Files\Splunk` by default.)
 6. Create a new file called `ksconf.bat` and paste in the following batch script.  Be sure to
    adjust for a non-standard `%SPLUNK_HOME%` value, if necessary.
    
        @echo off
        SET SPLUNK_HOME=C:\Program Files\Splunk
        SET PYTHONPATH=%SPLUNK_HOME%\bin;%SPLUNK_HOME%\Python-2.7\Lib\site-packages\win32;%SPLUNK_HOME%\Python-2.7\Lib\site-packages;%SPLUNK_HOME%\Python-2.7\Lib
        SET PYTHONPATH=%PYTHONPATH%;%SPLUNK_HOME%\ksconf
        CALL "%SPLUNK_HOME%\bin\python.exe" -m ksconf.cli %*

 7. Copy `ksconf.bat` to the `Splunk\bin` folder.  (This assumes that `%SPLUNK_HOME%/bin` is part of
    your `%PATH%`.  If not, find an appropriate install location.)
 8. Test by running `ksconf --version` from the command line.
    Note that there's a Known issue with this, the version will show up as 'None'.


## Validate the install

Confirm installation with the following command:

    ksconf --help

If this works, it means that `ksconf` installed and is part of your `PATH` and should be useable
everywhere in your system.  Go forth and conquer!


## Command line completion

 * Available for Bash, zsh, tcsh.  (These instructions focus on BASH)
 * Install the argcomplete python package using `pip install argcomplete`
 * Add `activate-global-python-argcomplete` to your `~.bashrc`.
   Other less-global options are available in the docs.
 * Mac OS X user may run into some issue due to the old version of Bash shipped by default.
   Install a later version with homebrew:   `brew install bash` then.  To switch to the newer bash
   by default, run `chsh /usr/local/bin/bash`
 * For more information, read the [argcomplete docs][argcomplete].


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
[gh-releases]: https://github.com/Kintyre/ksconf/releases/latest
[pip-install]: https://pip.pypa.io/en/stable/installing/
[pypi-files]: https://pypi.org/project/kintyre-splunk-conf/#files
[python-download]: https://www.python.org/downloads/
[python-packaging]: https://docs.python.org/2.7/installing/index.html
[virtualenv]: https://virtualenv.pypa.io/en/stable/
