Random
======

Typographic and Convention
**************************

Pronounced:   k·s·kȯnf



Capitalization:


============    ====================================
Form            Acceptability factor
============    ====================================
``ksconf``      Always lower for CLI.
                Generally preferred.
KSCONF          Okay for titles.
Ksconf          Title case is okay too.
KSConf          You'll see this, but weird.
KsConf          No, except maybe in a class name?
KsconF          Thought about it.
                Reserved for ASCII art ONLY
============    ====================================


    | I wrote this while laughing at my own lack of consistency.
    | -- Lowell


.. _splunk conf updates:

How Splunk writes to conf files
********************************

Splunk does some counter intuitive thing when it writes to local conf files.

For example,

 #. All conf file updates are automatically minimized.
    Splunk never has to write the entire contents because updates *only* happen to "local" files.
 #. Modified stanzas are sometimes rewritten in place,
    and other times removed from the current position and moved to the bottom of the .conf file.
    This behavior appears to vary based on what REST endpoint is used to initiate the update.
 #. New stanzas are written with attributes sorted lexicographically.
    When a stanza is updated in place, the modified attributes may be updated in place and
    new entires are typically added at the bottom of the stanza.
 #. Sometimes boolean values persist in unexpected ways.
    Primarily this is because there's more than one way to represent them textually,
    and that textual representation is different than what's stored in default.
    Often, literal values are passed through a conf REST POST so they make it to disk,
    but when read, are translated into booleans.

.. A test for further note:  If you have field named ``false`` something like ``EVAL-false_field = false`` wouldn't look at the field named "false" but instead always return 0.



Essentially, Splunk will always "minimize" the conf file at each update.  This is because
Splunk internally keeps track of the final representation of the entire stanza (in memory), and only
when it's written to disk does Splunk care about the current contents of the local file.  In
fact, Splunk re-reads the conf file immediately before updating it.  This is why, if you've made a
local changes and forgot to reload, Splunk will typically not lose your changes. (Unless you've
updated the same attribute both places... I mean, it's not magic.)


..  tip:: Don't believe me? Try it yourself.

    To prove that it works this way, simply find a saved search that you modified from any app that
    you installed.  Look at the local conf file and observe your changes.  Now, go edit the saved
    search and restore some attribute to it's original value; the most obvious one here would be the
    ``search`` attribute, but that's tricky if it's multiple lines.  Now, go look at the local conf
    file again.  If you've updated it with *exactly* the same value, then that attribute will have been
    completely removed from the local file.  This is in fact a neat trick that can be used to revert
    local changes to allow future updates to "pass-though" unimpeded.  In SHC scenarios, this may
    be your only option to remove local settings.

Okay, so what's the value in having a :ref:`minimize <ksconf_cmd_minimize>` command if Splunk does
this automatically every time it's makes a change?  Well, simply put, because Splunk can't write to
all local file locations.  Splunk only writes to the local folders of system, etc/users, and etc/apps (and
sometimes to deployment-apps app.conf local file, but that's a different topic).

Also, there are times where boolean values will show up in an unexpected manor because of how
Splunk treats them internally.  It isn't certain if this is a silly mistake in the default .conf
files or a clever workaround to what's essentially a design flaw in the conf system. Either
way, we suspect the user benefits.  Because Splunk accepts more values as boolean than what it will
write out, certain boolean values will always be explicitly stored in the conf files.
This means that ``disabled`` and several other settings in ``savedsearches.conf`` always get
explicitly written.  How is that helpful?  Well, imagine what would happen if you accidentally
changed ``disabled = 1`` in the global stanzas in savedsearches.conf.  Well, *nothing* if all
savedsearches have that values explicitly written.  The point is this: there are times when
repeating yourself isn't a bad thing.  (Incidentally, this is the reason for the ``--preserve-key``
flag on the :ref:`minimize <ksconf_cmd_minimize>` command.)



..  _Grandfather Paradox:

Grandfather Paradox
*******************

The KSCONF Splunk app disadvantageously breaks it's designed paradigm.  Ksconf was designed to be
the program that manages all your other apps, so by deploying ksconf as an app itself, we open up the
possibility that ksconf could upgrade, deploy, or manage itself. Basically, it could cut off the limb 
that it's standing on. Practically, this can get messy, especially if
you're on Windows, where file locking is also likely to cause issues.

So sure, if you want to be picky, "Grandfather paradox" is probably the wrong analogy.
Pull requests are welcome.
