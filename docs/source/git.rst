Git tips & tricks
=================


Git configuration tweaks
-----------------------------

Ksconf as exteral difftool
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Setup ksconf as an external difftool provider for :command:`git`.
Edit :file:`~/.gitconfig` and add the following entires:

.. code-block:: ini
   :name: ~/.gitconfig`

   [difftool "ksconf"]
       cmd = "ksconf --force-color diff \"$LOCAL\" \"$REMOTE\" | less -R"
   [difftool]
       prompt = false
   [alias]
       ksdiff = "difftool --tool=ksconf"


Now you can run this new ``git`` alias to compare files in your directory using the ``ksconf diff``
feature instead of the default textual diff that git provides.

.. code-block:: sh

   git ksdiff props.conf


Stanza aware textual diffs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Make ``git diff`` show the 'stanza' on the ``@@`` output lines.

.. note:: How does git know that?

   Ever wonder how ``git diff`` is able to show you the name of the function or method where changes
   were made?  This works for many programming languages out of the box.  If you've ever spend much
   time looking at diffs that additional context is invaluable.  As it turns out, this is
   customizable by adding a stanza matching regular expression with a file pattern match.

Simply add the following settings to your git configuration:

.. code-block:: ini
   :name: ~/.gitconfig

   [diff "conf"]
       xfuncname = "^(\\[.*\\])$"

Then register this new ability with specific file patterns using git's ``attributes`` feature.
Edit :file:`~/.config/git/attributes` and add:

.. code-block:: none
   :name: ~/.config/git/attributes

   *.conf diff=conf
   *.meta diff=conf

.. note:: Didn't work as expected?

   Be aware that your location for your global-level attributes may be in a different location.  In
   any case, you can use the following commands to test if the settings have been applied correctly.

   .. code-block:: sh

      git check-attr -a -- *.conf

   Test to make sure the ``xfuncname`` attribute was set as expected:

   .. code-block:: sh

      git config diff.conf.xfuncname
