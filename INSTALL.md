# KSConf Installation Guide

The following doc describes installation options for Kintyre's Splunk Configuration tool.

## Requirements

 * Python 2.7
 * PIP (recommended)
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

There are several ways to install ksconf.  The following options go from the most easy and
recommended to more obscure and difficult:


### Install with PIP

The preferred installation method it to use pip to install the ksconf python package.  Since ksconf
is not registered with PyPi, it necessary to either download the git repository or a release bundle
from GitHub.  All standard python packaging approaches are available, but for the sake of non-python
developer, here are the 2 best options we recommend depending on whether or not you would like to
install for all users or just play around with it locally.


#### Install ksconf into a virtual environment (no admin access)

Installing `ksconf` with [virtualenv][virtualenv] is a great way to test the tool without requiring
admin privileges and has many advantages for a production install too.  Here are the basic steps to
get started.

Please change `venv` to a suitable path for your environment.

    # Install Python virtualenv package (if not already installed)
    pip install virtualenv

    # Create and activte new 'venv' virtual environment
    virtualenv venv
    source venv/bin/activate

    git clone https://github.com/Kintyre/ksconf.git
    cd ksconf
    pip install .


*Windows users:*  The above virtual environment activation should be run as
`venv\Scripts\activate.bat`.


#### Install ksconf system-wide (requires admin access)

On Windows, run these commands from an Administrator session.  On Mac or
Linux, simply run the install with "sudo", aka `sudo pip install .`

    git clone https://github.com/Kintyre/ksconf.git
    cd ksconf
    pip install .

#### Alternatives

Here are a few possible alternatives to the above commands that may be helpful if you don't have
`git` installed or don't have an open Internet access and need to download and transfer a tarball.

 1.  Give pip the github url (or two the build download URL; if git isn't installed)
 1.  Download the tarball and copy to the location.  (Simply replace `git clone` command with
     `tar -xzf ksconf-x.y.z.tar.gz`)
 1.  Consider using the 'ssh' github endpoints if https is blocked or if you're running a very old
     version of git lacking modern TLS support.  Use `git clone git@github.com:Kintyre/ksconf.git`


### Install with Splunk's Python

Splunk Enterprise 6.x and later installs an embedded Python 2.7 environment.
However, Splunk does not provide packing tools (such as `pip` and the `distutils` standard library
which is required to bootstrap install `pip`).  For these reasons, it's typically easier and cleaner
to install `ksconf` with the system provided Python.  However, sometime the system-provided Python
environment is the wrong version, is missing (like on Windows), or security restrictions prevent the
installation of additional packages.  In such cases, Splunk's embedded Python becomes a beacon of
hope.

    cd $SPLUNK_HOME
    git clone https://github.com/Kintyre/ksconf.git
    # or:  tar -xzvf ksconf-x.y.z.tar.gz; mv ksconf-* ksconf

    echo > $SPLUNK_HOME/bin/ksconf <<HERE
    #!/bin/sh
    export PYTHONPATH=$SPLUNK_HOME/ksconf
    exec $SPLUNK_HOME/bin/python -m ksconf.cli $*
    HERE
    chmod +x $SPLUNK_HOME/bin/ksconf

    # Test
    ksconf --version

    # Known issue:  Version will be 'None'

As to not leave out the poor souls running Windows:

 1. Open a browser to [ksconf releases](https://github.com/Kintyre/ksconf/releases/latest) on GitHub
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


# Frequent gotchas

## PIP Install TLS Error

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


# Resources

 * [Python packaging](https://docs.python.org/2.7/installing/index.html) docs provide a general
   overview on installing Python packages, how to install per-user vs install system-wide.
 * [Install PIP](https://pip.pypa.io/en/stable/installing) docs explain how to bootstrap or upgrade
   `pip` the Python packaging tool.  Recent versions of Python come with this by default, but
   releases before Python 2.7.9 do not.




[argcomplete]: https://argcomplete.readthedocs.io/en/latest/
[virtualenv]: https://virtualenv.pypa.io/en/stable/
