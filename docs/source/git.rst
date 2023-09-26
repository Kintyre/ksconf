Git tips & tricks
=================

These tips & tricks are based on prior Splunk, git, and ksconf experience.
None of this content is an endorsement of a particular approach or tool.
Read the docs, and take responsibility.  As always, your millage may vary.

.. _ksconf_pre_commit:

Pre-commit hooks
----------------

Ksconf is setup to work as a `pre-commit`_ plugin.
To use ksconf in this manner, simply configure the ksconf repo in your pre-commit configuration file.
If you haven't done any of this before, it's not difficult to setup but is beyond the scope of this guide.
We suggest that you read the pre-commit docs and review this section when you are ready to setup the hooks.


Hooks provided by ksconf
~~~~~~~~~~~~~~~~~~~~~~~~~

Three hooks are currently defined by the ksconf repository:


    ksconf-check
        Runs :ref:`ksconf_cmd_check` to perform basic validation tests against all files
        in your repo that end with ``.conf`` or ``.meta``.
        Any errors will be reported by the UI at commit time and
        you'll be able to correct mistakes before bogus files are committed into your repo.
        If you're not sure why you'd need this, check out :ref:`Why validate my conf files? <why_check>`

    ksconf-sort
        Runs :ref:`ksconf_cmd_sort` to normalize any of your ``.conf`` or ``.meta`` files
        which will make diffs more readable and merging more predictable.
        As with any hook, you can customize the filename pattern of which files this applies to.
        For example, to manually organize :file:`props.conf` files, simply add the ``exclude`` setting.
        *See Example below.*

    ksconf-xml-format:
        Runs :ref:`ksconf_cmd_xml-format` to apply consistency to your XML representations of Simple XML dashboards and navigation files.
        Dashboard Studio views can also be formatted too, along with the nested JSON payload.
        Formatting includes appropriate indention and the automatic addition of ``<![CDATA[ ... ]]>`` blocks, as needed,
        to reduce the need for XML escaping, resulting in more readable source file.
        By default, this hook looks at standard locations where XML views and navigation typically live.

Configuring pre-commit hooks in you repo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To add ksconf pre-commit hooks to your repository, add the following content to your
:file:`.pre-commit-config.yaml` file:


..  code-block:: yaml
    :name: .pre-commit-config.yaml

    repos:
    - repo: https://github.com/Kintyre/ksconf
      rev: v0.11.8
      hooks:
        - id: ksconf-check
        - id: ksconf-sort
        - id: ksconf-xml-format


For general reference, here's a copy of what we frequently use for our repos.

..  code-block:: yaml

    - repo: https://github.com/pre-commit/pre-commit-hooks
      rev: v2.0.0
      hooks:
        - id: trailing-whitespace
          exclude: README.md
        - id: end-of-file-fixer
          exclude: README.md$
        - id: check-json
        - id: check-xml
        - id: check-ast
        - id: check-added-large-files
          args: [ '--maxkb=50' ]
        - id: check-merge-conflict
        - id: detect-private-key
        - id: mixed-line-ending
          args: [ '--fix=lf' ]
    - repo: https://github.com/Kintyre/ksconf
      rev: v0.11.8
      hooks:
        - id: ksconf-check
        - id: ksconf-sort
          exclude: (props|logging)\.conf
        - id: ksconf-xml-format

..  tip::

    You should update ``rev`` to the most currently released stable version.
    Upgrading this frequently isn't typically necessary since these two operations are pretty basic and stable.
    However, it's still a good idea to review the change log to see what, if any, pre-commit functionality was updated.


.. note::

    Sometimes pre-commit can get in the way.

    Instead of disabling it entirely, it's often better to disable the specific rule that's causing an issue
    using the ``SKIP`` environmental variable.
    So for example, if intentionally adding a file over 50 Kb, a command like this will allow all the *other* rules to still run.

    ..  code-block:: sh

        SKIP=check-added-large-file git commit -m "Refresh lookup files for bogus TA"

    This and other tricks are fully documented in the `pre-commit`_ docs.
    However, this comes up frequently enough that it's worth repeating here.


Should my version of ksconf and pre-commit plugins be the same?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you're running both ``ksconf`` locally as well as the ksconf pre-commit plugin, then technically you have ksconf installed twice.
That may sound less than ideal, but practically, this isn't a problem.
As long as the version of the ksconf CLI tool is *close* to the ``rev`` listed in :file:`.pre-commit-config.yaml`, then everything should work fine.

Our suggestion:

 #. Keep versions in the same `major.minor` release range or bump the version every 6-12 months.
 #. Check the changelog for any pre-commit related changes or compatibility concerns.

While keeping ``ksconf`` CLI versions in sync across your environment is recommended, it doesn't matter as much for the pre-commit plugin.  Why?

 #. The pre-commit plugin offers a small subset of overall ksconf functionality.
 #. The exposed functionality is stable and changes infrequently.
 #. Updating pre-commit too frequently may cause unnecessary delays if you have a large team or high number of git clones throughout your environment, as each one will have to wait and upgrade the next time pre-commit is kicked off.


Git configuration tweaks
-----------------------------


.. _ksconf_ext_diff:

Ksconf as external difftool
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use :ref:`ksconf_cmd_diff` as an external *difftool* provider for :command:`git`.
Edit :file:`~/.gitconfig` and add the following entries:

..  code-block:: ini
    :name: ~/.gitconfig`

    [difftool "ksconf"]
        cmd = "ksconf --force-color diff \"$LOCAL\" \"$REMOTE\" | less -R"
    [difftool]
        prompt = false
    [alias]
        ksdiff = "difftool --tool=ksconf"


Now you can run this new ``git`` alias to compare files in your directory using the ``ksconf diff``
feature instead of the default textual diff that git provides.
This is especially helpful if the ``ksconf-sort`` pre-commit hook hasn't been enabled.

..  code-block:: sh

    git ksdiff props.conf


..  tip:: Wonky version of git?

    If you find yourself in the situation where ``git-difftool`` hasn't been fully installed correctly (or the Perl extensions are missing), then here's a workaround option for you.

    ..  code-block:: sh

        ksconf diff <(git show HEAD:./props.conf) props.conf

    Take note of the relative path prefix ``./``.
    In practice, this can be problematic.


Stanza aware textual diffs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Make ``git diff`` show the 'stanza' on the ``@@`` output lines.

..  note:: How does git know that?

    Ever wonder how ``git diff`` is able to show you the name of the function or method where changes
    were made?  This works for many programming languages out of the box.  If you've ever spent much
    time looking at diffs, that additional context is invaluable.  As it turns out, this is
    customizable by adding a stanza matching regular expression with a file pattern match.

Simply add the following settings to your git configuration:

..  code-block:: ini
    :name: ~/.gitconfig

    [diff "conf"]
        xfuncname = "^(\\[.*\\])$"

Then register this new ability with specific file patterns using git's ``attributes`` feature.
Edit :file:`~/.config/git/attributes` and add:

..  code-block:: none
    :name: ~/.config/git/attributes

    *.conf diff=conf
    *.meta diff=conf

..  note:: Didn't work as expected?

    Be aware that the location for your global-level attributes may be different.
    Use the following command to test if the settings have been applied.

   ..  code-block:: sh

       git check-attr -a -- *.conf

   Test to make sure the ``xfuncname`` attribute was set as expected:

   ..  code-block:: sh

       git config diff.conf.xfuncname


Git tricks
----------

Avoid replicating the .git folder
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Version controlling certain directories, like ``master-apps`` or ``shcluster`` can result in the entire ``.git`` folder being replicated to other Splunk instances.
This can be problematic because (1) this folder can be quite large, and (2) it can cause confusion on the receiving side leaving an admin to believe that the destination folder is version controlled.
Splunk doesn't provide a way to block the ``.git`` folder from being replicated.

Generally, there may be other more appropriate way to control content of these folders, but when faced with this situation, a simple workaround is to move the real ``.git`` folder to a secondary location (outside of the replicated folder) and instead us a ``.git`` file with a ``gitdir:`` pointer to the real git folder.
This is may sound complicated, but it's quite easy in practice.
Here's an example with a ``master-apps`` folder:

..  code-block:: sh

    cd $SPLUNK_HOME/etc/master-apps
    mv -v "${PWD}/.git" "${PWD}.git"
    echo "gitdir: ${PWD}.git" > "$PWD/.git"

After running the above commands, the ``.git`` folder is now named ``master-apps.git``, and ``master-apps/.git`` is now just a small file referencing the new location of the git repository folder.  Splunk deployment/synchronization operations now just copy a small file, rather than the ``.git`` folder.

More information is available at `gitrepository-layout <https://git-scm.com/docs/gitrepository-layout#_description>`_.

..  include:: common
