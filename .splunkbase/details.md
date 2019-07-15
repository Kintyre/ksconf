
# What is KSCONF?

KSCONF is a command-line tool that helps administrators and developers manage their Splunk environments by enhancing control of their configuration files.  The interface is modular so that each function (or subcommand) can be learned quickly and used independently.  While most users will probably only use a subset of the total capabilities of this tool, it’s reassuring to have a deep toolbox of power goodies ready to be unleashed at a moments notice.  Ksconf works with (and does not replace) your existing Splunk deployment mechanisms and version control tools.

KSCONF is open source and an open development effort.  Check us out on [GitHub](https://github.com/Kintyre/ksconf#kintyres-splunk-configuration-tool)

Pronounced:   k·s·kȯnf

## Design principles

- *Ksconf is a toolbox.*  - Each tool has a specific purpose and function that works independently.  Borrowing from the Unix philosophy, each command should do one small thing well and be easily combined to handle higher-order tasks.
- *When possible, be familiar.* - Various commands borrow from popular UNIX command line tools such as “grep” and “diff”.  The overall modular nature of the command is similar to the modular interface used by “git” and the “splunk” cli.
- *Don’t impose workflow.* - Ksconf works with or without version control and independently of your deployment mechanisms.  (If you are looking to implement these things, ksconf is a great building block)
- *Embrace automated testing.* - It’s impractical to check every scenarios between each release, but significant work has gone into unittesting the CLI to avoid breaks between releases.

## Common uses for ksconf
- Promote changes from “local” to “default”
- Maintain multiple independent layers of configurations
- Reduce duplicate settings in a local file
- Upgrade apps stored in version control
- Merge or separate configuration files
- Push .conf stanzas to a REST endpoint (send custom configs to Splunk Cloud)

## What's in the KSCONF App for Splunk?

This Splunk app comes bundled with a CLI tool that helps manage other Splunk apps.  While this is not a traditional use case for a Splunk app, it is a very quick and easy way to deploy ksconf.

Why did we make this a Splunk app?   Well, while ksconf is technically just a Python package that can be deployed in a variety of ways, we found that the logistics of getting it deployed can be quite difficult due to a packaging issues, legacy cruft, and OS limitations.  This approach avoids all that mess.


# Getting Started

Full documentation for ksconf and, therefore this app, is hosted at read-the-docs.  A full copy of the `ksconf` documentation is also included, just like how Splunk ships with a fully copy of the docs in the system/README folder.  (And all the air-gapped people rejoice! but sadly, no one could hear them.)


## Docs

  * [Official docs](https://ksconf.readthedocs.io/en/latest/) hosted via ReadTheDocs.io
  * [Command line reference](https://ksconf.readthedocs.io/en/latest/cmd.html)

## Need help?

 * [Ask questions](https://github.com/Kintyre/ksconf/issues/new?labels=question)
 * Chat about [#ksconf](https://slack.com/app_redirect?channel=CDVT14KUN) on the Splunk User group [Slack](https://splunk-usergroups.slack.com) channel

## Get Involved

 * [Report bugs](https://github.com/Kintyre/ksconf/issues/new?template=bug.md)
 * Review [known bugs](https://github.com/Kintyre/ksconf/labels/bug)
 * [Request new features](https://github.com/Kintyre/ksconf/issues/new?template=feature-request.md&labels=enhancement)
 * [Contribute code](https://ksconf.readthedocs.io/en/latest/devel.html#contributing)

## Roadmap

Additional Splunk UI feature are planned, but currently not implemented.

 * Dashboard to track all changes coordinated by `ksconf`
 * Configuration snapshot tracking
 * Custom SPL command to give visibility into the what exists in the `local` folder.  (The built-in `rest` command only shows you the final merged view of your settings; and sometimes you have to look deeper.)

## Installation & Configuration

See the [Install an add-on](https://docs.splunk.com/Documentation/AddOns/released/Overview/Singleserverinstall) in Splunk's official documentation.  There is one manual step required to active the CLI portion of this app, if you choose to do so.  See the [Installation docs](https://ksconf.readthedocs.io/en/latest/install.html) for more details.

## Support

Community support is available on best-effort basis.  For information about commercial support, contact [Kintyre](mailto:hello@kintyre.co)
Issues are tracked via [GitHub](https://github.com/Kintyre/ksconf/issues)

## History
See the full [Change log](https://ksconf.readthedocs.io/en/latest/changelog.html)
